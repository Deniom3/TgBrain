"""Интеграционные тесты покрытия API key auth для всех endpoints."""
import os
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from src.config import get_settings

pytestmark = pytest.mark.integration


# ======================================================================
# Константы: защищённые endpoints (73 штуки)
# ======================================================================

PROTECTED_ENDPOINTS = [
    # Ask (1)
    ("POST", "/api/v1/ask", {"question": "test", "chat_id": 1}),

    # Messages/Ingest (1)
    ("POST", "/api/v1/messages/ingest", {"chat_id": 1, "text": "test", "date": "2024-01-01T00:00:00"}),

    # Messages/Import (3)
    ("POST", "/api/v1/messages/import", None),
    ("GET", "/api/v1/messages/import/test-task/progress", None),
    ("DELETE", "/api/v1/messages/import/test-task/cancel", None),

    # Summary Generate (2)
    ("POST", "/api/v1/chats/1/summary/generate", None),
    ("POST", "/api/v1/chats/summary/generate", {"chat_ids": [1]}),

    # Summary Send Webhook (1)
    ("POST", "/api/v1/chats/1/summary/send-webhook", None),

    # Settings/App (4)
    ("GET", "/api/v1/settings/app", None),
    ("GET", "/api/v1/settings/app/log_level", None),
    ("PUT", "/api/v1/settings/app/log_level", {"value": "DEBUG"}),
    ("PUT", "/api/v1/settings/app/timezone", {"value": "UTC"}),

    # Settings/Telegram (3)
    ("GET", "/api/v1/settings/telegram", None),
    ("PUT", "/api/v1/settings/telegram", {"api_id": 123, "api_hash": "test", "phone_number": "+1234567890"}),
    ("GET", "/api/v1/settings/telegram/check", None),

    # Settings/LLM (5)
    ("GET", "/api/v1/settings/llm", None),
    ("GET", "/api/v1/settings/llm/gemini", None),
    ("PUT", "/api/v1/settings/llm/gemini", {"is_active": True}),
    ("POST", "/api/v1/settings/llm/gemini/activate", None),
    ("POST", "/api/v1/settings/llm/gemini/check", None),

    # Settings/Embedding (7)
    ("GET", "/api/v1/settings/embedding", None),
    ("GET", "/api/v1/settings/embedding/ollama", None),
    ("PUT", "/api/v1/settings/embedding/ollama/model", {"model": "test"}),
    ("PUT", "/api/v1/settings/embedding/ollama", {"is_active": True}),
    ("POST", "/api/v1/settings/embedding/ollama/activate", None),
    ("POST", "/api/v1/settings/embedding/ollama/refresh-dimension", None),
    ("POST", "/api/v1/settings/embedding/ollama/check", None),

    # Settings/Chats CRUD (6)
    ("GET", "/api/v1/settings/chats", None),
    ("GET", "/api/v1/settings/chats/list", None),
    ("GET", "/api/v1/settings/chats/monitored", None),
    ("GET", "/api/v1/settings/chats/1", None),
    ("PUT", "/api/v1/settings/chats/1", {"title": "test"}),
    ("DELETE", "/api/v1/settings/chats/1", None),

    # Settings/Chat Operations (4)
    ("POST", "/api/v1/settings/chats/1/toggle", None),
    ("POST", "/api/v1/settings/chats/1/enable", None),
    ("POST", "/api/v1/settings/chats/1/disable", None),
    ("POST", "/api/v1/settings/chats/bulk-update", {"chat_ids": [1]}),

    # Settings/Chat Users (3)
    ("POST", "/api/v1/settings/chats/sync", None),
    ("POST", "/api/v1/settings/chats/user/add", {"chat_id": 1, "user_id": 1}),
    ("POST", "/api/v1/settings/chats/user/remove", {"chat_id": 1, "user_id": 1}),

    # Settings/Chat Summary Settings (10)
    ("POST", "/api/v1/settings/chats/1/summary/enable", None),
    ("POST", "/api/v1/settings/chats/1/summary/disable", None),
    ("POST", "/api/v1/settings/chats/1/summary/toggle", None),
    ("PUT", "/api/v1/settings/chats/1/summary/period", {"hours": 24}),
    ("PUT", "/api/v1/settings/chats/1/summary/schedule", {"schedule": "0 9 * * *"}),
    ("GET", "/api/v1/settings/chats/1/summary/schedule", None),
    ("DELETE", "/api/v1/settings/chats/1/summary/schedule", None),
    ("PUT", "/api/v1/settings/chats/1/summary/prompt", {"prompt": "test"}),
    ("GET", "/api/v1/settings/chats/1/summary/prompt", None),
    ("DELETE", "/api/v1/settings/chats/1/summary/prompt", None),

    # Settings/Webhook (4)
    ("PUT", "/api/v1/settings/chats/1/webhook/config", {"url": "http://test"}),
    ("GET", "/api/v1/settings/chats/1/webhook/config", None),
    ("DELETE", "/api/v1/settings/chats/1/webhook/config", None),
    ("POST", "/api/v1/settings/chats/1/webhook/test", None),

    # Settings/Reindex (6)
    ("GET", "/api/v1/settings/reindex/check", None),
    ("GET", "/api/v1/settings/reindex/stats", None),
    ("GET", "/api/v1/settings/reindex/status", None),
    ("POST", "/api/v1/settings/reindex/start", None),
    ("POST", "/api/v1/settings/reindex/control", {"action": "pause"}),
    ("GET", "/api/v1/settings/reindex/history", None),

    # Settings/Reindex Speed (2)
    ("GET", "/api/v1/settings/reindex/speed", None),
    ("PATCH", "/api/v1/settings/reindex/speed", {"speed_mode": "low"}),

    # Settings/Overview (1)
    ("GET", "/api/v1/settings/overview", None),

    # Chat Summary Retrieval (6)
    ("GET", "/api/v1/chats/1/summary", None),
    ("GET", "/api/v1/chats/1/summary/latest", None),
    ("GET", "/api/v1/chats/1/summary/1", None),
    ("DELETE", "/api/v1/chats/1/summary/1", None),
    ("POST", "/api/v1/chats/1/summary/cleanup", None),
    ("GET", "/api/v1/chats/summary/stats", None),

    # System (4)
    ("GET", "/api/v1/system/throughput", None),
    ("GET", "/api/v1/system/stats", None),
    ("GET", "/api/v1/system/flood-history", None),
    ("GET", "/api/v1/system/request-history", None),
]


