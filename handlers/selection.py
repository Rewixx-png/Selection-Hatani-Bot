import logging
import re
import random
from io import BytesIO
from playwright.async_api import async_playwright
import redis.asyncio as redis

from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, InputMediaPhoto, InputMediaVideo
from aiogram.utils.markdown import html_decoration as hd

import config
import db
import keyboards
import utils
from states import SelectionStates

router = Router()
router.message.filter(F.chat.id == config.CHAT_ID)
router.callback_query.filter(F.message.chat.id == config.CHAT_ID)

async def get_screenshot_playwright(url: str) -> bytes | None:
    browser = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 800}
            )
            
            if config.ANTI_BOT_TOKEN:
                await context.add_cookies([{'name': 'datadome', 'value': config.ANTI_BOT_TOKEN, 'domain': '.tiktok.com', 'path': '/'}])
                logging.info("Cookie для обхода защиты (datadome) установлен.")
            
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            page = await context.new_page()
            
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)

            cookie_banner_selector = '[data-e2e="cookie-banner-accept-button"]'
            try:
                await page.locator(cookie_banner_selector).click(timeout=3000)
                logging.info("Баннер с cookie найден и нажат.")
            except Exception:
                logging.info("Баннер с cookie не найден, продолжаем.")

            video_grid_selector = '[data-e2e="user-post-item-list"]'
            await page.wait_for_selector(video_grid_selector, timeout=20000)
            
            await page.wait_for_timeout(1000)
            
            screenshot_bytes = await page.screenshot()
            
            logging.info(f"Скриншот для URL {url} успешно сделан через Playwright.")
            return screenshot_bytes
    except Exception as e:
        logging.exception(f"Ошибка при работе Playwright для URL {url}: {e}")
        return None
    finally:
        if browser:
            await browser.close()

