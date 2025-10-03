# utils.py
import logging
import asyncio
import time
import re
from typing import Optional, Dict, Tuple, List, Union

from aiogram import Bot, types
from aiogram.utils.markdown import html_decoration as hd
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramNotFound,
    TelegramForbiddenError
)

import config
import db

# --- Форматирование ---
def format_user_link(user: Union[types.User, types.Chat]) -> str:
    """Форматирует ссылку на пользователя для HTML."""
    name_to_show = user.first_name or user.title or f"ID:{user.id}"
    name = hd.quote(str(name_to_show))
    return hd.link(name, f"tg://user?id={user.id}")

def format_username(user: Union[types.User, types.Chat]) -> str:
    """Возвращает @username или имя/название для HTML."""
    if user.username:
        return f"@{user.username}"
    else:
        name_to_show = user.first_name or user.title or f"ID:{user.id}"
        return hd.quote(str(name_to_show))

# --- Безопасные операции с API ---

async def safe_delete_message(bot: Bot, chat_id: int, message_id: int, log_prefix: str = ""):
    """Безопасно удаляет сообщение, логируя ошибки."""
    prefix = f"[{log_prefix}] " if log_prefix else ""
    try:
        await bot.delete_message(chat_id, message_id)
        logging.info(f"{prefix}Сообщение {message_id} в чате {chat_id} удалено.")
    except TelegramNotFound:
        logging.warning(f"{prefix}Сообщение {message_id} в чате {chat_id} не найдено для удаления.")
    except TelegramAPIError as e:
        logging.error(f"{prefix}Ошибка API при удалении сообщения {message_id} в чате {chat_id}: {e}")
    except Exception as e:
        logging.exception(f"{prefix}Неизвестная ошибка при удалении сообщения {message_id} в чате {chat_id}: {e}")