# ======================================================================
# Публичные endpoints (10 тестов)
# ======================================================================

@pytest.mark.asyncio
async def test_root_endpoint_public(monkeypatch):
    """GET / → 200 без X-API-Key даже при установленном API_KEY."""
    monkeypatch.setenv("API_KEY", "test-integration-key")
    get_settings.cache_clear()

    from main import app

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_qr_auth_page_public(monkeypatch):
    """GET /qr-auth → 200 без X-API-Key даже при установленном API_KEY."""
    monkeypatch.setenv("API_KEY", "test-integration-key")
    get_settings.cache_clear()

    from main import app

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/qr-auth")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_endpoint_public(monkeypatch):
    """GET /health → 200 без X-API-Key даже при установленном API_KEY."""
    monkeypatch.setenv("API_KEY", "test-integration-key")
    get_settings.cache_clear()

    from main import app

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_docs_endpoint_public(monkeypatch):
    """GET /docs → 200 без X-API-Key даже при установленном API_KEY."""
    monkeypatch.setenv("API_KEY", "test-integration-key")
    get_settings.cache_clear()

    from main import app

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/docs")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_openapi_endpoint_public(monkeypatch):
    """GET /openapi.json → 200 без X-API-Key даже при установленном API_KEY."""
    monkeypatch.setenv("API_KEY", "test-integration-key")
    get_settings.cache_clear()

    from main import app

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/openapi.json")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_qr_auth_status_public(monkeypatch):
    """GET /api/v1/settings/telegram/auth-status → 200 без X-API-Key."""
    monkeypatch.setenv("API_KEY", "test-integration-key")
    get_settings.cache_clear()

    from main import app

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/settings/telegram/auth-status")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_qr_code_generation_public(monkeypatch):
    """POST /api/v1/settings/telegram/qr-code → 200 без X-API-Key."""
    monkeypatch.setenv("API_KEY", "test-integration-key")
    get_settings.cache_clear()

    from datetime import datetime, timedelta, timezone
    from unittest.mock import AsyncMock, patch

    from src.auth.models import QRAuthSession
    from src.domain.models.auth import TelegramAuth
    from src.domain.value_objects import ApiHash, ApiId
    from main import app

    mock_repo = AsyncMock()
    mock_repo.is_session_active = AsyncMock(return_value=False)
    mock_repo.get = AsyncMock(return_value=TelegramAuth(
        id=1,
        api_id=ApiId(12345),
        api_hash=ApiHash("a" * 32),
    ))
    app.state.telegram_auth_repo = mock_repo

    now = datetime.now(timezone.utc)
    mock_session = QRAuthSession(
        session_id="test-session-id",
        session_name="qr_auth_test",
        qr_code_data="mock_qr_data",
        created_at=now,
        expires_at=now + timedelta(minutes=5),
    )

    try:
        with patch("src.auth.service.QRAuthService.create_session", new_callable=AsyncMock, return_value=mock_session):
            transport = ASGITransport(app=app, raise_app_exceptions=False)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/settings/telegram/qr-code")

        assert response.status_code == 200
    finally:
        app.state.telegram_auth_repo = None


