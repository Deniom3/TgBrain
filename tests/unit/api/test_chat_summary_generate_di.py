"""
Unit-тесты эндпоинтов генерации chat summary с мокированными DI зависимостями.

Проверяет:
- Создание задачи summary для одного чата
- Возврат кэшированной задачи
- Обработка ошибок недоступности сервисов
- Fallback на настройки по умолчанию
- Массовая генерация с явными chat_ids
- Массовая генерация через репозиторий
- Пустой список чатов
"""

from typing import Generator, Tuple
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from src.api.dependencies.rate_limiter import summary_rate_limit
from src.api.dependencies.services import (
    get_chat_settings_repo,
    get_summary_usecase,
)
from src.api.endpoints.chat_summary_generate import (
    router as generate_router,
)
from src.api.endpoints.chat_summary_retrieval import (
    router as retrieval_router,
)
from src.api.models import ErrorDetail, ErrorResponse
from src.application.usecases.generate_summary import (
    GenerateSummaryUseCase,
    SummaryTaskResult,
)
from src.application.usecases.result import Failure, Success


@pytest.fixture
def mock_usecase() -> AsyncMock:
    """Мокированный GenerateSummaryUseCase."""
    mock = MagicMock(spec=GenerateSummaryUseCase)
    mock.get_or_create_task = AsyncMock()
    mock.get_enabled_chat_ids = AsyncMock()
    return mock


@pytest.fixture
def app_with_summary_routes(
    test_app,
    mock_chat_settings_repo,
    mock_usecase,
) -> Generator[Tuple[TestClient, MagicMock, MagicMock], None, None]:
    """
    FastAPI приложение с роутами summary и DI overrides.

    Включает роутеры generate/retrieval и настраивает dependency overrides.
    """

    test_app.include_router(generate_router)
    test_app.include_router(retrieval_router)

    test_app.dependency_overrides[get_chat_settings_repo] = lambda: mock_chat_settings_repo
    test_app.dependency_overrides[get_summary_usecase] = lambda: mock_usecase

    async def mock_rate_limit():
        from src.api.dependencies.rate_limiter import AuthenticatedUser
        return AuthenticatedUser(is_authenticated=True)

    test_app.dependency_overrides[summary_rate_limit] = mock_rate_limit

    yield TestClient(test_app), mock_chat_settings_repo, mock_usecase

    test_app.dependency_overrides.clear()


def _make_success_result(
    task_id: int = 1,
    status: str = "pending",
    from_cache: bool = False,
    is_new: bool = True,
    chat_id: int = -1001234567890,
) -> Success:
    return Success(SummaryTaskResult(
        task_id=task_id,
        status=status,
        from_cache=from_cache,
        is_new=is_new,
        chat_id=chat_id,
    ))


def test_generate_chat_summary_success_creates_task(app_with_summary_routes) -> None:
    """
    Arrange: usecase возвращает новую задачу.
    Act: POST /chats/{chat_id}/summary/generate.
    Assert: 200, is_new=True, корректная структура ответа.
    """
    client, _, mock_usecase = app_with_summary_routes
    mock_usecase.get_or_create_task.return_value = _make_success_result(
        task_id=1, status="completed", is_new=True,
    )

    response = client.post(
        "/api/v1/chats/-1001234567890/summary/generate",
        json={"period_minutes": 60},
    )

    assert response.status_code == 200

    data = response.json()
    assert data["task_id"] == 1
    assert data["status"] == "completed"
    assert data["from_cache"] is False
    assert data["chat_id"] == -1001234567890

    mock_usecase.get_or_create_task.assert_called_once()


def test_generate_chat_summary_cached_returns_from_cache(app_with_summary_routes) -> None:
    """
    Arrange: usecase возвращает кэшированную задачу (from_cache=True).
    Act: POST запрос.
    Assert: from_cache=True.
    """
    client, _, mock_usecase = app_with_summary_routes
    mock_usecase.get_or_create_task.return_value = _make_success_result(
        task_id=1, status="completed", from_cache=True, is_new=False,
    )

    response = client.post(
        "/api/v1/chats/-1001234567890/summary/generate",
        json={"period_minutes": 60},
    )

    assert response.status_code == 200

    data = response.json()
    assert data["from_cache"] is True
    assert data["message"] == "Summary получено из кэша"

    mock_usecase.get_or_create_task.assert_called_once()


def test_generate_chat_summary_existing_task(app_with_summary_routes) -> None:
    """
    Arrange: usecase возвращает существующую задачу (is_new=False, from_cache=False).
    Act: POST запрос.
    Assert: is_new=False, from_cache=False, статус processing.
    """
    client, _, mock_usecase = app_with_summary_routes
    mock_usecase.get_or_create_task.return_value = _make_success_result(
        task_id=2, status="processing", from_cache=False, is_new=False,
    )

    response = client.post(
        "/api/v1/chats/-1001234567890/summary/generate",
        json={"period_minutes": 60},
    )

    assert response.status_code == 200

    data = response.json()
    assert data["from_cache"] is False
    assert data["status"] == "processing"
    assert data["message"] == "Задача уже выполняется"

    mock_usecase.get_or_create_task.assert_called_once()