async def safe_edit_message_text(bot: Bot, text: str, chat_id: int, message_id: int,
                                 reply_markup=None, parse_mode='HTML', log_prefix: str = "") -> bool:
    """Безопасно редактирует текст сообщения."""
    prefix = f"[{log_prefix}] " if log_prefix else ""
    try:
        # <<< ИЗМЕНЕНО: Используем именованные аргументы для предотвращения ошибок >>>
        await bot.edit_message_text(
            text=text,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
        logging.info(f"{prefix}Сообщение {message_id} в чате {chat_id} отредактировано.")
        return True
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            logging.warning(f"{prefix}Сообщение {message_id} в чате {chat_id} не было изменено.")
        else:
            logging.error(f"{prefix}Ошибка BadRequest при редактировании сообщения {message_id} в чате {chat_id}: {e}")
        return False
    except TelegramNotFound:
        logging.warning(f"{prefix}Сообщение {message_id} в чате {chat_id} не найдено для редактирования.")
        return False
    except Exception as e:
        logging.exception(f"{prefix}Неизвестная ошибка при редактировании сообщения {message_id} в чате {chat_id}: {e}")
        return False

# ... (остальной код файла utils.py без изменений) ...

async def safe_edit_message_caption(bot: Bot, caption: str, chat_id: int, message_id: int,
                                    reply_markup=None, parse_mode='HTML', log_prefix: str = "") -> bool:
    prefix = f"[{log_prefix}] " if log_prefix else ""
    try:
        await bot.edit_message_caption(chat_id=chat_id, message_id=message_id, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
        logging.info(f"{prefix}Подпись сообщения {message_id} в чате {chat_id} отредактирована.")
        return True
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            logging.warning(f"{prefix}Подпись сообщения {message_id} в чате {chat_id} не была изменена.")
        else:
            logging.error(f"{prefix}Ошибка BadRequest при редактировании подписи {message_id} в чате {chat_id}: {e}")
        return False
    except TelegramNotFound:
        logging.warning(f"{prefix}Сообщение {message_id} в чате {chat_id} не найдено для редактирования подписи.")
        return False
    except TelegramAPIError as e:
        logging.error(f"{prefix}Ошибка API при редактировании подписи сообщения {message_id} в чате {chat_id}: {e}")
        return False
    except Exception as e:
        logging.exception(f"{prefix}Неизвестная ошибка при редактировании подписи сообщения {message_id} в чате {chat_id}: {e}")
        return False

async def safe_restrict_chat_member(bot: Bot, chat_id: int, user_id: int, permissions: types.ChatPermissions, until_date: Optional[int] = None, log_prefix: str = "") -> bool:
    prefix = f"[{log_prefix}] " if log_prefix else ""
    action = "Ограничение" if until_date else "Снятие ограничений"
    try:
        await bot.restrict_chat_member(chat_id, user_id, permissions, until_date=until_date)
        logging.info(f"{prefix}{action} прав для user_id {user_id} в chat_id {chat_id} выполнено успешно.")
        return True
    except TelegramBadRequest as e:
         error_text = str(e).lower()
         if "user is an administrator of the chat" in error_text or "can't restrict self" in error_text:
             logging.warning(f"{prefix}Не удалось {action.lower()} права user_id {user_id} (пользователь - админ/бот сам).")
         elif "not enough rights" in error_text or "can't remove chat owner" in error_text:
              logging.warning(f"{prefix}Не удалось {action.lower()} права user_id {user_id} (недостаточно прав у бота).")
         else:
             logging.error(f"{prefix}Неожиданная ошибка BadRequest при {action.lower()} прав user_id {user_id}: {e}")
         return False
    except TelegramAPIError as e:
        logging.error(f"{prefix}Ошибка API при {action.lower()} прав user_id {user_id}: {e}")
        return False
    except Exception as e:
        logging.exception(f"{prefix}Неизвестная ошибка при {action.lower()} прав user_id {user_id}: {e}")
        return False

async def safe_kick_chat_member(bot: Bot, chat_id: int, user_id: int, log_prefix: str = "") -> bool:
    prefix = f"[{log_prefix}] " if log_prefix else ""
    try:
        await bot.ban_chat_member(chat_id, user_id)
        logging.info(f"[{log_prefix}] Пользователь {user_id} забанен (кикнут) из чата {chat_id}.")
        await bot.unban_chat_member(chat_id, user_id, only_if_banned=True)
        return True
    except TelegramBadRequest as e:
         error_text = str(e).lower()
         if "user is an administrator of the chat" in error_text:
             logging.warning(f"{prefix}Не удалось кикнуть user_id {user_id} (пользователь - администратор).")
         elif "not enough rights" in error_text or "can't remove chat owner" in error_text:
              logging.warning(f"{prefix}Не удалось кикнуть user_id {user_id} (недостаточно прав у бота).")
         else:
             logging.error(f"{prefix}Неожиданная ошибка BadRequest при кике user_id {user_id}: {e}")
         return False
    except TelegramAPIError as e:
        logging.error(f"{prefix}Ошибка API при кике user_id {user_id}: {e}")
        return False
    except Exception as e:
        logging.exception(f"{prefix}Неизвестная ошибка при кике user_id {user_id}: {e}")
        return False

unmute_tasks: Dict[Tuple[int, int], asyncio.Task] = {}
kick_tasks: Dict[int, asyncio.Task] = {}

async def kick_and_notify(bot: Bot, user_id: int, chat_id: int, first_name: str, reason: str, subscribers: Optional[str] = None) -> bool:
    log_prefix = f"KickNotify/{user_id}"
    logging.info(f"[{log_prefix}] Попытка кика. Причина: {reason}")
    kicked = await safe_kick_chat_member(bot, chat_id, user_id, log_prefix=log_prefix)
    if kicked:
        temp_user = types.User(id=user_id, first_name=first_name, is_bot=False)
        user_link_str = format_user_link(temp_user)
        kick_message_text = (
            f"🚫 Пользователь {user_link_str} "
            f"(ID: {hd.code(str(user_id))}) был удален из чата отбора."
        )
        try:
            kick_msg = await bot.send_message(chat_id, kick_message_text, parse_mode="HTML")
            asyncio.create_task(delete_message_after(bot, chat_id, kick_msg.message_id, 60))
            return True
        except Exception as e:
            logging.error(f"[{log_prefix}] Ошибка при отправке уведомления о кике в чат: {e}")
            return True
    else:
        logging.warning(f"[{log_prefix}] Кик не удался.")
        return False

async def schedule_unmute(bot: Bot, user_id: int, chat_id: int, unmute_timestamp: int):
    from handlers.moderation import unmute_user_func
    now = int(time.time())
    delay = unmute_timestamp - now
    if delay <= 0:
        try:
            success = await unmute_user_func(bot, user_id, chat_id, triggered_by_schedule=True)
        except Exception as e_unmute:
             logging.error(f"Ошибка при немедленном размуте по расписанию {user_id}: {e_unmute}")
             await db.remove_mute(user_id, chat_id)
        return
    task_key = (user_id, chat_id)
    if task_key in unmute_tasks and not unmute_tasks[task_key].done():
        unmute_tasks[task_key].cancel()
    async def unmute_coro():
        try:
            await asyncio.sleep(delay)
            await unmute_user_func(bot, user_id, chat_id, triggered_by_schedule=True)
        except asyncio.CancelledError:
            logging.info(f"Задача на размут для {task_key} была отменена.")
        except Exception as e:
            logging.exception(f"Ошибка в корутине размута для {task_key}: {e}")
        finally:
            if task_key in unmute_tasks: del unmute_tasks[task_key]
    task = asyncio.create_task(unmute_coro())
    unmute_tasks[task_key] = task
    logging.info(f"Запланирован размут для {task_key} через {delay:.2f} секунд.")

def cancel_unmute_task(user_id: int, chat_id: int):
    task_key = (user_id, chat_id)
    if task_key in unmute_tasks and not unmute_tasks[task_key].done():
        unmute_tasks[task_key].cancel()
        return True
    return False

async def schedule_kick(bot: Bot, user_id: int, chat_id: int, delay: int, reason: str, user_first_name: str, initial_message: Optional[types.Message] = None):
    if user_id in kick_tasks and not kick_tasks[user_id].done():
        kick_tasks[user_id].cancel()
    async def kick_coro():
        try:
            await asyncio.sleep(delay)
            user_data = await db.get_user_selection_data(user_id)
            status = user_data['status'] if user_data else None
            started_pm = user_data['started_pm'] == 1 if user_data else False
            if status == 'pending' and not started_pm:
                kick_reason_pm = "не подтверждено начало диалога с ботом в ЛС"
                try:
                    await bot.send_message(user_id, f"Вы были удалены из чата отбора, так как не подтвердили старт в ЛС.")
                except Exception: pass
                kicked = await kick_and_notify(
                    bot=bot, user_id=user_id, chat_id=chat_id,
                    first_name=user_first_name, reason=kick_reason_pm
                )
                if kicked:
                     await db.set_user_selection_status(user_id, 'inactive_kick')
                     if initial_message:
                        kick_message_text = (
                            f"🚫 Пользователь {hd.link(hd.quote(user_first_name), f'tg://user?id={user_id}')} был удален.\n"
                            f"Причина: {hd.quote(kick_reason_pm)}."
                        )
                        await safe_edit_message_text(
                            bot, kick_message_text, chat_id, initial_message.message_id,
                            reply_markup=None, log_prefix=f"KickInactiveEdit/{user_id}"
                        )
            else:
                logging.info(f"Кик для user_id {user_id} отменен, статус: '{status}', начал ЛС: {started_pm}.")
        except asyncio.CancelledError:
            logging.info(f"Задача на кик для user_id {user_id} была отменена.")
        except Exception as e:
            logging.exception(f"Ошибка в корутине кика для user_id {user_id}: {e}")
        finally:
            if user_id in kick_tasks: del kick_tasks[user_id]
    task = asyncio.create_task(kick_coro())
    kick_tasks[user_id] = task
    logging.info(f"Запланирован кик user_id {user_id} через {delay} секунд. Причина: {reason}")

def cancel_kick_task(user_id: int):
    if user_id in kick_tasks and not kick_tasks[user_id].done():
        kick_tasks[user_id].cancel()
        return True
    return False

async def delete_message_after(bot: Bot, chat_id: int, message_id: int, delay: int):
     await asyncio.sleep(delay)
     await safe_delete_message(bot, chat_id, message_id, log_prefix=f"DelayedDelete/{message_id}")