@router.callback_query(F.data == "selection:start")
async def start_selection(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    log_prefix = f"SelectionStart/{user_id}"

    status = await db.get_user_selection_status(user_id)
    if status in ['passed', 'failed']:
        await call.answer(config.MSG_ALREADY_COMPLETED_SELECTION, show_alert=True)
        return
    current_fsm_state = await state.get_state()
    if status == 'started' and current_fsm_state is not None:
        await call.answer(config.MSG_ALREADY_STARTED_SELECTION, show_alert=True)
        return

    logging.info(f"[{log_prefix}] Пользователь начал отбор.")
    await state.set_state(SelectionStates.waiting_for_tiktok_link)
    
    await call.message.edit_text(
        "➡️ Пожалуйста, пришлите ссылку на ваш TikTok профиль.",
        reply_markup=None
    )
    await state.update_data(prompt_message_id=call.message.message_id)
    await call.answer()

@router.message(SelectionStates.waiting_for_tiktok_link, F.text)
async def process_tiktok_link(message: types.Message, state: FSMContext, bot: Bot, redis: redis.Redis):
    user_id = message.from_user.id
    log_prefix = f"TikTokLink/{user_id}"

    if "tiktok.com" not in message.text or not message.text.startswith("https://"):
        await message.reply("⚠️ Пожалуйста, отправьте корректную и полную ссылку на TikTok профиль (начиная с https://).")
        return

    data = await state.get_data()
    prompt_id = data.get("prompt_message_id")
    if prompt_id:
        await utils.safe_delete_message(bot, message.chat.id, prompt_id)

    tiktok_link = message.text
    await message.delete() 
    
    wait_msg = await bot.send_message(
        message.chat.id, 
        "⏳ **Проверяю ссылку...**\nЗапускаю браузер и открываю ваш профиль. Это может занять до 45 секунд.",
        parse_mode="Markdown"
    )
    screenshot_bytes = await get_screenshot_playwright(tiktok_link)
    await wait_msg.delete()

    if not screenshot_bytes:
        await bot.send_message(message.chat.id, "❌ Не удалось получить скриншот профиля. Возможно, ссылка неверна, или TikTok временно заблокировал доступ. Попробуйте отправить ссылку еще раз.")
        prompt_message = await bot.send_message(message.chat.id, "➡️ Пожалуйста, пришлите ссылку на ваш TikTok профиль.")
        await state.update_data(prompt_message_id=prompt_message.message_id)
        return

    redis_key = f"screenshot:{user_id}"
    await redis.set(redis_key, screenshot_bytes, ex=900)
    
    await state.update_data(
        tiktok_link=tiktok_link,
        screenshot_redis_key=redis_key 
    )

    photo_file = BufferedInputFile(screenshot_bytes, filename="profile.jpg")
    keyboard = keyboards.get_profile_confirmation_keyboard()
    sent_photo = await bot.send_photo(
        chat_id=message.chat.id,
        photo=photo_file,
        caption="Это ваш профиль?",
        reply_markup=keyboard
    )
    
    await state.update_data(screenshot_message_id=sent_photo.message_id)
    await state.set_state(SelectionStates.waiting_for_profile_confirmation)

@router.callback_query(SelectionStates.waiting_for_profile_confirmation, F.data == "selection:confirm_profile_no")
async def process_profile_confirmation_no(call: types.CallbackQuery, state: FSMContext):
    await call.message.delete()
    prompt_message = await call.message.answer("Понял. Пожалуйста, отправьте правильную ссылку на ваш TikTok профиль.")
    await state.set_state(SelectionStates.waiting_for_tiktok_link)
    await state.update_data(prompt_message_id=prompt_message.message_id)
    await call.answer()

@router.callback_query(SelectionStates.waiting_for_profile_confirmation, F.data == "selection:confirm_profile_yes")
async def process_profile_confirmation_yes(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    wait_msg = await call.message.answer("⏳ Сохраняю ваш выбор...")
    
    data = await state.get_data()
    screenshot_message_id = data.get("screenshot_message_id")
    if screenshot_message_id:
        await utils.safe_delete_message(call.bot, call.message.chat.id, screenshot_message_id)
    
    await wait_msg.delete()
    
    prompt_msg = await call.message.answer(
        "✅ Отлично! Теперь финальный шаг: отправьте ваш лучший эдит в виде видеофайла.\n"
        f"❗️Ограничение по размеру: {config.MAX_EDIT_FILE_SIZE_MB} МБ."
    )
    await state.update_data(prompt_message_id=prompt_msg.message_id)
    await state.set_state(SelectionStates.waiting_for_edit_video)

@router.message(SelectionStates.waiting_for_edit_video, F.video)
async def process_edit_video(message: types.Message, state: FSMContext, bot: Bot, redis: redis.Redis):
    user_id = message.from_user.id
    log_prefix = f"EditVideo/{user_id}"

    if message.video.file_size > config.MAX_EDIT_FILE_SIZE_BYTES:
        await message.reply(f"⚠️ Видео слишком большое! Максимальный размер - {config.MAX_EDIT_FILE_SIZE_MB} МБ.")
        return

    user_data = await state.get_data()
    prompt_id = user_data.get("prompt_message_id")
    if prompt_id:
        await utils.safe_delete_message(bot, message.chat.id, prompt_id)

    wait_msg = await message.answer("✅ Видео принято! Формирую заявку для администраторов...")
    await message.delete()

    logging.info(f"[{log_prefix}] Получено видео для отбора (file_id: {message.video.file_id})")
    
    tiktok_link = user_data.get('tiktok_link', 'Не указан')
    screenshot_redis_key = user_data.get('screenshot_redis_key')
    screenshot_bytes = None
    if screenshot_redis_key:
        screenshot_bytes = await redis.get(screenshot_redis_key)
        await redis.delete(screenshot_redis_key)
        logging.info(f"[{log_prefix}] Скриншот извлечен и удален из Redis по ключу {screenshot_redis_key}")
    
    edit_video_file_id = message.video.file_id
    await state.clear()

    applicant_link = utils.format_user_link(message.from_user)
    tiktok_username_match = re.search(r'@([\w.-]+)', tiktok_link)
    tiktok_username = tiktok_username_match.group(0) if tiktok_username_match else "Профиль"
    
    try:
        media_group = []
        video_caption = (
            f"🔥 {hd.bold('Новая заявка на отбор!')} 🔥\n\n"
            f"👤 Кандидат: {applicant_link} ({hd.code(str(user_id))})\n"
            f"🔗 TikTok: {hd.link(tiktok_username, tiktok_link)}"
        )
        
        if screenshot_bytes:
            photo_input = BufferedInputFile(screenshot_bytes, filename="profile.jpg")
            media_group.append(InputMediaPhoto(media=photo_input))
        
        media_group.append(InputMediaVideo(media=edit_video_file_id, caption=video_caption))

        sent_media_messages = await bot.send_media_group(
            chat_id=config.CHAT_ID,
            media=media_group
        )
        
        control_panel_text = "👇 Администраторы, оцените эдит и вынесите решение."
        keyboard = keyboards.get_approve_reject_keyboard(
            applicant_id=user_id,
            tiktok_link=tiktok_link,
            tiktok_username=tiktok_username
        )
        
        control_panel_message = await bot.send_message(
            chat_id=config.CHAT_ID,
            text=control_panel_text,
            reply_to_message_id=sent_media_messages[0].message_id,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

        await bot.pin_chat_message(config.CHAT_ID, control_panel_message.message_id)
        
        await wait_msg.delete()
        
        logging.info(f"[{log_prefix}] Заявка (медиагруппа + панель) отправлена на модерацию (msg_id: {control_panel_message.message_id}).")
        await bot.send_message(user_id, "✅ Ваша заявка отправлена на рассмотрение! Ожидайте решения администрации.")

    except Exception as e:
        await wait_msg.delete()
        logging.exception(f"[{log_prefix}] Ошибка при отправке заявки на модерацию: {e}")
        await bot.send_message(user_id, "❌ Произошла ошибка при отправке вашей заявки. Попробуйте снова или обратитесь к администратору.")
        await db.set_user_selection_status(user_id, 'error_send')