def test_generate_chat_summary_db_pool_not_initialized(app_with_summary_routes, test_app) -> None:
    """
    Arrange: get_summary_usecase переопределён на выброс 503.
    Act: POST запрос.
    Assert: 503 Service Unavailable.
    """
    client, _, _ = app_with_summary_routes

    def raise_503():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-106", message="Database pool not initialized")
            ).model_dump(),
        )

    test_app.dependency_overrides[get_summary_usecase] = raise_503

    try:
        response = client.post(
            "/api/v1/chats/-1001234567890/summary/generate",
            json={"period_minutes": 60},
        )

        assert response.status_code == 503
    finally:
        test_app.dependency_overrides.pop(get_summary_usecase, None)


def test_generate_chat_summary_usecase_not_available(app_with_summary_routes, test_app) -> None:
    """
    Arrange: get_summary_usecase переопределён на выброс 503.
    Act: POST запрос.
    Assert: 503 Service Unavailable.
    """
    client, _, _ = app_with_summary_routes

    def raise_503():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-106", message="GenerateSummaryUseCase не инициализирован")
            ).model_dump(),
        )

    test_app.dependency_overrides[get_summary_usecase] = raise_503

    try:
        response = client.post(
            "/api/v1/chats/-1001234567890/summary/generate",
            json={"period_minutes": 60},
        )

        assert response.status_code == 503
    finally:
        test_app.dependency_overrides.pop(get_summary_usecase, None)


def test_generate_chat_summary_settings_not_found_uses_default(app_with_summary_routes) -> None:
    """
    Arrange: usecase возвращает новую задачу (без period_minutes — fallback).
    Act: POST запрос без period_minutes.
    Assert: задача создана успешно.
    """
    client, _, mock_usecase = app_with_summary_routes
    mock_usecase.get_or_create_task.return_value = _make_success_result(
        task_id=3, status="pending", is_new=True,
    )

    response = client.post(
        "/api/v1/chats/-1001234567890/summary/generate",
        json={},
    )

    assert response.status_code == 200

    data = response.json()
    assert data["task_id"] == 3
    assert data["status"] == "pending"


def test_generate_all_with_explicit_chat_ids(app_with_summary_routes) -> None:
    """
    Arrange: запрос с явными chat_ids, get_enabled_summary_chat_ids не должен вызываться.
    Act: POST /chats/summary/generate с body.chat_ids.
    Assert: get_enabled_summary_chat_ids не вызван, задачи созданы.
    """
    client, _, mock_usecase = app_with_summary_routes
    chat_ids = [-1001111111111, -1002222222222]
    mock_usecase.get_or_create_task.return_value = _make_success_result(
        task_id=3, status="pending", is_new=True,
    )

    response = client.post(
        "/api/v1/chats/summary/generate",
        json={"chat_ids": chat_ids},
    )

    assert response.status_code == 200

    data = response.json()
    assert data["total_chats"] == 2
    assert len(data["tasks"]) == 2
    assert mock_usecase.get_enabled_chat_ids.call_count == 0


def test_generate_all_uses_repo_for_enabled_chats(app_with_summary_routes) -> None:
    """
    Arrange: запрос без chat_ids, usecase возвращает список чатов.
    Act: POST /chats/summary/generate без body.chat_ids.
    Assert: get_enabled_summary_chat_ids вызван, задачи созданы.
    """
    client, _, mock_usecase = app_with_summary_routes
    enabled_chats = [-1001111111111, -1002222222222]
    mock_usecase.get_enabled_chat_ids.return_value = enabled_chats
    mock_usecase.get_or_create_task.return_value = _make_success_result(
        task_id=3, status="pending", is_new=True,
    )

    response = client.post(
        "/api/v1/chats/summary/generate",
        json={},
    )

    assert response.status_code == 200

    data = response.json()
    assert data["total_chats"] == 2
    mock_usecase.get_enabled_chat_ids.assert_called_once()


def test_generate_all_no_chats_returns_400(app_with_summary_routes) -> None:
    """
    Arrange: usecase возвращает пустой список чатов.
    Act: POST /chats/summary/generate.
    Assert: 400 Bad Request.
    """
    client, _, mock_usecase = app_with_summary_routes
    mock_usecase.get_enabled_chat_ids.return_value = []

    response = client.post(
        "/api/v1/chats/summary/generate",
        json={},
    )

    assert response.status_code == 400

    data = response.json()
    assert "Нет чатов для генерации" in data["detail"]["error"]["message"]


def test_generate_all_partial_failures_logged(app_with_summary_routes) -> None:
    """
    Arrange: usecase возвращает success для первого чата, failure для второго.
    Act: POST /chats/summary/generate с двумя chat_ids.
    Assert: первый — "pending", второй — "error", общий статус 200.
    """
    client, _, mock_usecase = app_with_summary_routes
    chat_ids = [-1001111111111, -1002222222222]

    call_count = [0]

    async def side_effect_get_or_create_task(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return _make_success_result(task_id=3, status="pending", is_new=True)
        return Failure(RuntimeError("LLM недоступен"))

    mock_usecase.get_or_create_task = AsyncMock(side_effect=side_effect_get_or_create_task)

    response = client.post(
        "/api/v1/chats/summary/generate",
        json={"chat_ids": chat_ids},
    )

    assert response.status_code == 200

    data = response.json()
    assert data["total_chats"] == 2
    assert len(data["tasks"]) == 2
    assert data["tasks"][0]["status"] == "pending"
    assert data["tasks"][1]["status"] == "error"
