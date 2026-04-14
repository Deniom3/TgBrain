"""
Unit-тесты эндпоинтов получения chat summary с мокированными DI зависимостями.

Проверяет:
- Получение списка summary для чата
- Получение последнего summary
- Статус задачи (completed, pending, processing, failed)
- Удаление summary
- Очистка старых summary
- Статистика по summary
"""

from datetime import datetime, timedelta, timezone
from typing import Generator, Tuple
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.dependencies.services import get_summary_repo
from src.api.endpoints.chat_summary_retrieval import (
    router as retrieval_router,
)
from src.models.data_models import ChatSummary, SummaryStatus


@pytest.fixture
def app_with_retrieval_routes(test_app) -> Generator[Tuple[TestClient, MagicMock], None, None]:
    """
    FastAPI приложение с роутами retrieval и DI overrides.

    mock_repo использует методы *_with_pool, которые инкапсулируют
    управление пулом соединений. Эндпоинты больше не обращаются
    к `_pool.acquire()` напрямую.
    """
    mock_repo = MagicMock()

    test_app.include_router(retrieval_router)
    test_app.dependency_overrides[get_summary_repo] = lambda: mock_repo

    yield TestClient(test_app), mock_repo

    test_app.dependency_overrides.clear()


def _create_task_row(status: str = "completed") -> dict:
    """Создать строку задачи для мока."""
    now = datetime.now(timezone.utc)
    status_map = {
        "completed": SummaryStatus.COMPLETED,
        "pending": SummaryStatus.PENDING,
        "processing": SummaryStatus.PROCESSING,
        "failed": SummaryStatus.FAILED,
    }
    return {
        "id": 1,
        "chat_id": -1001234567890,
        "status": status_map.get(status, SummaryStatus.COMPLETED),
        "created_at": now,
        "updated_at": now,
        "result_text": "Результат" if status == "completed" else "Ошибка" if status == "failed" else "",
        "messages_count": 50 if status == "completed" else 0,
        "period_start": now - timedelta(hours=24),
        "period_end": now,
        "generated_by": "llm",
        "metadata": None,
    }


def test_get_chat_summaries_success(app_with_retrieval_routes) -> None:
    """
    Arrange: мок репозитория возвращает список summary.
    Act: GET /chats/{chat_id}/summary.
    Assert: 200, список SummaryListItem.
    """
    client, mock_repo = app_with_retrieval_routes
    now = datetime.now(timezone.utc)
    mock_row = MagicMock()
    mock_row.id = 1
    mock_row.chat_id = -1001234567890
    mock_row.created_at = now
    mock_row.period_start = now - timedelta(hours=24)
    mock_row.period_end = now
    mock_row.messages_count = 50
    mock_row.generated_by = "llm"
    mock_row.status = SummaryStatus.COMPLETED

    mock_repo.get_summaries_by_chat_with_pool = AsyncMock(return_value=[mock_row])

    response = client.get("/api/v1/chats/-1001234567890/summary")

    assert response.status_code == 200

    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == 1
    assert data[0]["chat_id"] == -1001234567890
    assert data[0]["messages_count"] == 50


def test_get_chat_summaries_empty(app_with_retrieval_routes) -> None:
    """
    Arrange: мок репозитория возвращает пустой список.
    Act: GET /chats/{chat_id}/summary.
    Assert: 200, пустой список [].
    """
    client, mock_repo = app_with_retrieval_routes

    mock_repo.get_summaries_by_chat_with_pool = AsyncMock(return_value=[])

    response = client.get("/api/v1/chats/-1001234567890/summary")

    assert response.status_code == 200

    data = response.json()
    assert data == []


def test_get_latest_summary_success(app_with_retrieval_routes) -> None:
    """
    Arrange: мок репозитория возвращает готовое summary.
    Act: GET /chats/{chat_id}/summary/latest.
    Assert: 200, SummaryDetail с данными.
    """
    client, mock_repo = app_with_retrieval_routes
    now = datetime.now(timezone.utc)
    summary = ChatSummary(
        id=1,
        chat_id=-1001234567890,
        status=SummaryStatus.COMPLETED,
        created_at=now,
        result_text="Текст summary",
        period_start=now - timedelta(hours=24),
        period_end=now,
        messages_count=50,
        generated_by="llm",
        params_hash="hash123",
    )

    mock_repo.get_latest_summary_with_pool = AsyncMock(return_value=summary)

    response = client.get("/api/v1/chats/-1001234567890/summary/latest")

    assert response.status_code == 200

    data = response.json()
    assert data["id"] == 1
    assert data["chat_id"] == -1001234567890
    assert data["result_text"] == "Текст summary"
    assert data["messages_count"] == 50


