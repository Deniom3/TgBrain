"""
API endpoints для управления настройками приложения.

Предоставляет REST API для:
- Просмотра всех настроек
- Обновления настроек Telegram авторизации
- Обновления настроек LLM провайдеров
- Обновления общих настроек приложения
- Управления настройками чатов
- Управления переиндексацией эмбеддингов
- Управления webhook конфигурацией
"""

from fastapi import APIRouter

from .telegram import router as telegram_router
from .llm import router as llm_router
from .embedding import router as embedding_router
from .app import router as app_router
from .chats import router as chats_router
from .chat_summary_settings_endpoints import router as summary_settings_router
from .chat_users_endpoints import router as chat_users_router
from .chat_operations_endpoints import router as chat_operations_router
from .overview import router as overview_router
from .reindex import router as reindex_router, set_reindex_service, get_reindex_service
from .qr_auth import set_qr_auth_complete_callback, set_logout_complete_callback
from .webhook_endpoints import router as webhook_router

router = APIRouter(prefix="/api/v1/settings", tags=["Settings"])

# Подключаем все роутеры
router.include_router(telegram_router)
router.include_router(llm_router)
router.include_router(embedding_router)
router.include_router(app_router)
router.include_router(chats_router)
router.include_router(summary_settings_router)
router.include_router(chat_users_router)
router.include_router(chat_operations_router)
router.include_router(overview_router)
router.include_router(reindex_router)
router.include_router(webhook_router)

__all__ = [
    "router",
    "set_reindex_service",
    "get_reindex_service",
    "set_qr_auth_complete_callback",
    "set_logout_complete_callback",
]
