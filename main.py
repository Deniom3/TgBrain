#!/usr/bin/env python3
"""
TgBrain — FastAPI приложение.
REST API для поиска, суммаризации и проверки здоровья.

Точка входа приложения. Содержит только:
- Создание FastAPI app
- Подключение middleware
- Подключение routers
- Запуск uvicorn
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(override=True)

from src.api.endpoints.ask import router as ask_router  # noqa: E402
from src.api.endpoints.chat_summary_generate import router as chat_summary_generate_router  # noqa: E402
from src.api.endpoints.chat_summary_retrieval import router as chat_summary_retrieval_router  # noqa: E402
from src.api.endpoints.docs_viewer import router as docs_viewer_router  # noqa: E402
from src.api.endpoints.external_ingest import router as external_ingest_router  # noqa: E402
from src.api.endpoints.health import router as health_router  # noqa: E402
from src.api.endpoints.import_endpoint import router as import_router  # noqa: E402
from src.api.endpoints.root import router as root_router  # noqa: E402
from src.api.endpoints.summary_send_webhook import router as summary_send_webhook_router  # noqa: E402
from src.api.dependencies import verify_api_key  # noqa: E402
from src.api.exception_handlers import register_exception_handlers  # noqa: E402
from src.api.qr_auth_callbacks import register_qr_auth_callbacks  # noqa: E402
from src.app import create_lifespan, init_app_state  # noqa: E402
from src.config.cors import parse_cors_origins  # noqa: E402
from src.config.logging_config import setup_logging  # noqa: E402
from src.settings_api import router as settings_router  # noqa: E402
from src.settings_api.qr_auth import router as qr_auth_router  # noqa: E402
from src.settings_api.reindex_speed import router as reindex_speed_router  # noqa: E402
from src.settings_api.system import router as system_router  # noqa: E402

# ==================== Настройка логирования ====================

setup_logging()
logger = logging.getLogger("tgbrain")

# ==================== Инициализация приложения ====================

lifespan = create_lifespan()

app = FastAPI(
    title="TgBrain",
    description="REST API для поиска и суммаризации сообщений из Telegram-чатов",
    version="1.0.0",
    lifespan=lifespan,
)

cors_origins = parse_cors_origins(os.getenv("CORS_ORIGINS"))
logger.info(f"CORS origins: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_app_state(app)

# ==================== Подключение routers ====================

# Публичные routers (без авторизации)
app.include_router(health_router)
app.include_router(qr_auth_router, prefix="/api/v1/settings")
app.include_router(root_router)
app.include_router(docs_viewer_router)

# Защищённые routers (требуют X-API-Key)
app.include_router(ask_router, prefix="/api/v1", dependencies=[Depends(verify_api_key)])
app.include_router(chat_summary_retrieval_router, dependencies=[Depends(verify_api_key)])
app.include_router(chat_summary_generate_router, dependencies=[Depends(verify_api_key)])
app.include_router(summary_send_webhook_router, dependencies=[Depends(verify_api_key)])
app.include_router(external_ingest_router, dependencies=[Depends(verify_api_key)])
app.include_router(import_router, dependencies=[Depends(verify_api_key)])
app.include_router(settings_router, dependencies=[Depends(verify_api_key)])
app.include_router(system_router, dependencies=[Depends(verify_api_key)])
app.include_router(reindex_speed_router, dependencies=[Depends(verify_api_key)])

# ==================== Обработчики и callbacks ====================

register_exception_handlers(app)
register_qr_auth_callbacks(app)


# ==================== Запуск ====================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
