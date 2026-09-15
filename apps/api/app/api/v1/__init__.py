"""v1 路由聚合。"""

from fastapi import APIRouter

from app.api.v1 import auth, chat, dashboard, files, health, roles, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(roles.router)
api_router.include_router(files.router)
api_router.include_router(dashboard.router)
api_router.include_router(chat.router)

__all__ = ["api_router"]
