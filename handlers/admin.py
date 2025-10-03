# handlers/admin.py
import logging
import re

from aiogram import types, Router, Bot, F
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.utils.markdown import html_decoration as hd

import config
import db
import keyboards
import utils
from handlers.moderation import unmute_user_func

router = Router()
admin_chat_filter = F.message.chat.id == config.CHAT_ID
router.callback_query.filter(admin_chat_filter)


@router.callback_query(F.data.startswith("admin:approve:"), F.from_user.id.in_(config.ADMIN_IDS))
async def approve_application_callback(call: types.CallbackQuery, bot: Bot):
    """Обработчик одобрения заявки."""
    admin_id = call.from_user.id
    chat_id = call.message.chat.id
    
    # Сообщение, на которое ответила панель управления (то есть, медиагруппа)
    media_message = call.message.reply_to_message
    
    try:
        applicant_id = int(call.data.split(":")[-1])
    except (IndexError, ValueError):
        await call.answer("❌ Ошибка: Неверный ID пользователя в кнопке.", show_alert=True)
        return

    log_prefix = f"Approve/{applicant_id}"
    logging.info(f"[{log_prefix}] Администратор {admin_id} одобрил заявку.")
    
    # Ищем caption в сообщениях медиагруппы
    caption = ""
    if media_message and media_message.media_group_id:
        # Если это медиагруппа, ищем сообщение с caption
        # В нашем случае это всегда второе сообщение (видео)
        # Для простоты ищем caption в самом reply_to_message, если он там есть
        if media_message.caption:
            caption = media_message.caption
    
    tiktok_link_match = re.search(r"🔗 TikTok: <a href=\"(.*?)\">", caption)
    tiktok_link_from_caption = tiktok_link_match.group(1) if tiktok_link_match else "Не найдена"
    program_from_caption = "Не указана" # Эта информация больше не собирается

    # Удаляем и панель управления, и сообщение, на которое она отвечала (первое в медиагруппе)
    await utils.safe_delete_message(bot, chat_id, call.message.message_id, log_prefix=log_prefix)
    if media_message:
       await utils.safe_delete_message(bot, chat_id, media_message.message_id, log_prefix=log_prefix)

    try:
        applicant_info = await bot.get_chat(applicant_id)
        applicant_link = utils.format_user_link(applicant_info)
        admin_info = await bot.get_chat(admin_id)
        admin_link = utils.format_user_link(admin_info)
    except Exception:
        applicant_link = f"ID: {applicant_id}"
        admin_link = f"ID: {admin_id}"

    approved_text_chat = (
        f"✅ Заявка пользователя {applicant_link} {hd.bold('одобрена')}!\n"
        f"👤 Администратор: {admin_link}\n\n"
        f"🔗 Кандидату необходимо связаться с {hd.link('владельцем', config.CREATOR_PROFILE_URL)} для получения ссылки."
    )
    approved_text_pm = (
         f"🎉 Поздравляем! Ваша заявка в HataniSquad {hd.bold('одобрена')}!\n\n"
         f"Для вступления в основную беседу, свяжитесь с {hd.link('владельцем', config.CREATOR_PROFILE_URL)}."
    )

    await bot.send_message(chat_id, approved_text_chat, disable_web_page_preview=True)
    try:
        await bot.send_message(applicant_id, approved_text_pm, disable_web_page_preview=True)
    except (TelegramBadRequest, TelegramForbiddenError) as e_pm:
        logging.warning(f"[{log_prefix}] Не удалось отправить ЛС об одобрении: {e_pm}")

    await db.record_passed_user(applicant_id, tiktok_link_from_caption, program_from_caption)
    await call.answer("✅ Заявка одобрена.")


