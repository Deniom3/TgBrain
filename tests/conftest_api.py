"""
API fixtures для тестирования TgBrain.

Содержит фикстуры для тестирования API endpoints:
- FastAPI приложение с mock зависимостями
- TestClient для HTTP запросов
- Integration client с реальной БД
"""

from __future__ import annotations

import datetime as _dt
import os
from datetime import timezone
from typing import AsyncGenerator, Awaitable, Callable, Generator, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from httpx import AsyncClient

__all__ = [
    "test_app",
    "test_client",
    "app",
    "integration_import_client",
]


# ---------------------------------------------------------------------------
# Helpers — создание моков и конфигурация приложения
# ---------------------------------------------------------------------------

def _create_mock_connection() -> MagicMock:
    """Создаёт мок asyncpg connection с базовыми методами."""
    mock_connection = MagicMock()

    async def mock_fetchrow(query: str, *args: object) -> dict | None:
        if "is_monitored" in query:
            return {"is_monitored": True}
        return None

    async def mock_execute(*args: object, **kwargs: object) -> None:
        return None

    mock_connection.fetchrow = mock_fetchrow
    mock_connection.execute = mock_execute
    mock_connection.fetch = AsyncMock(return_value=[])

    return mock_connection


def _create_mock_pool_with_connection(mock_connection: MagicMock) -> MagicMock:
    """Оборачивает мок connection в мок pool с acquire контекстом."""
    from tests.conftest_db import _create_mock_pool

    mock_pool = _create_mock_pool()

    class MockAcquireContext:
        async def __aenter__(self) -> MagicMock:
            return mock_connection

        async def __aexit__(self, *args: object) -> None:
            return None

    mock_pool.acquire = MagicMock(return_value=MockAcquireContext())
    return mock_pool


def _create_mock_rate_limiter() -> object:
    """Создаёт мок rate limiter для тестов."""

    class MockRateLimiter:
        def __init__(self) -> None:
            self.call_counts: dict[str, int] = {}
            self.limit = 100

        async def execute(
            self,
            priority: object,
            func: Callable[..., object],
            *args: object,
            **kwargs: object,
        ) -> object:
            key = str(priority)
            self.call_counts[key] = self.call_counts.get(key, 0) + 1
            result = func(*args, **kwargs)
            if hasattr(result, "__await__"):
                return await cast(Awaitable[object], result)
            return result

        async def check_rate_limit(self, key: str, priority: object = None) -> bool:
            return True

    return MockRateLimiter()


def _configure_app_state(app: FastAPI, mock_limiter: object) -> None:
    """Настраивает все мок-объекты в app.state."""
    mock_connection = _create_mock_connection()
    mock_pool = _create_mock_pool_with_connection(mock_connection)
    app.state.db_pool = mock_pool

    mock_embeddings = MagicMock()
    mock_embeddings.get_embedding = AsyncMock(return_value=[0.1] * 768)
    app.state.embeddings = mock_embeddings

    mock_rag = MagicMock()
    mock_rag.ask = AsyncMock()
    mock_rag.check_chat_exists = AsyncMock(return_value=True)
    app.state.rag = mock_rag

    mock_ask_usecase = MagicMock()
    app.state.ask_usecase = mock_ask_usecase

    app.state.rate_limiter = mock_limiter

    mock_message_saver = MagicMock()
    mock_message_saver.embeddings = mock_embeddings
    app.state.message_saver = mock_message_saver

    from src.settings.repositories.telegram_auth import TelegramAuthRepository

    mock_telegram_auth_repo = AsyncMock(spec=TelegramAuthRepository)
    mock_telegram_auth_repo.is_session_active = AsyncMock(return_value=True)
    mock_telegram_auth_repo.get = AsyncMock(return_value=None)
    app.state.telegram_auth_repo = mock_telegram_auth_repo


def _configure_app_routes(app: FastAPI, mock_limiter: object) -> None:
    """Регистрирует роуты и dependency_overrides."""
    from src.api.endpoints import ask, external_ingest
    from src.api.dependencies import get_current_user
    from src.api.dependencies.auth import AuthenticatedUser

    app.include_router(ask.router, prefix="/api/v1")
    app.include_router(external_ingest.router)

    async def _override_get_current_user() -> AuthenticatedUser:
        return AuthenticatedUser(is_authenticated=True)

    async def _override_get_rate_limiter() -> object:
        return mock_limiter

    app.dependency_overrides[get_current_user] = _override_get_current_user
    app.dependency_overrides[external_ingest.get_rate_limiter] = _override_get_rate_limiter


