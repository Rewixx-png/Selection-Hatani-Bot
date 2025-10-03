import logging
import asyncio
import time
import sys
import os
import redis.asyncio as redis
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.exceptions import TelegramAPIError
from aiogram.client.default import DefaultBotProperties

try:
    import config
    import db
    import utils
    from handlers import main_router
except ImportError as e:
    print(f"Ошибка импорта: {e}. Убедитесь, что все файлы (.py) находятся в нужных местах.")
    sys.exit(1)
except AttributeError as e:
    print(f"Ошибка атрибута при импорте: {e}. Проверьте содержимое config.py и других модулей.")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
logging.info("--- Инициализация бота ---")

try:
    redis_client = redis.Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        db=config.REDIS_DB_FSM,
        decode_responses=False
    )
    logging.info("Прямое подключение к Redis успешно создано.")
except Exception as e:
    logging.error(f"Не удалось создать прямое подключение к Redis: {e}")
    sys.exit(1)

storage = RedisStorage(redis=redis_client)
logging.info(f"Используется Redis FSM Storage...")

dp = Dispatcher(storage=storage, redis=redis_client)
bot = Bot(token=config.TOKEN, default=DefaultBotProperties(parse_mode='HTML'))

dp.include_router(main_router)
logging.info("Все доступные хендлеры зарегистрированы через роутеры.")

async def on_startup(bot: Bot):
    logging.warning("--- Бот запускается ---")
    await db.create_tables()
    logging.info(f"Используется база данных: {config.DATABASE_FILE}")
    logging.info("Восстановление незавершенных мутов из БД...")
    active_mutes = await db.get_active_mutes()
    count = 0
    now = time.time()
    for user_id, chat_id, unmute_ts, notification_msg_id in active_mutes:
        if unmute_ts > now:
            await utils.schedule_unmute(bot, user_id, chat_id, unmute_ts)
            count += 1
        else:
            logging.info(f"Время мута для {user_id} в {chat_id} истекло во время офлайна, попытка размута...")
            from handlers.moderation import unmute_user_func
            try:
                success = await unmute_user_func(bot, user_id, chat_id, triggered_by_schedule=True)
                if success:
                    logging.info(f"Пользователь {user_id} размучен при старте.")
                    await db.remove_mute(user_id, chat_id)
                else:
                    logging.warning(f"Не удалось размутить пользователя {user_id} при старте.")
            except Exception as e_unmute:
                logging.error(f"Ошибка при попытке размута пользователя {user_id} на старте: {e_unmute}")
                await db.remove_mute(user_id, chat_id)
    logging.info(f"Запланировано {count} задач на размут.")
    logging.warning("--- Бот готов к работе ---")

async def on_shutdown(bot: Bot):
    logging.warning("--- Бот останавливается ---")
    logging.info("Отмена активных задач...")
    for task in list(utils.unmute_tasks.values()):
        if task and not task.done():
            task.cancel()
    for task in list(utils.kick_tasks.values()):
        if task and not task.done():
            task.cancel()
    await asyncio.sleep(0.1)
    await redis_client.close()
    logging.info("Прямое подключение к Redis закрыто.")
    await dp.storage.close()
    logging.info("Хранилище FSM закрыто.")
    await bot.session.close()
    logging.info("Сессия бота закрыта.")
    logging.warning("--- Бот остановлен ---")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.warning("--- Выключение бота ---")