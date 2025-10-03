import logging
import time
import re
from typing import Optional

from aiogram import types, Router, Bot, F
from aiogram.filters import Command, and_f, or_f
from aiogram.utils.markdown import html_decoration as hd

import config
import db
import keyboards
import utils

router = Router()

async def mute_user(bot: Bot, user_id: int, chat_id: int, duration: int, reason: str,
                  original_message_id: Optional[int] = None, caused_by_word: Optional[str] = None) -> bool:
    try:
        user_info = await bot.get_chat(user_id)
        user_link = utils.format_user_link(user_info)
    except Exception as e:
        logging.warning(f"Не удалось получить информацию о пользователе {user_id} для мута: {e}")
        user_link = f"ID: {user_id}"

    unmute_timestamp = int(time.time()) + duration
    perms = types.ChatPermissions(can_send_messages=False, can_send_media_messages=False, can_send_other_messages=False, can_add_web_page_previews=False)

    success = await utils.safe_restrict_chat_member(
        bot=bot, chat_id=chat_id, user_id=user_id,
        permissions=perms, until_date=unmute_timestamp, log_prefix=f"Mute/{user_id}"
    )

    if not success:
        if user_id in config.ADMIN_IDS and not await db.get_admin_trax_mode(user_id):
            keyboard = keyboards.get_admin_profanity_trakh_keyboard(original_message_id or 0, caused_by_word or "слово")
            text = (f"🤯 Ой! Я пытался замутить админа {user_link} за слово '{hd.bold(hd.quote(caused_by_word or '???'))}' "
                    f"(причина: {reason}), но не смог... Нажмешь кнопку? 👉👈")
            await bot.send_message(chat_id, text, reply_markup=keyboard)
        return False

    keyboard = keyboards.get_unmute_admin_keyboard(user_id)
    text = f"🔇 Пользователь {user_link} был замучен на {duration // 60} минут.\nПричина: {hd.quote(reason)}."
    notification_msg_id = None
    try:
        mute_message = await bot.send_message(chat_id, text, reply_markup=keyboard)
        notification_msg_id = mute_message.message_id
    except Exception as e:
        logging.error(f"Ошибка при отправке уведомления о муте: {e}")

    await db.add_mute(user_id, chat_id, unmute_timestamp, notification_msg_id)
    await utils.schedule_unmute(bot, user_id, chat_id, unmute_timestamp)
    return True

async def unmute_user_func(bot: Bot, user_id: int, chat_id: int,
                           triggered_by_admin: bool = False, admin_id: Optional[int] = None,
                           triggered_by_schedule: bool = False) -> bool:
    log_prefix = f"Unmute/{user_id}"
    try:
        user_info = await bot.get_chat(user_id)
        user_link = utils.format_user_link(user_info)
    except Exception:
        user_link = f"ID: {user_id}"

    notification_msg_id = await db.get_mute_notification_id(user_id, chat_id)
    perms = types.ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True)
    success = await utils.safe_restrict_chat_member(bot, chat_id, user_id, perms, log_prefix=log_prefix)

    await db.remove_mute(user_id, chat_id)

    if not triggered_by_schedule:
        utils.cancel_unmute_task(user_id, chat_id)

    if not success:
        return False

    if notification_msg_id:
        unmute_text = f"✅ Пользователь {user_link} размучен"
        if triggered_by_admin and admin_id:
            try:
                admin_info = await bot.get_chat(admin_id)
                unmute_text += f" администратором {utils.format_user_link(admin_info)}."
            except Exception:
                 unmute_text += " администратором."
        elif triggered_by_schedule:
            unmute_text += " автоматически."
        else:
            unmute_text += "."
        await utils.safe_edit_message_text(bot, unmute_text, chat_id, notification_msg_id, reply_markup=None, log_prefix=log_prefix)

    logging.info(f"[{log_prefix}] Пользователь успешно размучен.")
    return True

@router.message(Command("trax"), F.from_user.id.in_(config.ADMIN_IDS), F.chat.type.in_({"supergroup", "private"}))
async def trax_command(message: types.Message):
    user_id = message.from_user.id
    try:
        current_status = await db.get_admin_trax_mode(user_id)
        new_status = not current_status
        await db.set_admin_trax_mode(user_id, new_status)
        status_text = "активирован ✅" if new_status else "деактивирован ❌"
        await message.reply(f"Режим администратора (TRAX) {status_text}")
    except Exception as e:
        logging.exception(f"Ошибка при обработке /trax для {user_id}: {e}")
        await message.reply("Произошла ошибка.")

@router.message(F.chat.id == config.CHAT_ID, F.from_user.id == config.USER_TO_DELETE)
async def delete_specific_user_messages(message: types.Message, bot: Bot):
    await utils.safe_delete_message(bot, message.chat.id, message.message_id, log_prefix=f"DeleteUserMsg/{message.from_user.id}")

@router.message(
    F.chat.id == config.CHAT_ID,
    or_f(F.text, F.caption)
)
async def check_profanity(message: types.Message, bot: Bot):
    user_id = message.from_user.id
    text = (message.text or message.caption).lower()

    if user_id in config.ADMIN_IDS and await db.get_admin_trax_mode(user_id):
        return

    found_word = None
    for word in config.PROFANITY_WORDS:
        pattern = r'(?i)\b' + re.escape(word) + r'\b'
        if re.search(pattern, text):
            found_word = word
            break

    if found_word:
        log_prefix = f"Profanity/{user_id}"
        logging.info(f"[{log_prefix}] Найдено слово '{found_word}' в сообщении {message.message_id}.")
        await utils.safe_delete_message(bot, message.chat.id, message.message_id, log_prefix)
        await mute_user(
            bot=bot, user_id=user_id, chat_id=message.chat.id,
            duration=config.MUTE_DURATION, reason="ненормативная лексика",
            original_message_id=message.message_id, caused_by_word=found_word
        )

@router.callback_query(F.data.startswith("admin:profanity_trakh:"), F.from_user.id.in_(config.ADMIN_IDS))
async def admin_profanity_trakh_callback(call: types.CallbackQuery, bot: Bot):
     try:
         word = call.data.split(":")[-1]
         await utils.safe_edit_message_text(
             bot=bot, chat_id=call.message.chat.id, message_id=call.message.message_id,
             text=f"Ай-ай-ай, кто-то сказал '{hd.bold(hd.quote(word))}'! 🤭",
             reply_markup=None
         )
         await call.answer("Ай ~ ~")
     except Exception as e:
         logging.exception(f"Ошибка в admin_profanity_trakh_callback: {e}")
         await call.answer("Ой, что-то пошло не так")