import logging
import random

from aiogram import types, Router, Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.markdown import html_decoration as hd

import config
import db
import keyboards
import utils
from states import SelectionStates

router = Router()
router.message.filter(F.chat.id == config.CHAT_ID)
router.callback_query.filter(F.message.chat.id == config.CHAT_ID)

@router.message(F.new_chat_members)
async def greet_new_member(message: types.Message, bot: Bot):
    for user in message.new_chat_members:
        if user.id == bot.id:
            try:
                if message.chat.id != config.CHAT_ID:
                    await bot.leave_chat(message.chat.id)
                    logging.info(f"Бот покинул чат {message.chat.id} ({message.chat.title}).")
            except Exception as e:
                logging.error(f"Ошибка при выходе из чата {message.chat.id}: {e}")
            return

        user_name = hd.quote(user.first_name)
        user_id = user.id
        log_prefix = f"NewMember/{user_id}"
        logging.info(f"[{log_prefix}] Новый участник {user_name} присоединился к чату.")

        status_data = await db.get_user_selection_data(user_id)
        status = status_data['status'] if status_data else None

        if status in ['passed', 'failed', 'inactive_kick']:
            logging.warning(f"[{log_prefix}] Пользователь уже есть в базе со статусом '{status}'.")
            perms = types.ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_add_web_page_previews=True, can_send_other_messages=True)
            await utils.safe_restrict_chat_member(bot, config.CHAT_ID, user_id, perms, log_prefix=f"RejoinUnrestrict/{user_id}")
            continue

        perms = types.ChatPermissions(can_send_messages=False, can_send_media_messages=False, can_send_other_messages=False, can_add_web_page_previews=False)
        restricted = await utils.safe_restrict_chat_member(bot, config.CHAT_ID, user_id, perms, log_prefix=f"NewMemberRestrict/{user_id}")

        if restricted:
            keyboard = keyboards.get_unmute_start_keyboard(user_id)
            welcome_text = (
                f"Приветствуем, {user_name}!\n\n"
                f"Добро пожаловать на {hd.bold('отбор')} в сообщество {hd.bold('HataniSquad')}.\n\n"
                f"❗️{hd.bold('Важный шаг:')} Пожалуйста, нажмите кнопку {hd.bold('«🤖 Перейти в ЛС»')} ниже, "
                f"чтобы написать мне в личные сообщения и нажать там {hd.code('/start')}.\n\n"
                f"✅ После этого вернитесь сюда и нажмите вторую кнопку {hd.bold('«✅ Я уже написал /start»')}."
            )
            try:
                welcome_message = await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")
                await db.set_user_selection_status(user_id, 'pending')
                await utils.schedule_kick(
                    bot=bot, user_id=user_id, chat_id=config.CHAT_ID,
                    delay=config.SELECTION_INACTIVE_KICK_DELAY,
                    reason="не начал диалог в ЛС и не подтвердил",
                    user_first_name=user.first_name,
                    initial_message=welcome_message
                )
                logging.info(f"[{log_prefix}] Приветственное сообщение для {user_id} отправлено, запланирован кик.")
            except Exception as e:
                logging.exception(f"[{log_prefix}] Ошибка при отправке приветствия/планировании кика для {user_id}: {e}")
        else:
            logging.error(f"[{log_prefix}] Не удалось ограничить права для нового пользователя {user_id}.")

