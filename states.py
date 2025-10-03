# states.py
from aiogram.fsm.state import State, StatesGroup

class SelectionStates(StatesGroup):
    # Состояния для первоначального входа и согласия с правилами
    waiting_for_agreement = State()
    waiting_for_rules = State()

    # Новый, упрощенный процесс отбора
    waiting_for_tiktok_link = State()
    waiting_for_profile_confirmation = State() # Новое состояние для подтверждения скриншота
    waiting_for_edit_video = State()