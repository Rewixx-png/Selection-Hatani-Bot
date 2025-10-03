# config.py
import logging
import sys
import os
import random 
from typing import Set, List

# --- Основные настройки ---
try:
    # Определяем базовую директорию проекта
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    TOKEN_PATH = os.path.join(BASE_DIR, "token.txt")
    with open(TOKEN_PATH, "r") as file:
        TOKEN = file.read().strip()
    logging.info("Токен успешно прочитан из файла token.txt")
except FileNotFoundError:
    logging.error("Файл token.txt не найден! 🥺")
    sys.exit()
except Exception as e:
    exc_type, exc_obj, exc_tb = sys.exc_info()
    fname = exc_tb.tb_frame.f_code.co_filename
    lineno = exc_tb.tb_lineno
    logging.error(f"Ошибка при чтении токена ({fname}:{lineno}): {e} 😥")
    sys.exit()

# --- Идентификаторы ---
CHAT_ID: int = -1002017590469  # ID чата отбора
BOT_USERNAME: str = "HataniAdminBot" 
ADMIN_IDS: Set[int] = {
    7485721661, 1052824235, 1867868165, 7385915582,
    650971663, 5192054637, 5723419877
}
USER_TO_DELETE: int = 5210630997 # ID пользователя для удаления сообщений

# --- База данных ---
DATABASE_FILE: str = "bot_database.db"

# --- Redis (для FSM Storage) ---
REDIS_HOST: str = 'localhost'
REDIS_PORT: int = 6379
REDIS_DB_FSM: int = 0 # База данных Redis для FSM

# --- Модерация ---
MUTE_DURATION: int = 30 * 60  # 30 минут в секундах
PROFANITY_WORDS: Set[str] = {
    "сука", "блядь", "пиздец", "хуй", "ебать", "гондон", "пидор", "хуесос", "мать", "еблан",
    "мудак", "тварь", "уебок", "залупа", "манда", "жопа", "дерьмо", "говнюк", "падла", "шлюха",
    "петух", "черт", "лох", "чмо", "урод", "сучка", "блядина", "пидарас", "хуила", "матерь",
    "ебанат", "мудила", "скотина", "уебище", "залупень", "мандовошка", "жопашник", "говно", "говноед",
    "паскуда", "блядюга", "курица", "дьявол", "лошара", "чертила", "выродок", "сучара", "блядская",
    "пидрила", "хуйня", "мамаша", "ебанутый", "мудозвон", "гадина", "уебан", "залупина", "мандище",
    "жопища", "говнище", "говнюшка", "стерва", "блядюшка", "козел", "бес", "ботаник", "чурка",
    "дебил", "сучье", "блядство", "пидорский", "хуевый", "мама", "ебанько", "мудорез", "гнида",
    "уебский", "залупный", "мандовый", "жопный", "говняный", "говнючий", "мерзавец", "блядский",
    "осел", "сатана", "зубрила", "хач", "кретин", "сученыш", "блядюжник", "пидормот", "хуеплес",
    "родители", "ебатория", "мудозвонство", "падаль", "уебищный", "залупоголовый", "мандотряс",
    "жополиз", "говномет", "говнятина", "подлец", "блядота", "баран", "шайтан", "очкарик",
    "чурбан", "идиот", "ублюдок", "засранец", "дурак", "кретин", "придурок", "тупица", "остолоп",
    "балбес", "болван", "лопух", "мембрана", "дырка", "вагина", "пенис", "яйца", "мошонка",
    "ссанье", "пердеж", "блевотина", "задрот", "гей", "лесбиянка", "трансвестит", "гермафродит",
    "импотент", "фригидная", "онанист", "мастурбатор", "извращенец", "фетишист", "зоофил",
    "педофил", "некрофил", "копрофил", "урофил", "скотина", "тварь", "мразь", "гад", "зверь",
    "паразит", "пиявка", "вшивый", "вшивая", "блохастый", "глист", "червяк", "таракан", "крыса",
    "сволочь", "стервец", "стервоза", "стервозный", "сучий", "блядский", "пидорский", "хуевый",
    "ебаный", "пиздецки", "хуево", "блядски", "ебано", "пиздец",
}
if len(PROFANITY_WORDS) < 100:
    logging.warning(f"Внимание: В списке ненормативной лексики сейчас {len(PROFANITY_WORDS)} слов. Рекомендуется добавить еще.")
