# keyboards.py
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import config # Используем config.py

async def get_main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру главного меню."""
    from db import get_user_selection_status # Импорт здесь, чтобы избежать циклической зависимости при старте

    builder = InlineKeyboardBuilder()
    status = await get_user_selection_status(user_id)

    # Кнопка отбора показывается, если статус не 'passed' и не 'failed'
    if status not in ['passed', 'failed']:
        builder.button(text="🎯 Начать отбор в HataniSquad", callback_data="selection:start")

    builder.button(text="👤 Профиль создателя", url=config.CREATOR_PROFILE_URL)
    builder.button(text="🎥 TikTok создателя", url=config.CREATOR_TIKTOK_URL)
    
    builder.adjust(1)
    return builder.as_markup()

def get_agreement_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения пользовательского соглашения."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📜 Пользовательское соглашение", url=config.AGREEMENT_URL)
    builder.button(text="✅ Подтвердить", callback_data=f"selection:confirm_agreement:{user_id}")
    builder.adjust(1)
    return builder.as_markup()

def get_rules_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения правил."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📜 Правила HataniSquad", url=config.RULES_URL)
    builder.button(text="✅ Подтвердить", callback_data=f"selection:confirm_rules:{user_id}")
    builder.adjust(1)
    return builder.as_markup()

def get_unmute_start_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Кнопки для нового участника: перейти в ЛС и подтвердить старт."""
    builder = InlineKeyboardBuilder()
    bot_pm_url = f"https://t.me/{config.BOT_USERNAME}?start=verify"
    builder.button(text="🤖 Перейти в ЛС к боту", url=bot_pm_url)
    builder.button(text="✅ Я уже написал /start в ЛС", callback_data=f"selection:start_verification:{user_id}")
    builder.adjust(1)
    return builder.as_markup()

def get_profile_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения профиля TikTok."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, это мой профиль", callback_data="selection:confirm_profile_yes")
    builder.button(text="❌ Нет, ввести другую ссылку", callback_data="selection:confirm_profile_no")
    builder.adjust(1)
    return builder.as_markup()

def get_approve_reject_keyboard(applicant_id: int, tiktok_link: str, tiktok_username: str) -> InlineKeyboardMarkup:
    """Клавиатура для одобрения/отклонения заявки администратором (первичная)."""
    builder = InlineKeyboardBuilder()
    builder.button(text=f"👤 ТТ: {tiktok_username}", url=tiktok_link)
    builder.button(text="✅ Одобрить", callback_data=f"admin:approve:{applicant_id}")
    builder.button(text="❌ Отклонить", callback_data=f"admin:reject:{applicant_id}")
    builder.adjust(1, 2)
    return builder.as_markup()

def get_rejection_reason_keyboard(applicant_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для выбора причины отклонения админом."""
    builder = InlineKeyboardBuilder()
    for code, text in config.REJECTION_REASONS.items():
        builder.button(text=text, callback_data=f"admin:reject_reason:{applicant_id}:{code}")
    builder.adjust(1)
    return builder.as_markup()

def get_unmute_admin_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для администратора, чтобы размутить пользователя."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔓 Размутить", callback_data=f"admin:unmute:{user_id}")
    return builder.as_markup()

def get_admin_profanity_trakh_keyboard(message_id: int, word: str) -> InlineKeyboardMarkup:
     """Клавиатура для 'трахнуть' админа за мат."""
     builder = InlineKeyboardBuilder()
     builder.button(text="Трахнуть 😉", callback_data=f"admin:profanity_trakh:{message_id}:{word}")
     return builder.as_markup()

def get_unban_admin_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для администратора, чтобы разбанить пользователя."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔓 Снять блокировку", callback_data=f"admin:unban:{user_id}")
    return builder.as_markup()