def _configure_app_middleware(app: FastAPI) -> None:
    """Добавляет CORS middleware и обработчики ошибок."""
    from src.domain.exceptions import ValidationError

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": "APP-102",
                    "message": f"Validation error: {exc.message}",
                    "field": exc.field,
                }
            },
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization"],
    )


def _configure_app_health_routes(app: FastAPI) -> None:
    """Регистрирует root и health эндпоинты для тестов."""

    @app.get("/", tags=["Root"])
    async def root() -> dict[str, str]:
        return {
            "name": "TgBrain API",
            "version": "1.0.0",
            "description": "REST API для поиска и суммаризации сообщений из Telegram-чатов",
            "docs": "/docs",
            "health": "/health"
        }

    @app.get("/health", tags=["Health"])
    async def health(check_components: bool = True) -> dict[str, object]:
        response: dict[str, object] = {
            "status": "ok",
            "components": {
                "database": "ok",
                "ollama_embeddings": "ok",
                "llm": "ok",
                "telegram": "ok"
            },
            "timestamp": _dt.datetime.now(timezone.utc).isoformat()
        }
        if not check_components:
            del response["components"]
        return response


# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------

@pytest.fixture
def test_app() -> Generator[FastAPI, None, None]:
    """
    Test FastAPI приложение с mock зависимостями (без lifespan).

    Создаёт новое приложение без lifespan для изоляции тестов от БД.
    Собирает приложение из готовых компонентов: middleware, роуты, моки.
    """
    app = FastAPI(
        title="TgBrain Test",
        description="Test API",
        version="1.0.0"
    )

    mock_limiter = _create_mock_rate_limiter()

    _configure_app_middleware(app)
    _configure_app_state(app, mock_limiter)
    _configure_app_health_routes(app)
    _configure_app_routes(app, mock_limiter)

    try:
        yield app
    finally:
        from src.api.endpoints import external_ingest
        from src.api.dependencies import get_current_user

        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(external_ingest.get_rate_limiter, None)


@pytest.fixture
def test_client(test_app: FastAPI) -> Generator[TestClient, None, None]:
    """
    Test client для HTTP запросов к FastAPI приложению.

    Использует TestClient для прямого вызова без сети.
    Используется в integration тестах API endpoints.

    Example:
        def test_ask(test_client: TestClient, test_app: FastAPI) -> None:
            test_app.state.rag.ask = AsyncMock(...)
            response = test_client.post("/api/v1/ask", json={...})
    """
    with TestClient(test_app) as client:
        yield client


@pytest.fixture
def app(test_app: FastAPI) -> FastAPI:
    """
    Алиас для test_app.

    Используется когда нужно настроить mock'и
    перед вызовом API (например test_app.state.rag.ask = AsyncMock(...)).
    Эквивалентен test_app — существует для обратной совместимости с существующими тестами.
    """
    return test_app


@pytest.fixture
async def integration_import_client() -> AsyncGenerator[AsyncClient, None]:
    """
    HTTP client для integration тестов с реальной БД.

    Требует RUN_INTEGRATION_TESTS=true и Docker containers.
    Подключается напрямую к TEST_DATABASE_URL, минуя .env.
    """
    import asyncpg
    from httpx import ASGITransport

    from tests.conftest_db import _is_production_url

    if os.getenv("RUN_INTEGRATION_TESTS", "false").lower() != "true":
        raise ValueError("Integration tests disabled. Set RUN_INTEGRATION_TESTS=true to enable.")

    test_db_url = os.getenv("TEST_DATABASE_URL", "").strip()
    if not test_db_url:
        raise ValueError("TEST_DATABASE_URL environment variable is required for integration tests")

    if _is_production_url(test_db_url):
        raise ValueError("Production database URL is not allowed for tests")

    app = FastAPI(
        title="TgBrain Test",
        description="Test API",
    )

    test_pool = await asyncpg.create_pool(dsn=test_db_url)
    app.state.db_pool = test_pool

    from src.api.endpoints.import_endpoint import router as import_router
    app.include_router(import_router)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        await test_pool.close()
