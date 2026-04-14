"""
Корневые эндпоинты приложения.

Endpoints:
- GET /: Информация об API
- GET /qr-auth: Страница QR авторизации Telegram
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["Root"])

_STATIC_DIR = Path(__file__).parent.parent.parent.parent / "static"
_QR_AUTH_HTML = _STATIC_DIR / "qr_auth.html"


@router.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    """Корневой endpoint с информацией об API."""
    return {
        "name": "TgBrain API",
        "version": "1.0.0",
        "description": "REST API для поиска и суммаризации сообщений из Telegram-чатов",
        "docs": "/docs",
        "documentation": "/docs-app",
        "health": "/health",
    }


@router.get("/qr-auth", tags=["QR Auth"])
async def qr_auth_page() -> FileResponse:
    """
    Страница QR авторизации Telegram.

    Открывает веб-интерфейс для сканирования QR кода.
    """
    return FileResponse(str(_QR_AUTH_HTML), media_type="text/html")