def test_get_latest_summary_not_found(app_with_retrieval_routes) -> None:
    """
    Arrange: мок репозитория возвращает None.
    Act: GET /chats/{chat_id}/summary/latest.
    Assert: 404 HTTPException.
    """
    client, mock_repo = app_with_retrieval_routes

    mock_repo.get_latest_summary_with_pool = AsyncMock(return_value=None)

    response = client.get("/api/v1/chats/-1001234567890/summary/latest")

    assert response.status_code == 404


def test_get_summary_task_completed(app_with_retrieval_routes) -> None:
    """
    Arrange: мок репозитория возвращает completed задачу.
    Act: GET /chats/{chat_id}/summary/{summary_id}.
    Assert: 200, status=completed, result_text заполнен.
    """
    client, mock_repo = app_with_retrieval_routes
    task_data = _create_task_row("completed")
    task_data["id"] = 1
    task_data["chat_id"] = -1001234567890

    mock_repo.get_summary_task_with_pool = AsyncMock(
        return_value=ChatSummary(**task_data)
    )

    response = client.get("/api/v1/chats/-1001234567890/summary/1")

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "completed"
    assert data["result_text"] == "Результат"


def test_get_summary_task_wrong_chat_id(app_with_retrieval_routes) -> None:
    """
    Arrange: задача принадлежит другому чату.
    Act: GET /chats/{wrong_chat_id}/summary/{summary_id}.
    Assert: 400 HTTPException.
    """
    client, mock_repo = app_with_retrieval_routes
    task_data = _create_task_row("completed")
    task_data["id"] = 1
    task_data["chat_id"] = -1009999999999

    mock_repo.get_summary_task_with_pool = AsyncMock(
        return_value=ChatSummary(**task_data)
    )

    response = client.get("/api/v1/chats/-1001234567890/summary/1")

    assert response.status_code == 400


def test_get_summary_task_not_found(app_with_retrieval_routes) -> None:
    """
    Arrange: мок репозитория возвращает None для задачи.
    Act: GET /chats/{chat_id}/summary/{summary_id}.
    Assert: 404 HTTPException.
    """
    client, mock_repo = app_with_retrieval_routes

    mock_repo.get_summary_task_with_pool = AsyncMock(return_value=None)

    response = client.get("/api/v1/chats/-1001234567890/summary/999")

    assert response.status_code == 404


def test_get_summary_task_pending(app_with_retrieval_routes) -> None:
    """
    Arrange: мок репозитория возвращает pending задачу.
    Act: GET /chats/{chat_id}/summary/{summary_id}.
    Assert: 200, status=pending, progress_percent=0.
    """
    client, mock_repo = app_with_retrieval_routes
    task_data = _create_task_row("pending")
    task_data["id"] = 1
    task_data["chat_id"] = -1001234567890

    mock_repo.get_summary_task_with_pool = AsyncMock(
        return_value=ChatSummary(**task_data)
    )

    response = client.get("/api/v1/chats/-1001234567890/summary/1")

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "pending"
    assert data["progress_percent"] == 0.0


def test_get_summary_task_processing(app_with_retrieval_routes) -> None:
    """
    Arrange: мок репозитория возвращает processing задачу.
    Act: GET /chats/{chat_id}/summary/{summary_id}.
    Assert: 200, status=processing, progress_percent=50.
    """
    client, mock_repo = app_with_retrieval_routes
    task_data = _create_task_row("processing")
    task_data["id"] = 1
    task_data["chat_id"] = -1001234567890

    mock_repo.get_summary_task_with_pool = AsyncMock(
        return_value=ChatSummary(**task_data)
    )

    response = client.get("/api/v1/chats/-1001234567890/summary/1")

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "processing"
    assert data["progress_percent"] == 50.0


def test_get_summary_task_failed(app_with_retrieval_routes) -> None:
    """
    Arrange: мок репозитория возвращает failed задачу.
    Act: GET /chats/{chat_id}/summary/{summary_id}.
    Assert: 200, status=failed, error_message заполнен.
    """
    client, mock_repo = app_with_retrieval_routes
    task_data = _create_task_row("failed")
    task_data["id"] = 1
    task_data["chat_id"] = -1001234567890

    mock_repo.get_summary_task_with_pool = AsyncMock(
        return_value=ChatSummary(**task_data)
    )

    response = client.get("/api/v1/chats/-1001234567890/summary/1")

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "failed"
    assert data["error_message"] == "Ошибка"