else:
    logging.info(f"В списке ненормативной лексики {len(PROFANITY_WORDS)} слов.")

# --- Отбор ---
SELECTION_INACTIVE_KICK_DELAY: int = 10 * 60 
TIKTOK_SUBSCRIBER_THRESHOLD: int = 1000
REJECTED_PROGRAMS: Set[str] = {"CapCut", "Kine Master", "Power Direct"}
MAX_EDIT_FILE_SIZE_MB: int = 15
MAX_EDIT_FILE_SIZE_BYTES: int = MAX_EDIT_FILE_SIZE_MB * 1024 * 1024
EDIT_PROGRAM_CHOICES: dict = {
    "CapCut": "CapCut", "Kine Master": "Kine Master", "Power Direct": "Power Direct",
    "After Motion Z": "After Motion Z", "Alight Motion": "Alight Motion", "After Effects": "After Effects",
    "Node": "Node", "Sony Vegas": "Sony Vegas", "other": "Другая программа"
}
SELECTION_STEPS: List[str] = ["TikTok", "Подписчики", "Программа", "Эдит"]
SELECTION_PROGRESS_FORMAT: str = "📊 Прогресс: {current}/{total} | {steps_str}" 

def format_progress(current_step_index: int) -> str:
    total_steps = len(SELECTION_STEPS)
    steps_list = []
    for i, name in enumerate(SELECTION_STEPS):
        if i < current_step_index:
            steps_list.append(f"✅ {name}")
        elif i == current_step_index:
            steps_list.append(f"➡️ {name}") 
        else:
            steps_list.append(f"⏳ {name}") 
    steps_str = " | ".join(steps_list)
    return SELECTION_PROGRESS_FORMAT.format(current=current_step_index + 1, total=total_steps, steps_str=steps_str)

REJECTION_REASONS: dict = {
    "tech": "Слабая техника / эффекты", "quality": "Низкое качество видео", "idea": "Слабая идея / неоригинально",
    "music": "Несоответствие музыке / ритму", "other": "Другое (общая оценка)"
}

# --- URL ---
CREATOR_PROFILE_URL: str = "https://t.me/ILYAA2K23"
CREATOR_TIKTOK_URL: str = "https://www.tiktok.com/@tpebop.fx?_t=ZT-8ulfiFwpFHi&_r=1"
AGREEMENT_URL: str = "https://teletype.in/@rewix_x/bZRg7isIVXi"
RULES_URL: str = "https://teletype.in/@rewix_x/VDwYWdPiOrc"
SELECTION_CHAT_URL: str = "https://t.me/hatani_selection"

# --- Тексты сообщений ---
MSG_PRIVATE_CHAT_REDIRECT: str = f"Для прохождения отбора необходимо присоединиться к беседе: {SELECTION_CHAT_URL}"
MSG_ALREADY_STARTED_SELECTION: str = "⚠️ Вы уже начали процесс отбора."
MSG_ALREADY_COMPLETED_SELECTION: str = "⚠️ Вы уже прошли процесс отбора."
MSG_ADMIN_ONLY_COMMAND: str = "⚠️ Эта команда доступна только администраторам."
MSG_ADMIN_ONLY_BUTTON: str = "⚠️ Эта кнопка предназначена только для администрации."
MSG_WRONG_CHAT: str = "⚠️ Эта функция доступна только в беседе отбора."
POSITIVE_RESPONSES: List[str] = ["Отлично!", "Супер!", "Принято!", "Хорошо!", "Понял!", "Записал!"]
PROMPT_PHRASES: List[str] = ["Теперь, пожалуйста,", "Следующий шаг:", "Далее:", "Теперь нужно:"]

# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# <<< ДОБАВЛЕН ТОКЕН ДЛЯ ОБХОДА ЗАЩИТЫ >>>
# Токен от сервиса Monster API (DataDome) для решения капчи
ANTI_BOT_TOKEN: str = "v6WanzZx7tQmhaPMnkSlb_CDSKAP5xesvPUoOiB4NSspNXhTzmnP12HatUEd-H7lbmlZW8b-pS9-X4uqS3_V6EXnhsmKxI5bJMvA2oxOx9YO5Q0d2SohORwiVrW5ym4TsrocBZOvLgPHigWd-ZlS"