from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, chat, settings, files, config

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(chat.router)
api_router.include_router(settings.router)
api_router.include_router(files.router)
api_router.include_router(config.router)

