# db.py
import aiosqlite
import logging
from datetime import datetime, timezone
from typing import Optional, List, Tuple

import config

DATABASE_FILE = config.DATABASE_FILE

async def create_tables():
    """Создает таблицы в базе данных, если они не существуют."""
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            db.row_factory = aiosqlite.Row
            await db.execute('''
                CREATE TABLE IF NOT EXISTS passed_users (
                    user_id INTEGER PRIMARY KEY, tiktok_link TEXT, edit_program TEXT, approval_timestamp TEXT
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS failed_users (
                    user_id INTEGER PRIMARY KEY, tiktok_link TEXT, edit_program TEXT, rejection_reason TEXT, rejection_timestamp TEXT
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS admin_trax_mode (
                    admin_id INTEGER PRIMARY KEY, trax_enabled INTEGER DEFAULT 0 NOT NULL
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS active_mutes (
                    user_id INTEGER, chat_id INTEGER, unmute_timestamp INTEGER NOT NULL, notification_message_id INTEGER,
                    PRIMARY KEY (user_id, chat_id)
                )
            ''')
            await db.execute('''
               CREATE TABLE IF NOT EXISTS selection_status (
                    user_id INTEGER PRIMARY KEY, status TEXT NOT NULL, last_update TEXT, started_pm INTEGER DEFAULT 0 NOT NULL
               )
            ''')
            await db.commit()
            logging.info("Таблицы базы данных созданы или уже существуют.")
    except aiosqlite.Error as e:
        logging.error(f"Ошибка при создании таблиц: {e}")
        if "duplicate column name: started_pm" not in str(e):
            try:
                async with aiosqlite.connect(DATABASE_FILE) as db:
                    logging.warning("Таблица selection_status уже существует, попытка добавить колонку started_pm...")
                    await db.execute("ALTER TABLE selection_status ADD COLUMN started_pm INTEGER DEFAULT 0 NOT NULL;")
                    await db.commit()
            except aiosqlite.Error as alter_e:
                 logging.error(f"Не удалось добавить колонку started_pm: {alter_e}")

async def set_user_selection_status(user_id: int, status: str):
    """Устанавливает или обновляет статус отбора пользователя."""
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            timestamp = datetime.now(timezone.utc).isoformat()
            await db.execute("INSERT OR IGNORE INTO selection_status (user_id, status, last_update, started_pm) VALUES (?, ?, ?, 0)", (user_id, status, timestamp))
            await db.execute("UPDATE selection_status SET status = ?, last_update = ? WHERE user_id = ?", (status, timestamp, user_id))
            await db.commit()
    except aiosqlite.Error as e:
        logging.error(f"Ошибка при установке статуса отбора для user_id {user_id}: {e}")

async def get_user_selection_data(user_id: int) -> Optional[aiosqlite.Row]:
    """Получает все данные о статусе отбора пользователя."""
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT status, started_pm FROM selection_status WHERE user_id = ?", (user_id,))
            return await cursor.fetchone()
    except aiosqlite.Error as e:
        logging.error(f"Ошибка при получении данных статуса для user_id {user_id}: {e}")
        return None

async def get_user_selection_status(user_id: int) -> Optional[str]:
    """Получает текущий статус отбора пользователя."""
    data = await get_user_selection_data(user_id)
    return data['status'] if data else None

async def mark_user_started_pm(user_id: int):
    """Отмечает, что пользователь запустил бота в ЛС."""
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            await db.execute("INSERT OR IGNORE INTO selection_status (user_id, status, last_update, started_pm) VALUES (?, ?, ?, 0)",
                         (user_id, 'unknown_pm_start', datetime.now(timezone.utc).isoformat()))
            await db.execute("UPDATE selection_status SET started_pm = 1 WHERE user_id = ?", (user_id,))
            await db.commit()
    except aiosqlite.Error as e:
        logging.error(f"Ошибка при установке флага started_pm для user_id {user_id}: {e}")

async def check_user_started_pm(user_id: int) -> bool:
    """Проверяет, запускал ли пользователь бота в ЛС."""
    data = await get_user_selection_data(user_id)
    return bool(data and data['started_pm'] == 1)

async def delete_user_selection_status(user_id: int):
    """Удаляет запись о статусе отбора пользователя."""
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            await db.execute("DELETE FROM selection_status WHERE user_id = ?", (user_id,))
            await db.commit()
            logging.info(f"Статус отбора для user_id {user_id} удален.")
    except aiosqlite.Error as e:
        logging.error(f"Ошибка при удалении статуса отбора для user_id {user_id}: {e}")