@router.callback_query(F.data.startswith("admin:reject:"), F.from_user.id.in_(config.ADMIN_IDS))
async def reject_application_callback(call: types.CallbackQuery, bot: Bot):
    """Показывает кнопки выбора причины отклонения."""
    try:
        applicant_id = int(call.data.split(":")[-1])
    except (IndexError, ValueError):
        await call.answer("❌ Ошибка: Неверный ID.", show_alert=True)
        return

    try:
        original_text = call.message.text or ""
    except AttributeError:
        await call.answer("⚠️ Исходное сообщение уже удалено, действие невозможно.", show_alert=True)
        return

    new_text = f"{original_text}\n\n---\n📝 {hd.bold('Выберите причину отклонения:')}"
    keyboard = keyboards.get_rejection_reason_keyboard(applicant_id)

    # <<< ИСПРАВЛЕНО: Используем safe_edit_message_text, т.к. у сообщения нет caption >>>
    await utils.safe_edit_message_text(
        bot=bot, text=new_text, chat_id=call.message.chat.id, message_id=call.message.message_id,
        reply_markup=keyboard, log_prefix=f"RejectInit/{applicant_id}"
    )
    await call.answer("📝 Выберите причину отклонения.")


@router.callback_query(F.data.startswith("admin:reject_reason:"), F.from_user.id.in_(config.ADMIN_IDS))
async def handle_rejection_reason(call: types.CallbackQuery, bot: Bot):
    """Обрабатывает выбор причины отклонения."""
    try:
        _, _, applicant_id_str, reason_code = call.data.split(":")
        applicant_id = int(applicant_id_str)
        rejection_reason = config.REJECTION_REASONS.get(reason_code)
        if not rejection_reason: raise ValueError("Неверный код причины")
    except Exception as e:
        logging.error(f"Ошибка парсинга callback_data в handle_rejection_reason: {call.data} ({e})")
        await call.answer("❌ Ошибка: Неверные данные кнопки.", show_alert=True)
        return

    log_prefix = f"RejectConfirm/{applicant_id}"
    logging.info(f"[{log_prefix}] Админ {call.from_user.id} отклонил заявку. Причина: {rejection_reason}")
    
    media_message = call.message.reply_to_message
    caption = ""
    # Ищем caption в сообщениях медиагруппы
    if media_message and media_message.media_group_id:
        if media_message.caption:
            caption = media_message.caption
    
    tiktok_link_match = re.search(r"🔗 TikTok: <a href=\"(.*?)\">", caption)
    tiktok_link_from_caption = tiktok_link_match.group(1) if tiktok_link_match else "Не найдена"
    applicant_name_match = re.search(r"👤 Кандидат: <a href=.*?>(.*?)</a>", caption)
    applicant_name_from_caption = hd.quote(applicant_name_match.group(1)) if applicant_name_match else f"ID:{applicant_id}"
    program_from_caption = "Не указана"

    rejection_pm_text = f"❌ К сожалению, ваша заявка в HataniSquad отклонена.\nПричина: {hd.quote(rejection_reason)}"
    try:
        await bot.send_message(applicant_id, rejection_pm_text)
    except (TelegramBadRequest, TelegramForbiddenError) as e:
        logging.warning(f"[{log_prefix}] Не удалось отправить ЛС об отклонении: {e}")

    # Удаляем панель и медиа
    await utils.safe_delete_message(bot, call.message.chat.id, call.message.message_id, log_prefix=log_prefix)
    if media_message:
        await utils.safe_delete_message(bot, call.message.chat.id, media_message.message_id, log_prefix=log_prefix)

    await utils.kick_and_notify(
        bot=bot, user_id=applicant_id, chat_id=config.CHAT_ID,
        first_name=applicant_name_from_caption,
        reason=f"заявка отклонена админом ({rejection_reason})",
        subscribers=None
    )
    await db.record_failed_user(applicant_id, tiktok_link_from_caption, program_from_caption, rejection_reason)
    await call.answer("❌ Заявка отклонена.")