@router.callback_query(F.data.startswith("selection:start_verification:"))
async def start_verification_callback(call: types.CallbackQuery, state: FSMContext):
    user_id = int(call.data.split(":")[-1])
    callback_user_id = call.from_user.id
    log_prefix = f"StartVerification/{user_id}"

    if callback_user_id != user_id:
        await call.answer("⚠️ Эта кнопка предназначена для нового участника.", show_alert=True)
        return

    if not await db.check_user_started_pm(user_id):
        await call.answer(f"Пожалуйста, сначала перейдите в ЛС к боту и напишите /start там!", show_alert=True)
        logging.info(f"[{log_prefix}] Пользователь нажал подтверждение, но не стартовал в ЛС.")
        return

    utils.cancel_kick_task(user_id)
    logging.info(f"[{log_prefix}] Задача на кик отменена.")

    agreement_text = "Отлично! Теперь прочитайте пользовательское соглашение:"
    keyboard = keyboards.get_agreement_keyboard(user_id)
    try:
        await call.message.edit_text(agreement_text, reply_markup=keyboard)
        await state.set_state(SelectionStates.waiting_for_agreement)
        await db.set_user_selection_status(user_id, 'started')
        logging.info(f"[{log_prefix}] Пользователю предложено соглашение, state: waiting_for_agreement.")
        await call.answer()
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer()
        else:
            logging.exception(f"[{log_prefix}] Ошибка при показе соглашения: {e}")
            await call.answer("Произошла ошибка.", show_alert=True)
    except Exception as e:
        logging.exception(f"[{log_prefix}] Ошибка при показе соглашения: {e}")
        await call.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data.startswith("selection:confirm_agreement:"), SelectionStates.waiting_for_agreement)
async def confirm_agreement_callback(call: types.CallbackQuery, state: FSMContext):
    user_id = int(call.data.split(":")[-1])

    if call.from_user.id != user_id:
        await call.answer("⚠️ Эта кнопка для вас.", show_alert=True)
        return

    rules_text = "Теперь, пожалуйста, ознакомьтесь с правилами HataniSquad:"
    keyboard = keyboards.get_rules_keyboard(user_id)
    try:
        await call.message.edit_text(rules_text, reply_markup=keyboard)
        await state.set_state(SelectionStates.waiting_for_rules)
        logging.info(f"[ConfirmAgreement/{user_id}] Пользователю предложены правила.")
        await call.answer()
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer()
        else:
            logging.exception(f"[ConfirmAgreement/{user_id}] Ошибка при показе правил: {e}")
            await call.answer("Произошла ошибка.", show_alert=True)
    except Exception as e:
        logging.exception(f"[ConfirmAgreement/{user_id}] Ошибка при показе правил: {e}")
        await call.answer("Произошла ошибка.", show_alert=True)

@router.callback_query(F.data.startswith("selection:confirm_rules:"), SelectionStates.waiting_for_rules)
async def confirm_rules_callback(call: types.CallbackQuery, state: FSMContext, bot: Bot):
    user_id = int(call.data.split(":")[-1])
    log_prefix = f"ConfirmRules/{user_id}"

    if call.from_user.id != user_id:
        await call.answer("⚠️ Эта кнопка для вас.", show_alert=True)
        return

    perms = types.ChatPermissions(
        can_send_messages=True, can_send_media_messages=True,
        can_send_other_messages=True, can_add_web_page_previews=True
    )
    unrestricted = await utils.safe_restrict_chat_member(bot, config.CHAT_ID, user_id, perms, log_prefix=log_prefix)

    if unrestricted:
        response_start = random.choice(config.POSITIVE_RESPONSES)
        menu_text = (
            f"{response_start} Вы подтвердили правила и можете общаться в чате.\n\n"
            f"ℹ️ Добро пожаловать в {hd.bold('главное меню')}.\n"
            f"👉 Если хотите пройти отбор, нажмите соответствующую кнопку."
        )
        keyboard = await keyboards.get_main_menu_keyboard(user_id)
        try:
            await call.message.edit_text(menu_text, reply_markup=keyboard)
            await state.clear()
            logging.info(f"[{log_prefix}] Пользователь подтвердил правила, разблокирован. FSM сброшен.")
            await call.answer("Теперь вы можете писать в чате!")
        except Exception as e:
            logging.exception(f"[{log_prefix}] Ошибка при показе главного меню: {e}")
            await state.clear()
    else:
        logging.error(f"[{log_prefix}] Не удалось снять ограничения после подтверждения правил.")
        await call.answer("Произошла ошибка. Обратитесь к администратору.", show_alert=True)
        await state.clear()