async def get_admin_trax_mode(admin_id: int) -> bool:
    """Получает статус trax mode администратора."""
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT trax_enabled FROM admin_trax_mode WHERE admin_id=?", (admin_id,))
            result = await cursor.fetchone()
            return bool(result and result['trax_enabled'] == 1)
    except aiosqlite.Error as e:
        logging.error(f"Ошибка при получении trax mode для admin_id {admin_id}: {e}")
        return False

async def set_admin_trax_mode(admin_id: int, enabled: bool):
    """Устанавливает статус trax mode администратора."""
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            await db.execute("REPLACE INTO admin_trax_mode (admin_id, trax_enabled) VALUES (?, ?)", (admin_id, 1 if enabled else 0))
            await db.commit()
    except aiosqlite.Error as e:
        logging.error(f"Ошибка при установке trax mode для admin_id {admin_id}: {e}")

async def record_passed_user(user_id: int, tiktok_link: Optional[str], edit_program: Optional[str]):
    """Записывает пользователя в таблицу прошедших отбор."""
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            timestamp = datetime.now(timezone.utc).isoformat()
            await db.execute("INSERT OR REPLACE INTO passed_users (user_id, tiktok_link, edit_program, approval_timestamp) VALUES (?, ?, ?, ?)", (user_id, tiktok_link, edit_program, timestamp))
            await db.commit()
        await set_user_selection_status(user_id, 'passed')
    except aiosqlite.Error as e:
        logging.error(f"Ошибка при записи прошедшего пользователя {user_id}: {e}")

async def record_failed_user(user_id: int, tiktok_link: Optional[str], edit_program: Optional[str], rejection_reason: str):
    """Записывает пользователя в таблицу не прошедших отбор."""
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            timestamp = datetime.now(timezone.utc).isoformat()
            await db.execute("INSERT OR REPLACE INTO failed_users (user_id, tiktok_link, edit_program, rejection_reason, rejection_timestamp) VALUES (?, ?, ?, ?, ?)", (user_id, tiktok_link, edit_program, rejection_reason, timestamp))
            await db.commit()
        await set_user_selection_status(user_id, 'failed')
    except aiosqlite.Error as e:
        logging.error(f"Ошибка при записи не прошедшего пользователя {user_id}: {e}")

async def add_mute(user_id: int, chat_id: int, unmute_timestamp: int, notification_message_id: Optional[int]):
    """Добавляет или обновляет запись об активном муте."""
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            await db.execute("REPLACE INTO active_mutes (user_id, chat_id, unmute_timestamp, notification_message_id) VALUES (?, ?, ?, ?)", (user_id, chat_id, unmute_timestamp, notification_message_id))
            await db.commit()
    except aiosqlite.Error as e:
        logging.error(f"Ошибка при добавлении мута для user_id {user_id}: {e}")

async def remove_mute(user_id: int, chat_id: int):
    """Удаляет запись об активном муте."""
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            await db.execute("DELETE FROM active_mutes WHERE user_id = ? AND chat_id = ?", (user_id, chat_id))
            await db.commit()
    except aiosqlite.Error as e:
        logging.error(f"Ошибка при удалении мута для user_id {user_id}: {e}")

async def get_active_mutes() -> List[Tuple[int, int, int, Optional[int]]]:
    """Возвращает список всех активных мутов."""
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            db.row_factory = aiosqlite.Row
            current_time = int(datetime.now(timezone.utc).timestamp())
            cursor = await db.execute("SELECT user_id, chat_id, unmute_timestamp, notification_message_id FROM active_mutes WHERE unmute_timestamp > ?", (current_time - 60,))
            rows = await cursor.fetchall()
            return [(row['user_id'], row['chat_id'], row['unmute_timestamp'], row['notification_message_id']) for row in rows]
    except aiosqlite.Error as e:
        logging.error(f"Ошибка при получении активных мутов: {e}")
        return []

async def get_mute_notification_id(user_id: int, chat_id: int) -> Optional[int]:
    """Получает ID сообщения с уведомлением о муте."""
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT notification_message_id FROM active_mutes WHERE user_id = ? AND chat_id = ?", (user_id, chat_id))
            result = await cursor.fetchone()
            return result['notification_message_id'] if result and result['notification_message_id'] else None
    except aiosqlite.Error as e:
        logging.error(f"Ошибка при получении ID уведомления о муте для user_id {user_id}: {e}")
        return None

async def delete_failed_user(user_id: int):
    """Удаляет запись о пользователе из таблицы не прошедших отбор."""
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db:
            await db.execute("DELETE FROM failed_users WHERE user_id = ?", (user_id,))
            await db.commit()
            logging.info(f"Запись о 'failed' для user_id {user_id} удалена.")
    except aiosqlite.Error as e:
        logging.error(f"Ошибка при удалении 'failed' записи для user_id {user_id}: {e}")