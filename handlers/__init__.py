# handlers/__init__.py
from aiogram import Router

# Импортируем роутеры из всех модулей-обработчиков
from . import common
from . import chat_events
from . import moderation
from . import selection
from . import admin

# Создаем главный роутер, который будет подключен к диспетчеру
main_router = Router()

# Включаем в него все остальные роутеры
# Порядок важен: сначала более специфичные, потом общие
main_router.include_router(admin.router)
main_router.include_router(selection.router)
main_router.include_router(common.router)
main_router.include_router(moderation.router)
main_router.include_router(chat_events.router) # События чата (вход/выход) часто лучше ставить в конец