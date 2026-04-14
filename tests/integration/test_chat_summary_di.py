"""
Integration-тесты DI для chat summary эндпоинтов.

Требуют Docker с PostgreSQL и флага --integration.

Проверяют полный цикл:
- DI → репозиторий → БД
- Реальная генерация задачи summary
- Реальное получение списка summary
"""

from typing import AsyncGenerator, Generator

import asyncpg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies.services import (
    get_chat_settings_repo,
    get_summary_repo,
    get_summary_task_service,
)


@pytest.fixture
async def integration_test_app(real_db_pool: asyncpg.Pool) -> AsyncGenerator[FastAPI, None]:
    """
    FastAPI приложение с реальной БД для integration тестов.

    Включает роутеры chat summary и настраивает DI
    с реальным пулом соединений.
    """
    from src.api.endpoints.chat_summary_generate import (
        router as generate_router,
    )
    from src.api.endpoints.chat_summary_retrieval import (
        router as retrieval_router,
    )
    from src.settings.repositories.chat_settings import ChatSettingsRepository
    from src.settings.repositories.chat_summary.repository import ChatSummaryRepository

    app = FastAPI(title="Test", description="Integration test")

    app.state.db_pool = real_db_pool

    chat_settings_repo = ChatSettingsRepository(real_db_pool)
    summary_repo = ChatSummaryRepository(real_db_pool)

    app.include_router(generate_router)
    app.include_router(retrieval_router)

    app.dependency_overrides[get_chat_settings_repo] = lambda: chat_settings_repo
    app.dependency_overrides[get_summary_repo] = lambda: summary_repo

    async def raise_503():
        from fastapi import HTTPException, status

        from src.api.models import ErrorDetail, ErrorResponse
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-106", message="SummaryTaskService не инициализирован")
            ).model_dump(),
        )

    app.dependency_overrides[get_summary_task_service] = raise_503

    try:
        yield app
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def integration_client(integration_test_app: FastAPI) -> Generator[TestClient, None, None]:
    """TestClient для integration тестов."""
    with TestClient(integration_test_app) as client:
        yield client


@pytest.fixture
async def clean_test_chat(real_db_pool: asyncpg.Pool) -> AsyncGenerator[int, None]:
    """Создать и очистить тестовый чат."""
    chat_id = -1009876543210

    async with real_db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO chat_settings (chat_id, title, type, summary_enabled) VALUES ($1, $2, $3, $4) ON CONFLICT (chat_id) DO NOTHING",
            chat_id, "Integration Test Chat", "private", True,
        )
        await conn.execute(
            "DELETE FROM chat_summaries WHERE chat_id = $1",
            chat_id,
        )

    yield chat_id

    async with real_db_pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM chat_summaries WHERE chat_id = $1",
            chat_id,
        )
        await conn.execute(
            "DELETE FROM chat_settings WHERE chat_id = $1",
            chat_id,
        )


@pytest.mark.integration
def test_generate_chat_summary_integration(integration_client: TestClient, clean_test_chat: int, integration_test_app: FastAPI) -> None:
    """
    Arrange: тестовый чат существует в БД, task_service недоступен.
    Act: POST /chats/{chat_id}/summary/generate.
    Assert: 503 (task_service не инициализирован), но DI pipeline работает.
    """
    response = integration_client.post(
        f"/api/v1/chats/{clean_test_chat}/summary/generate",
        json={"period_minutes": 60},
    )

    assert response.status_code == 503


@pytest.mark.integration
def test_get_chat_summaries_integration(integration_client: TestClient, clean_test_chat: int) -> None:
    """
    Arrange: тестовый чат существует, но summary ещё нет.
    Act: GET /chats/{chat_id}/summary.
    Assert: 200, пустой список.
    """
    response = integration_client.get(f"/api/v1/chats/{clean_test_chat}/summary")

    assert response.status_code == 200

    data = response.json()
    assert data == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_enabled_summary_chat_ids_integration(integration_test_app: FastAPI, clean_test_chat: int) -> None:
    """
    Arrange: тестовый чат с summary_enabled=TRUE существует в БД.
    Act: Вызов репозитория напрямую через async test (без asyncio.get_event_loop()).
    Assert: chat_id присутствует в результате.
    """
    from src.settings.repositories.chat_settings import ChatSettingsRepository

    repo = ChatSettingsRepository(integration_test_app.state.db_pool)
    result = await repo.get_enabled_summary_chat_ids()

    assert clean_test_chat in result


@pytest.mark.integration
def test_generate_chat_summary_with_mocked_task_service(
    real_db_pool: asyncpg.Pool,
    clean_test_chat: int,
) -> None:
    """
    Integration тест создания задачи summary с реальным репозиторием
    и мокированным SummaryTaskService (не 503).

    Проверяет:
    - Реальный ChatSettingsRepository читает настройки из БД
    - Endpoint корректно обрабатывает ответ от task_service
    - Задача создаётся и возвращается корректный response

    Примечание: SummaryTaskService требует сложный граф зависимостей
    (LLMClient, EmbeddingsClient, RAGService, Ollama), который невозможен
    в чистом integration тесте без полного Docker-окружения с Ollama.
    Поэтому task_service мокируется, но ChatSettingsRepository и БД — реальные.
    """
    from datetime import datetime, timedelta, timezone
    from unittest.mock import AsyncMock

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.api.endpoints.chat_summary_generate import (
        router as generate_router,
    )
    from src.api.endpoints.chat_summary_retrieval import (
        router as retrieval_router,
    )
    from src.api.dependencies.rate_limiter import summary_rate_limit
    from src.models.data_models import ChatSummary, SummaryStatus
    from src.settings.repositories.chat_settings import ChatSettingsRepository
    from src.settings.repositories.chat_summary.repository import ChatSummaryRepository

    app = FastAPI(title="Test", description="Integration test with task service")
    app.state.db_pool = real_db_pool

    chat_settings_repo = ChatSettingsRepository(real_db_pool)
    summary_repo = ChatSummaryRepository(real_db_pool)

    mock_task_service = AsyncMock()
    now = datetime.now(timezone.utc)
    mock_task = ChatSummary(
        id=999,
        chat_id=clean_test_chat,
        status=SummaryStatus.PENDING,
        created_at=now,
        result_text="",
        period_start=now - timedelta(hours=1),
        period_end=now,
        messages_count=0,
        generated_by="test",
        params_hash="test_hash",
    )
    mock_task_service.get_or_create_task = AsyncMock(return_value=(mock_task, True))

    app.include_router(generate_router)
    app.include_router(retrieval_router)

    app.dependency_overrides[get_chat_settings_repo] = lambda: chat_settings_repo
    app.dependency_overrides[get_summary_repo] = lambda: summary_repo
    app.dependency_overrides[get_summary_task_service] = lambda: mock_task_service

    async def mock_rate_limit():
        from src.api.dependencies.rate_limiter import AuthenticatedUser
        return AuthenticatedUser(is_authenticated=True)

    app.dependency_overrides[summary_rate_limit] = mock_rate_limit

    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/chats/{clean_test_chat}/summary/generate",
                json={"period_minutes": 60},
            )

            assert response.status_code == 200

            data = response.json()
            assert data["task_id"] == 999
            assert data["status"] == "pending"
            assert data["chat_id"] == clean_test_chat
            assert data["from_cache"] is False

            mock_task_service.get_or_create_task.assert_called_once()
    finally:
        app.dependency_overrides.clear()