def test_delete_summary_success(app_with_retrieval_routes) -> None:
    """
    Arrange: summary существует и принадлежит чату, удаление успешно.
    Act: DELETE /chats/{chat_id}/summary/{summary_id}.
    Assert: 200, "Summary deleted successfully".
    """
    client, mock_repo = app_with_retrieval_routes
    now = datetime.now(timezone.utc)
    summary = ChatSummary(
        id=1,
        chat_id=-1001234567890,
        status=SummaryStatus.COMPLETED,
        created_at=now,
        result_text="Текст",
        period_start=now - timedelta(hours=24),
        period_end=now,
        messages_count=10,
        generated_by="llm",
    )

    mock_repo.get_summary_by_id_with_pool = AsyncMock(return_value=summary)
    mock_repo.delete_summary_by_id_with_pool = AsyncMock(return_value=True)

    response = client.delete("/api/v1/chats/-1001234567890/summary/1")

    assert response.status_code == 200

    data = response.json()
    assert data["message"] == "Summary deleted successfully"


def test_delete_summary_not_found(app_with_retrieval_routes) -> None:
    """
    Arrange: summary не существует.
    Act: DELETE /chats/{chat_id}/summary/{summary_id}.
    Assert: 404 HTTPException.
    """
    client, mock_repo = app_with_retrieval_routes

    mock_repo.get_summary_by_id_with_pool = AsyncMock(return_value=None)

    response = client.delete("/api/v1/chats/-1001234567890/summary/999")

    assert response.status_code == 404


def test_delete_summary_wrong_chat_id(app_with_retrieval_routes) -> None:
    """
    Arrange: summary существует, но принадлежит другому чату.
    Act: DELETE /chats/{wrong_chat_id}/summary/{summary_id}.
    Assert: 400 HTTPException.
    """
    client, mock_repo = app_with_retrieval_routes
    now = datetime.now(timezone.utc)
    summary = ChatSummary(
        id=1,
        chat_id=-1009999999999,
        status=SummaryStatus.COMPLETED,
        created_at=now,
        result_text="Текст",
        period_start=now - timedelta(hours=24),
        period_end=now,
        messages_count=10,
        generated_by="llm",
    )

    mock_repo.get_summary_by_id_with_pool = AsyncMock(return_value=summary)

    response = client.delete("/api/v1/chats/-1001234567890/summary/1")

    assert response.status_code == 400


def test_cleanup_summaries_success(app_with_retrieval_routes) -> None:
    """
    Arrange: мок репозитория возвращает deleted_count=3.
    Act: POST /chats/{chat_id}/summary/cleanup.
    Assert: 200, deleted_count в ответе.
    """
    client, mock_repo = app_with_retrieval_routes

    mock_repo.delete_old_summaries_with_pool = AsyncMock(return_value=3)

    response = client.post(
        "/api/v1/chats/-1001234567890/summary/cleanup",
        json={"older_than_days": 30},
    )

    assert response.status_code == 200

    data = response.json()
    assert data["deleted_count"] == 3
    assert "3 summary" in data["message"]


def test_get_summaries_stats_success(app_with_retrieval_routes) -> None:
    """
    Arrange: мок репозитория возвращает статистику.
    Act: GET /chats/summary/stats.
    Assert: 200, List[SummaryStats].
    """
    client, mock_repo = app_with_retrieval_routes
    now = datetime.now(timezone.utc)
    stats_data = [
        {
            "chat_id": -1001234567890,
            "total_summaries": 5,
            "first_summary": now - timedelta(days=30),
            "last_summary": now,
            "avg_messages": 42,
        }
    ]

    mock_repo.get_stats_with_pool = AsyncMock(return_value=stats_data)

    response = client.get("/api/v1/chats/summary/stats")

    assert response.status_code == 200

    data = response.json()
    assert len(data) == 1
    assert data[0]["chat_id"] == -1001234567890
    assert data[0]["total_summaries"] == 5


def test_get_summaries_stats_empty(app_with_retrieval_routes) -> None:
    """
    Arrange: мок репозитория возвращает пустой список статистики.
    Act: GET /chats/summary/stats.
    Assert: 200, пустой список [].
    """
    client, mock_repo = app_with_retrieval_routes

    mock_repo.get_stats_with_pool = AsyncMock(return_value=[])

    response = client.get("/api/v1/chats/summary/stats")

    assert response.status_code == 200

    data = response.json()
    assert data == []