@router.callback_query(F.data.startswith("admin:unmute:"), F.from_user.id.in_(config.ADMIN_IDS))
async def unmute_user_admin_callback(call: types.CallbackQuery, bot: Bot):
    """Обработчик кнопки 'Размутить' для админа."""
    try:
        user_id_to_unmute = int(call.data.split(":")[-1])
    except (IndexError, ValueError):
        await call.answer("❌ Ошибка: Неверный ID пользователя.", show_alert=True)
        return

    success = await unmute_user_func(
        bot=bot, user_id=user_id_to_unmute, chat_id=call.message.chat.id,
        triggered_by_admin=True, admin_id=call.from_user.id
    )

    if success:
        admin_info = await bot.get_chat(call.from_user.id)
        user_info = await bot.get_chat(user_id_to_unmute)
        final_text = f"✅ Пользователь {utils.format_user_link(user_info)} размучен администратором {utils.format_user_link(admin_info)}."
        try:
            await call.message.edit_text(final_text, reply_markup=None)
        except TelegramBadRequest as e:
             if "message is not modified" not in str(e):
                 logging.error(f"Ошибка при редактировании сообщения после размута: {e}")
        await call.answer("✅ Пользователь размучен.")
    else:
        try:
            await call.message.edit_text(call.message.text + "\n(Действие уже выполнено или невозможно)", reply_markup=None)
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                 logging.error(f"Ошибка при редактировании сообщения о неудавшемся размуте: {e}")
        await call.answer("⚠️ Не удалось размутить (возможно, уже размучен).", show_alert=True)


@router.callback_query(F.data.startswith("admin:unban:"))
async def unban_user_admin_callback(call: types.CallbackQuery, bot: Bot):
    """Обработчик кнопки 'Снять блокировку' для админа."""
    member = await bot.get_chat_member(chat_id=call.message.chat.id, user_id=call.from_user.id)
    if not isinstance(member, (types.ChatMemberOwner, types.ChatMemberAdministrator)):
        await call.answer("⚠️ Эта кнопка доступна только администраторам чата.", show_alert=True)
        return

    try:
        user_id_to_unban = int(call.data.split(":")[-1])
    except (IndexError, ValueError):
        await call.answer("❌ Ошибка: Неверный ID пользователя.", show_alert=True)
        return

    log_prefix = f"Unban/{user_id_to_unban}"
    try:
        await bot.unban_chat_member(chat_id=call.message.chat.id, user_id=user_id_to_unban, only_if_banned=True)
        logging.info(f"[{log_prefix}] Администратор {call.from_user.id} снял блокировку с пользователя.")
        
        await db.delete_user_selection_status(user_id_to_unban)
        await db.delete_failed_user(user_id_to_unban)
        logging.info(f"[{log_prefix}] Статус пользователя и запись о 'failed' удалены из БД.")
        
        pm_unban_text = "✅ Администратор снял с вас временную блокировку в чате отбора HataniSquad. Теперь вы можете снова попробовать пройти отбор."
        try:
            await bot.send_message(user_id_to_unban, pm_unban_text)
            logging.info(f"[{log_prefix}] Уведомление о снятии блокировки отправлено пользователю в ЛС.")
        except (TelegramForbiddenError, TelegramBadRequest):
            logging.warning(f"[{log_prefix}] Не удалось отправить ЛС о снятии блокировки (возможно, бот заблокирован).")
        
        admin_info = call.from_user
        try:
            user_info = await bot.get_chat(user_id_to_unban)
        except Exception:
            user_info = types.User(id=user_id_to_unban, is_bot=False, first_name=f"ID:{user_id_to_unban}")

        final_text = (
            f"✅ Пользователь {utils.format_user_link(user_info)} был разблокирован "
            f"администратором {utils.format_user_link(admin_info)}."
        )
        await call.message.edit_text(final_text, reply_markup=None)
        await call.answer("✅ Блокировка снята.")

    except Exception as e:
        logging.error(f"[{log_prefix}] Ошибка при снятии блокировки: {e}")
        await call.answer("❌ Не удалось снять блокировку. Возможно, пользователь уже разбанен.", show_alert=True)