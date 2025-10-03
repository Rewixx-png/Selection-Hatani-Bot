import logging
import time
from aiogram import F, Router, types
from aiogram.filters import CommandStart, Command
from aiogram.utils.markdown import html_decoration as hd

import config
import db
from utils import format_user_link

router = Router()

@router.message(CommandStart(), F.chat.type == "private")
async def cmd_start_private(message: types.Message):
    user_id = message.from_user.id
    log_prefix = f"StartPM/{user_id}"
    logging.info(f"[{log_prefix}] Пользователь нажал /start в ЛС.")

    await db.mark_user_started_pm(user_id)

    reply_text = (f"Отлично! ✅ Вы подтвердили возможность общения со мной.\n\n"
                  f"Теперь возвращайтесь в чат отбора HataniSquad ({config.SELECTION_CHAT_URL}) "
                  f"и нажмите кнопку {hd.bold('«✅ Я уже написал /start в ЛС»')} "
                  f"под приветственным сообщением.")

    await message.reply(reply_text, disable_web_page_preview=True, parse_mode="HTML")
    logging.info(f"[{log_prefix}] Пользователь подтвердил ЛС, отправлено сообщение для возврата в чат.")


@router.message(F.chat.type == "private", F.content_type.in_({types.ContentType.TEXT}))
async def handle_private_message(message: types.Message):
    if not message.text.startswith('/'):
        await message.reply(config.MSG_PRIVATE_CHAT_REDIRECT, disable_web_page_preview=True)
        logging.info(f"Replied to private text message from user {message.from_user.id}")

@router.message(Command("hping"))
async def cmd_hping(message: types.Message):
    start_time = time.monotonic()
    sent_message = await message.reply("🏓 Понг...")
    end_time = time.monotonic()
    latency = (end_time - start_time) * 1000
    await sent_message.edit_text(
        f"TPEBOP PIDOPACIK :3 ({int(latency)}ms)"
    )