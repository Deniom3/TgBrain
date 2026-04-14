"""
Общие fixtures и mocks для тестирования TgBrain.

Содержит:
- Настройки (settings, test_db_settings)
- Тестовые данные (sample_message, sample_embedding)
- Mock репозиториев
- MessageRecord фикстуры
- RAG фикстуры
- JSON export фикстуры
- Mock сервисов для Schedule/Webhook тестов
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from src.config import Settings
    from src.models.data_models import MessageRecord
    from src.rag.search import RAGSearch

from unittest.mock import AsyncMock, MagicMock

import pytest

__all__ = [
    "settings",
    "test_db_settings",
    "sample_message",
    "sample_embedding",
    "mock_embedding_repo",
    "sample_message_records",
    "initialized_rag_search",
    "mock_rag_service",
    "create_test_export_file",
    "sample_json_export",
    "large_json_export",
    "mixed_chat_types_json",
    "timezone_naive_json",
    "mock_chat_settings_repo",
    "mock_summary_usecase",
    "mock_webhook_service",
    "mock_summary_repo",
]


@pytest.fixture
def settings() -> "Settings":
    """Загружает настройки из .env файла."""
    from src.config import get_settings

    get_settings.cache_clear()
    return get_settings()


@pytest.fixture
def sample_message() -> dict[str, object]:
    """Пример сообщения для тестов."""
    return {
        "chat_id": -1001234567890,
        "message_id": 12345,
        "text": "Тестовое сообщение для проверки функциональности",
        "sender": "Test User",
        "date": "2024-01-01 12:00:00"
    }


@pytest.fixture
def sample_embedding() -> list[float]:
    """Пример эмбеддинга для тестов."""
    return [0.1] * 768


@pytest.fixture
def mock_embedding_repo() -> MagicMock:
    """Mock embedding repository для unit тестов."""
    mock_repo = MagicMock()
    mock_provider = MagicMock()
    mock_provider.embedding_dim = 768
    mock_provider.name = "ollama"
    mock_provider.model = "nomic-embed-text"
    mock_repo.get_active = AsyncMock(return_value=mock_provider)
    return mock_repo


@pytest.fixture
def sample_message_records() -> list["MessageRecord"]:
    """Пример MessageRecord для тестов."""
    from src.domain.value_objects import ChatTitle, MessageText, SenderName
    from src.models.data_models import MessageRecord

    base_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

    return [
        MessageRecord(
            id=1,
            text=MessageText("Короткое сообщение 1"),
            date=base_time,
            chat_title=ChatTitle("Test Chat"),
            link="https://example.com/test/1",
            sender_name=SenderName("User One"),
            sender_id=100,
            similarity_score=0.95,
        ),
        MessageRecord(
            id=2,
            text=MessageText("Это более длинное сообщение от первого пользователя для тестирования"),
            date=base_time + timedelta(minutes=2),
            chat_title=ChatTitle("Test Chat"),
            link="https://example.com/test/2",
            sender_name=SenderName("User One"),
            sender_id=100,
            similarity_score=0.88,
        ),
        MessageRecord(
            id=3,
            text=MessageText("Сообщение от второго пользователя"),
            date=base_time + timedelta(minutes=3),
            chat_title=ChatTitle("Test Chat"),
            link="https://example.com/test/3",
            sender_name=SenderName("User Two"),
            sender_id=200,
            similarity_score=0.82,
        ),
        MessageRecord(
            id=4,
            text=MessageText("Ещё одно сообщение от первого пользователя"),
            date=base_time + timedelta(minutes=10),
            chat_title=ChatTitle("Test Chat"),
            link="https://example.com/test/4",
            sender_name=SenderName("User One"),
            sender_id=100,
            similarity_score=0.75,
        ),
        MessageRecord(
            id=5,
            text=MessageText("Сообщение от третьего пользователя с очень длинным текстом для проверки работы алгоритмов группировки и расширения контекста"),
            date=base_time + timedelta(minutes=15),
            chat_title=ChatTitle("Test Chat"),
            link="https://example.com/test/5",
            sender_name=SenderName("User Three"),
            sender_id=300,
            similarity_score=0.70,
        ),
    ]


@pytest.fixture
async def initialized_rag_search(
    mock_db_pool: MagicMock,
    settings: "Settings",
    mock_embedding_repo: MagicMock,
) -> "RAGSearch":
    """Fixture для инициализированного RAGSearch."""
    from src.rag.search import RAGSearch

    search = RAGSearch(
        config=settings,
        db_pool=mock_db_pool,
        embedding_repo=mock_embedding_repo,
    )
    await search.expander.initialize()

    return search


@pytest.fixture
def mock_rag_service() -> AsyncMock:
    """Mock RAGService для тестов."""
    rag_service = AsyncMock()
    rag_service.ask = AsyncMock()
    rag_service.check_chat_exists = AsyncMock(return_value=True)
    rag_service.summary = AsyncMock()
    return rag_service


@pytest.fixture
def create_test_export_file(tmp_path: Path) -> Callable[[int, str, int], Path]:
    """Создаёт тестовый JSON export файл."""
    def _create(
        chat_id: int = 1234567890,
        chat_type: str = "private",
        message_count: int = 100,
    ) -> Path:
        export_data = {
            "name": f"Test Chat {chat_id}",
            "type": chat_type,
            "id": chat_id,
            "messages": [
                {
                    "id": i,
                    "type": "message",
                    "date": "2026-03-27T10:00:00",
                    "from": f"User{i}",
                    "from_id": f"user{i}",
                    "text": f"Message text {i}",
                }
                for i in range(1, message_count + 1)
            ]
        }

        file_path = tmp_path / f"export_{chat_id}.json"
        file_path.write_text(json.dumps(export_data, ensure_ascii=False), encoding="utf-8")
        return file_path

    return _create


@pytest.fixture
def sample_json_export(tmp_path: Path) -> Path:
    """Sample JSON export file для integration тестов (100 сообщений)."""
    export_data = {
        "name": "Test Chat Integration",
        "type": "private_channel",
        "id": 1234567890,
        "messages": [
            {
                "id": i,
                "type": "message",
                "date": "2026-03-09T17:53:43",
                "from": "Test User",
                "from_id": "user123456",
                "text": f"Сообщение номер {i} для интеграционного тестирования",
            }
            for i in range(1, 101)
        ]
    }

    file_path = tmp_path / "export_sample.json"
    file_path.write_text(json.dumps(export_data, ensure_ascii=False), encoding="utf-8")
    return file_path


@pytest.fixture
def large_json_export(tmp_path: Path) -> Path:
    """Large JSON export file для integration тестов (10000 сообщений)."""
    export_data = {
        "name": "Large Test Chat",
        "type": "private_channel",
        "id": 9876543210,
        "messages": [
            {
                "id": i,
                "type": "message",
                "date": "2026-03-09T17:53:43",
                "from": "Test User",
                "from_id": "user123456",
                "text": f"Большое сообщение номер {i} для тестирования производительности импорта",
            }
            for i in range(1, 10001)
        ]
    }

    file_path = tmp_path / "export_large.json"
    file_path.write_text(json.dumps(export_data, ensure_ascii=False), encoding="utf-8")
    return file_path


@pytest.fixture
def mixed_chat_types_json(tmp_path: Path) -> Path:
    """JSON export с разными типами чатов для integration тестов."""
    export_data = {
        "name": "Mixed Chat Export",
        "type": "supergroup",
        "id": 1111111111,
        "messages": [
            {
                "id": 1,
                "type": "message",
                "date": "2026-03-09T10:00:00",
                "from": "User1",
                "from_id": "user1",
                "text": "Сообщение из supergroup",
            },
            {
                "id": 2,
                "type": "message",
                "date": "2026-03-09T11:00:00",
                "from": "User2",
                "from_id": "user2",
                "text": "Ещё одно сообщение из supergroup",
            },
        ]
    }

    file_path = tmp_path / "export_mixed.json"
    file_path.write_text(json.dumps(export_data, ensure_ascii=False), encoding="utf-8")
    return file_path


@pytest.fixture
def timezone_naive_json(tmp_path: Path) -> Path:
    """JSON export с датами без timezone для integration тестов."""
    export_data = {
        "name": "Timezone Test Chat",
        "type": "private_channel",
        "id": 2222222222,
        "messages": [
            {
                "id": 1,
                "type": "message",
                "date": "2026-03-09T17:53:43",
                "from": "Test User",
                "from_id": "user123456",
                "text": "Сообщение с naive datetime",
            },
            {
                "id": 2,
                "type": "message",
                "date": "2026-03-09T18:00:00",
                "from": "Test User",
                "from_id": "user123456",
                "text": "Второе сообщение с naive datetime",
            },
        ]
    }

    file_path = tmp_path / "export_timezone.json"
    file_path.write_text(json.dumps(export_data, ensure_ascii=False), encoding="utf-8")
    return file_path


@pytest.fixture
def mock_chat_settings_repo() -> AsyncMock:
    """Mock ChatSettingsRepository."""
    from src.settings.repositories.chat_settings import ChatSettingsRepository

    repo = AsyncMock(spec_set=ChatSettingsRepository)
    return repo


@pytest.fixture
def mock_summary_usecase() -> AsyncMock:
    """Mock GenerateSummaryUseCase."""
    from src.application.usecases.generate_summary import GenerateSummaryUseCase

    usecase = AsyncMock(spec_set=GenerateSummaryUseCase)
    usecase.get_or_create_task = AsyncMock()
    return usecase


@pytest.fixture
def mock_webhook_service() -> AsyncMock:
    """Mock WebhookService."""
    from src.webhook.webhook_service import WebhookService

    service = AsyncMock(spec_set=WebhookService)
    return service


@pytest.fixture
def mock_summary_repo() -> AsyncMock:
    """Mock ChatSummaryRepository."""
    from src.settings.repositories.chat_summary.repository import ChatSummaryRepository

    repo = AsyncMock(spec_set=ChatSummaryRepository)
    return repo


@pytest.fixture
def test_db_settings() -> "Settings":
    """
    Настройки для тестовой БД.

    Требует TEST_DATABASE_URL — не использует production URL.
    """
    from tests.conftest_db import _is_production_url

    from src.config import Settings

    db_url = os.getenv("TEST_DATABASE_URL", "").strip()
    if not db_url:
        raise ValueError("TEST_DATABASE_URL environment variable is required for tests")
    if _is_production_url(db_url):
        raise ValueError("Production database URL is not allowed for tests")

    return Settings(
        db_name="tg_db_test",
        db_url=db_url,
    )
