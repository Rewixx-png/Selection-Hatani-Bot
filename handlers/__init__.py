from aiogram import Router
from . import common
from . import chat_events
from . import moderation
from . import selection
from . import admin

main_router = Router()
main_router.include_router(admin.router)
main_router.include_router(selection.router)
main_router.include_router(common.router)
main_router.include_router(moderation.router)
main_router.include_router(chat_events.router)