@pytest.mark.asyncio
async def test_qr_status_public(monkeypatch):
    """GET /api/v1/settings/telegram/qr-status/{id} → 200 без X-API-Key."""
    monkeypatch.setenv("API_KEY", "test-integration-key")
    get_settings.cache_clear()

    from main import app

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/settings/telegram/qr-status/test-session-id")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_qr_cancel_public(monkeypatch):
    """POST /api/v1/settings/telegram/qr-cancel/{id} → 200 без X-API-Key."""
    monkeypatch.setenv("API_KEY", "test-integration-key")
    get_settings.cache_clear()

    from unittest.mock import AsyncMock, MagicMock

    from src.settings_api import qr_auth as qr_auth_module
    from main import app

    mock_service = MagicMock()
    mock_service.cancel_session = AsyncMock(return_value=True)
    qr_auth_module._active_services["test-session-id"] = mock_service

    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/settings/telegram/qr-cancel/test-session-id")

        assert response.status_code == 200
    finally:
        qr_auth_module._active_services.pop("test-session-id", None)


@pytest.mark.asyncio
async def test_logout_public(monkeypatch):
    """POST /api/v1/settings/telegram/logout → 200 без X-API-Key."""
    monkeypatch.setenv("API_KEY", "test-integration-key")
    get_settings.cache_clear()

    from unittest.mock import AsyncMock

    from src.domain.models.auth import TelegramAuth
    from src.domain.value_objects import SessionName
    from main import app

    mock_repo = AsyncMock()
    mock_repo.get = AsyncMock(return_value=TelegramAuth(
        id=1,
        session_name=SessionName("test_session"),
    ))
    mock_repo.clear_session = AsyncMock(return_value=True)
    app.state.telegram_auth_repo = mock_repo

    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/settings/telegram/logout")

        assert response.status_code == 200
    finally:
        app.state.telegram_auth_repo = None


# ======================================================================
# Local Dev Mode (2 теста)
# ======================================================================

@pytest.mark.asyncio
async def test_all_endpoints_public_when_api_key_not_set():
    """Без API_KEY все endpoints доступны — local dev mode."""
    original_key = os.environ.pop("API_KEY", None)
    get_settings.cache_clear()

    try:
        from main import app

        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            sample_protected = [
                ("GET", "/api/v1/settings/overview", None),
                ("GET", "/api/v1/settings/app", None),
                ("GET", "/api/v1/settings/llm", None),
                ("POST", "/api/v1/ask", {"question": "test", "chat_id": 1}),
            ]

            for method, path, body in sample_protected:
                if method == "GET":
                    response = await client.get(path)
                elif method == "POST":
                    response = await client.post(path, json=body) if body else await client.post(path)

                assert response.status_code != 401, (
                    f"Endpoint {method} {path} вернул 401 без API_KEY (local dev mode должен быть открыт)"
                )
    finally:
        if original_key is not None:
            os.environ["API_KEY"] = original_key
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_all_endpoints_public_when_api_key_empty():
    """С API_KEY="" все endpoints доступны — local dev mode."""
    original_key = os.environ.get("API_KEY")
    os.environ["API_KEY"] = ""
    get_settings.cache_clear()

    try:
        from main import app

        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            sample_protected = [
                ("GET", "/api/v1/settings/overview", None),
                ("GET", "/api/v1/settings/app", None),
                ("GET", "/api/v1/settings/llm", None),
                ("POST", "/api/v1/ask", {"question": "test", "chat_id": 1}),
            ]

            for method, path, body in sample_protected:
                if method == "GET":
                    response = await client.get(path)
                elif method == "POST":
                    response = await client.post(path, json=body) if body else await client.post(path)

                assert response.status_code != 401, (
                    f"Endpoint {method} {path} вернул 401 с API_KEY='' (local dev mode должен быть открыт)"
                )
    finally:
        if original_key is not None:
            os.environ["API_KEY"] = original_key
        else:
            os.environ.pop("API_KEY", None)
        get_settings.cache_clear()


# ======================================================================
# Защищённые endpoints (параметризованный тест — 73 endpoints)
# ======================================================================


def _make_request(client: AsyncClient, method: str, path: str, body: dict | None = None) -> Any:
    """Отправить HTTP запрос и вернуть response."""
    if method == "GET":
        return client.get(path)
    if method == "POST":
        return client.post(path, json=body) if body else client.post(path)
    if method == "PUT":
        return client.put(path, json=body) if body else client.put(path)
    if method == "DELETE":
        return client.delete(path)
    if method == "PATCH":
        return client.patch(path, json=body) if body else client.patch(path)
    raise ValueError(f"Неподдерживаемый метод: {method}")


@pytest.mark.parametrize("method,path,body", PROTECTED_ENDPOINTS)
@pytest.mark.asyncio
async def test_endpoint_requires_api_key(method: str, path: str, body: dict | None, monkeypatch):
    """Все защищённые endpoints возвращают 401 AUTH-101 без X-API-Key."""
    monkeypatch.setenv("API_KEY", "test-integration-key")
    get_settings.cache_clear()

    from main import app

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await _make_request(client, method, path, body)

    assert response.status_code == 401
    data = response.json()
    assert data["detail"]["error"]["code"] == "AUTH-101"
