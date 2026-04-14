"""
API модуль TgBrain.

Компоненты:
- models: Pydantic модели для запросов/ответов
- endpoints: API endpoints (health, chat_summary_generate, chat_summary_retrieval, ask)
- callbacks: Callback функции (QR auth)

Пример использования:
    from src.api import health_router, chat_summary_retrieval_router
"""

from __future__ import annotations

from src.api.callbacks.qr_auth_callback import (
    _on_qr_auth_complete_handler,
    restart_ingester,
)
from src.api.endpoints.chat_summary_generate import (
    router as chat_summary_generate_router,
)
from src.api.endpoints.chat_summary_retrieval import (
    router as chat_summary_retrieval_router,
)
from src.api.endpoints.health import router as health_router
from src.api.models import HealthResponse

__all__ = [
    "HealthResponse",
    "health_router",
    "chat_summary_retrieval_router",
    "chat_summary_generate_router",
    "_on_qr_auth_complete_handler",
    "restart_ingester",
]
