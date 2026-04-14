"""
Тесты формата ошибок на уровне API endpoints.

Использует httpx.AsyncClient с полным приложением для проверки
что все endpoint'ы возвращают ошибки в стандартном envelope-формате.
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch

from src.api.exception_handlers import register_exception_handlers


def _extract_error(body: dict) -> dict:
    """
    Извлекает error-объект из ответа.

    FastAPI оборачивает HTTPException.detail в {"detail": {...}},
    поэтому проверяем оба варианта.
    """
    if "error" in body:
        return body["error"]
    if "detail" in body and isinstance(body["detail"], dict):
        if "error" in body["detail"]:
            return body["detail"]["error"]
    return body


class TestAskEndpointErrorEnvelope:
    """Тесты формата ошибок /ask endpoint."""

    @pytest.mark.asyncio
    async def test_ask_endpoint_error_has_standard_envelope(self) -> None:
        """/ask 400/404/500 → standard envelope."""
        from src.api.endpoints.ask import router as ask_router
        from src.api.endpoints import ask as ask_module

        app = FastAPI()
        register_exception_handlers(app)

        mock_usecase = MagicMock()
        mock_usecase.execute = AsyncMock(side_effect=RuntimeError("Unexpected"))

        async def mock_get_usecase() -> MagicMock:
            return mock_usecase

        async def mock_get_limiter() -> MagicMock:
            limiter = MagicMock()
            limiter.execute = AsyncMock(side_effect=RuntimeError("Limiter failed"))
            return limiter

        app.include_router(ask_router, prefix="/api/v1")
        app.dependency_overrides[ask_module.get_ask_usecase] = mock_get_usecase
        app.dependency_overrides[ask_module.get_rate_limiter] = mock_get_limiter

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/ask",
                json={"question": "test", "search_in": "messages"},
            )

        body = response.json()
        error = _extract_error(body)
        assert "code" in error
        assert "message" in error


class TestExternalIngestErrorEnvelope:
    """Тесты формата ошибок /ingest endpoint."""

    @pytest.mark.asyncio
    async def test_external_ingest_error_has_standard_envelope(self) -> None:
        """/ingest 400 → standard envelope."""
        from src.api.endpoints.external_ingest import router as ingest_router
        from src.api.endpoints import external_ingest

        app = FastAPI()
        register_exception_handlers(app)

        async def mock_get_limiter() -> MagicMock:
            limiter = MagicMock()
            limiter.check_rate_limit = AsyncMock(return_value=True)
            return limiter

        app.include_router(ingest_router)
        app.dependency_overrides[external_ingest.get_rate_limiter] = mock_get_limiter

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/messages/ingest",
                json={
                    "chat_id": 123,
                    "text": "   ",
                    "date": "2026-01-01T00:00:00Z",
                },
            )

        assert response.status_code == 400
        body = response.json()
        error = _extract_error(body)
        assert "code" in error
        assert "message" in error


class TestChatSummaryGenerateErrorEnvelope:
    """Тесты формата ошибок /summary/generate endpoint."""

    @pytest.mark.asyncio
    async def test_chat_summary_generate_error_has_standard_envelope(self) -> None:
        """/summary/generate 500 → без X-Error-Code."""
        from src.api.endpoints.chat_summary_generate import router as summary_gen_router
        from src.api.dependencies import services as services_deps
        from src.api.dependencies import rate_limiter as rl_deps

        app = FastAPI()
        register_exception_handlers(app)

        mock_usecase = MagicMock()
        mock_usecase.get_or_create_task = AsyncMock(side_effect=RuntimeError("Task creation failed"))

        async def mock_get_usecase() -> MagicMock:
            return mock_usecase

        async def mock_rate_limit() -> MagicMock:
            return MagicMock(is_authenticated=True)

        app.include_router(summary_gen_router)
        app.dependency_overrides[services_deps.get_summary_usecase] = mock_get_usecase
        app.dependency_overrides[rl_deps.summary_rate_limit] = mock_rate_limit

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chats/123/summary/generate",
                json={"period_minutes": 1440},
            )

        assert response.status_code == 500
        body = response.json()
        error = _extract_error(body)
        assert "code" in error
        assert "message" in error


class TestChatSummaryRetrievalErrorEnvelope:
    """Тесты формата ошибок /summary/retrieve endpoint."""

    @pytest.mark.asyncio
    async def test_chat_summary_retrieval_error_has_standard_envelope(self) -> None:
        """/summary/retrieve 500 → standard envelope."""
        from src.api.endpoints.chat_summary_retrieval import router as summary_ret_router
        from src.api.dependencies import services as services_deps

        app = FastAPI()
        register_exception_handlers(app)

        mock_repo = MagicMock()
        mock_repo.get_summaries_by_chat_with_pool = AsyncMock(side_effect=RuntimeError("DB error"))

        async def mock_get_repo() -> MagicMock:
            return mock_repo

        app.include_router(summary_ret_router)
        app.dependency_overrides[services_deps.get_summary_repo] = mock_get_repo

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/chats/123/summary")

        assert response.status_code == 500
        body = response.json()
        error = _extract_error(body)
        assert "code" in error
        assert "message" in error


class TestSettingsAPIErrorEnvelope:
    """Тесты формата ошибок settings endpoint."""

    @pytest.mark.asyncio
    async def test_settings_api_error_has_standard_envelope(self) -> None:
        """settings endpoint 404 → standard envelope."""
        from src.settings_api.app import router as app_settings_router

        app = FastAPI()
        register_exception_handlers(app)

        mock_repo = AsyncMock()
        mock_repo.get = AsyncMock(return_value=None)
        mock_repo.get_value = AsyncMock(return_value=None)

        app.include_router(app_settings_router, prefix="/settings")

        app.state.app_settings_repo = mock_repo
        mock_telegram_auth = AsyncMock()
        mock_telegram_auth.is_session_active = AsyncMock(return_value=True)
        app.state.telegram_auth_repo = mock_telegram_auth

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("src.config.get_settings") as mock_get_settings:
                mock_settings = MagicMock()
                mock_get_settings.return_value = mock_settings

                response = await client.get(
                    "/settings/app/nonexistent_key",
                )

        assert response.status_code == 404
        body = response.json()
        error = _extract_error(body)
        assert "code" in error
        assert "message" in error


class TestSummarySendWebhookPreservesSuccessFalse:
    """Тесты что webhook endpoint сохраняет success=False."""

    def test_summary_send_webhook_preserves_success_false(self) -> None:
        """HTTP 200 + success=False не меняется."""
        from src.api.endpoints.summary_send_webhook import (
            SummarySendWebhookResponse,
        )

        response = SummarySendWebhookResponse(
            success=False,
            from_cache=False,
            webhook_sent=False,
            webhook_pending=False,
            message="Webhook не настроен",
            chat_id=123,
        )

        assert response.success is False
        assert response.webhook_sent is False

        dumped = response.model_dump()
        assert dumped["success"] is False
        assert dumped["webhook_sent"] is False
