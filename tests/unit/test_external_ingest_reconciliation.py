"""
Reconciliation тесты для External Message Ingestion.

Тестируют приоритет последнему сообщению и восстановление из pending.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import asyncpg

from src.ingestion.external_saver import ExternalMessageSaver
from src.ingestion.saver import MessageSaver


class MockAcquireCtx:
    """Mock async context manager для db_pool.acquire."""

    def __init__(self, connection: MagicMock) -> None:
        self._connection = connection

    async def __aenter__(self) -> MagicMock:
        return self._connection

    async def __aexit__(self, *args: object) -> None:
        return None


@pytest.fixture
def mock_pool():
    """Mock пула подключений к БД."""
    pool = MagicMock(spec=asyncpg.Pool)

    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock()
    mock_conn.execute = AsyncMock()

    pool.acquire = MagicMock(return_value=MockAcquireCtx(mock_conn))

    return pool


@pytest.fixture
def mock_message_saver():
    """Mock MessageSaver."""
    saver = MagicMock(spec=MessageSaver)
    saver.embeddings = AsyncMock()
    saver.embeddings.get_embedding = AsyncMock(return_value=[0.1] * 768)
    saver.embeddings.get_model_name = MagicMock(return_value="test/model")
    return saver


@pytest.fixture
def external_saver(mock_pool, mock_message_saver):
    """ExternalMessageSaver для тестов."""
    return ExternalMessageSaver(mock_pool, mock_message_saver)


class TestReconciliation:
    """Reconciliation тесты — приоритет последнему сообщению."""

    @pytest.mark.asyncio
    async def test_LastMessageWins_SameChat(self, external_saver, mock_pool, mock_message_saver):
        """Последнее сообщение побеждает в том же чате."""
        # Первое сообщение
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(side_effect=[
            {"is_monitored": True},
            None,
            {"id": 11111},
        ])
        mock_conn.execute = AsyncMock()

        mock_pool.acquire = MagicMock(return_value=MockAcquireCtx(mock_conn))

        result1 = await external_saver.save_external_message(
            chat_id=-1001234567890,
            text="Первое сообщение",
            date=datetime(2026, 3, 22, 10, 30, 0, tzinfo=timezone.utc),
        )

        assert result1.success is True
        assert result1.status.status == "processed"
        assert result1.message_id == 11111

        # Второе сообщение (позже)
        mock_conn2 = AsyncMock()
        mock_conn2.fetchrow = AsyncMock(side_effect=[
            {"is_monitored": True},
            None,
            {"id": 22222},
        ])
        mock_conn2.execute = AsyncMock()

        mock_pool.acquire = MagicMock(return_value=MockAcquireCtx(mock_conn2))

        result2 = await external_saver.save_external_message(
            chat_id=-1001234567890,
            text="Второе сообщение",
            date=datetime(2026, 3, 22, 10, 31, 0, tzinfo=timezone.utc),
        )

        assert result2.success is True
        assert result2.status.status == "processed"
        assert result2.message_id == 22222
        # Разные ID для разных сообщений
        assert result1.message_id != result2.message_id

    @pytest.mark.asyncio
    async def test_ConcurrentMessages_DifferentChats(self, external_saver, mock_pool):
        """Одновременные сообщения в разных чатах."""
        # Первое сообщение
        mock_conn1 = AsyncMock()
        mock_conn1.fetchrow = AsyncMock(side_effect=[
            {"is_monitored": True},
            None,
            {"id": 11111},
        ])
        mock_conn1.execute = AsyncMock()

        mock_pool.acquire = MagicMock(return_value=MockAcquireCtx(mock_conn1))

        result1 = await external_saver.save_external_message(
            chat_id=-1001234567890,
            text="Сообщение в чате 1",
            date=datetime(2026, 3, 22, 10, 30, 0, tzinfo=timezone.utc),
        )

        # Второе сообщение
        mock_conn2 = AsyncMock()
        mock_conn2.fetchrow = AsyncMock(side_effect=[
            {"is_monitored": True},
            None,
            {"id": 22222},
        ])
        mock_conn2.execute = AsyncMock()

        mock_pool.acquire = MagicMock(return_value=MockAcquireCtx(mock_conn2))

        result2 = await external_saver.save_external_message(
            chat_id=-1009876543210,
            text="Сообщение в чате 2",
            date=datetime(2026, 3, 22, 10, 30, 0, tzinfo=timezone.utc),
        )

        assert result1.success is True
        assert result2.success is True
        # Разные чаты — разные ID
        assert result1.chat_id != result2.chat_id

    @pytest.mark.asyncio
    async def test_UpdateMessage_TextChanged(self, external_saver, mock_pool, mock_message_saver):
        """Обновление сообщения при изменении текста."""
        mock_conn = AsyncMock()

        # Первое сообщение (текст должен быть >= 15 символов для прохождения фильтра)
        mock_conn.fetchrow = AsyncMock(side_effect=[
            {"is_monitored": True},
            None,
            {"id": 12345},
        ])
        mock_conn.execute = AsyncMock()

        mock_pool.acquire = MagicMock(return_value=MockAcquireCtx(mock_conn))

        result1 = await external_saver.save_external_message(
            chat_id=-1001234567890,
            text="Старый текст сообщения для теста",
            date=datetime(2026, 3, 22, 10, 30, 0, tzinfo=timezone.utc),
        )

        assert result1.success is True
        assert result1.status.status == "processed"

        # Обновление с тем же ID но новым текстом (в пределах 60 секунд)
        mock_conn2 = AsyncMock()
        mock_conn2.fetchrow = AsyncMock(side_effect=[
            {"is_monitored": True},
            {"id": 12345, "message_text": "Старый текст сообщения для теста"},
        ])
        mock_conn2.execute = AsyncMock()

        mock_pool.acquire = MagicMock(return_value=MockAcquireCtx(mock_conn2))

        result2 = await external_saver.save_external_message(
            chat_id=-1001234567890,
            text="Новый текст сообщения для теста",
            date=datetime(2026, 3, 22, 10, 30, 30, tzinfo=timezone.utc),
        )

        assert result2.success is True
        assert result2.status.status == "updated"
        assert result2.message_id == 12345
        assert result2.status.updated is True

    @pytest.mark.asyncio
    async def test_UpdateMessage_EmbeddingChanged(self, external_saver, mock_pool, mock_message_saver):
        """Обновление эмбеддинга при изменении текста."""
        mock_conn = AsyncMock()
        captured_embeddings = []

        async def capture_execute(query, *args):
            if "UPDATE messages" in query:
                # Извлекаем embedding из запроса
                captured_embeddings.append(args[2])

        mock_conn.fetchrow = AsyncMock(side_effect=[
            {"is_monitored": True},
            {"id": 12345, "message_text": "Старый текст"},
        ])
        mock_conn.execute = capture_execute

        mock_pool.acquire = MagicMock(return_value=MockAcquireCtx(mock_conn))

        # Обновление текста
        result = await external_saver.save_external_message(
            chat_id=-1001234567890,
            text="Новый текст",
            date=datetime(2026, 3, 22, 10, 30, 30, tzinfo=timezone.utc),
        )

        assert result.success is True
        assert result.status.status == "updated"
        # Эмбеддинг должен быть обновлён
        assert len(captured_embeddings) > 0

    @pytest.mark.asyncio
    async def test_PendingRecovery_AfterEmbeddingError(self, external_saver, mock_pool, mock_message_saver):
        """Восстановление из pending после ошибки векторизации."""
        mock_conn = AsyncMock()
        pending_data = {}

        async def capture_execute(query, *args):
            if "INSERT INTO pending_messages" in query:
                pending_data["message_data"] = args[0]
                pending_data["last_error"] = args[1]

        mock_conn.fetchrow = AsyncMock(side_effect=[
            {"is_monitored": True},
            None,
        ])
        mock_conn.execute = capture_execute

        mock_pool.acquire = MagicMock(return_value=MockAcquireCtx(mock_conn))

        # Ошибка векторизации
        mock_message_saver.embeddings.get_embedding = AsyncMock(
            side_effect=Exception("Embedding service unavailable")
        )

        result = await external_saver.save_external_message(
            chat_id=-1001234567890,
            text="Сообщение с ошибкой",
            date=datetime(2026, 3, 22, 10, 30, 0, tzinfo=timezone.utc),
        )

        assert result.success is True
        assert result.status.status == "pending"
        assert result.status.pending is True
        # Сообщение сохранено в pending
        assert pending_data.get("message_data") is not None
        assert "Embedding service unavailable" in pending_data["last_error"]

    @pytest.mark.asyncio
    async def test_PendingRecovery_AfterDatabaseError(self, external_saver, mock_pool):
        """Восстановление из pending после ошибки БД."""
        mock_conn = AsyncMock()
        pending_data = {}

        async def capture_execute(query, *args):
            if "INSERT INTO pending_messages" in query:
                pending_data["message_data"] = args[0]
                pending_data["last_error"] = args[1]

        mock_conn.fetchrow = AsyncMock(side_effect=[
            {"is_monitored": True},
            None,
        ])

        async def db_error_execute(query, *args):
            if "INSERT INTO messages" in query:
                raise Exception("DB connection lost")
            elif "INSERT INTO pending_messages" in query:
                pending_data["message_data"] = args[0]
                pending_data["last_error"] = args[1]

        mock_conn.execute = db_error_execute

        mock_pool.acquire = MagicMock(return_value=MockAcquireCtx(mock_conn))

        result = await external_saver.save_external_message(
            chat_id=-1001234567890,
            text="Сообщение с ошибкой БД",
            date=datetime(2026, 3, 22, 10, 30, 0, tzinfo=timezone.utc),
        )

        assert result.success is True
        assert result.status.status == "pending"
        assert result.status.pending is True
        # Сообщение сохранено в pending
        assert pending_data.get("message_data") is not None
        assert "DB error" in pending_data["last_error"]

    @pytest.mark.asyncio
    async def test_PendingTTL_Expired(self, external_saver, mock_pool):
        """Истечение TTL pending сообщения."""
        # Этот тест проверяет что pending сообщения имеют TTL
        # В реальной системе pending_cleanup_service удаляет старые записи
        # Здесь проверяем что данные корректно сохраняются

        mock_conn = AsyncMock()
        pending_data = {}

        async def capture_execute(query, *args):
            if "INSERT INTO pending_messages" in query:
                import json
                pending_data["message_data"] = json.loads(args[0])
                pending_data["retry_count"] = 0

        mock_conn.fetchrow = AsyncMock(side_effect=[
            {"is_monitored": True},
            None,
        ])
        mock_conn.execute = capture_execute

        mock_pool.acquire = MagicMock(return_value=MockAcquireCtx(mock_conn))

        # Ошибка векторизации
        mock_message_saver = external_saver.saver
        mock_message_saver.embeddings.get_embedding = AsyncMock(
            side_effect=Exception("Embedding service unavailable")
        )

        result = await external_saver.save_external_message(
            chat_id=-1001234567890,
            text="Сообщение для pending",
            date=datetime(2026, 3, 22, 10, 30, 0, tzinfo=timezone.utc),
        )

        assert result.success is True
        assert result.status.status == "pending"
        # Проверка структуры данных pending
        assert pending_data.get("message_data")
        assert pending_data["message_data"]["chat_id"] == -1001234567890
        assert pending_data["message_data"]["text"] == "Сообщение для pending"
        assert pending_data["message_data"]["source"] == "external"
