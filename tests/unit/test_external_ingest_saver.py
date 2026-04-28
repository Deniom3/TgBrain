"""
Unit тесты для ExternalMessageSaver.

Тестируют бизнес-логику сервиса без интеграции с endpoint.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import asyncpg

from src.ingestion.external_saver import ExternalMessageSaver
from src.ingestion.saver import MessageSaver


@pytest.fixture
def mock_pool():
    """Mock пула подключений к БД."""
    pool = MagicMock(spec=asyncpg.Pool)
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


class TestExternalMessageSaver:
    """Unit тесты для ExternalMessageSaver."""

    @pytest.mark.asyncio
    async def test_SaveMessage_Success(self, external_saver, mock_pool, mock_message_saver):
        """Успешное сохранение сообщения."""
        # Настройка mock connection
        mock_conn = AsyncMock()

        async def mock_fetchrow(query, *args):
            if "is_monitored" in query:
                return {
                    "is_monitored": True,
                    "filter_bots": True,
                    "filter_actions": True,
                    "filter_min_length": 15,
                    "filter_ads": True,
                }
            elif "SELECT id, message_text" in query:
                return None
            elif "INSERT INTO messages" in query:
                return {"id": 12345}
            return None

        async def mock_execute(query, *args):
            return None

        mock_conn.fetchrow = mock_fetchrow
        mock_conn.execute = mock_execute

        class MockAcquireCtx:
            async def __aenter__(self):
                return mock_conn

            async def __aexit__(self, *args):
                return None

        mock_pool.acquire = MagicMock(return_value=MockAcquireCtx())

        # Вызов метода
        result = await external_saver.save_external_message(
            chat_id=-1001234567890,
            text="Тестовое сообщение",
            date=datetime(2026, 3, 22, 10, 30, 0, tzinfo=timezone.utc),
            sender_id=123456,
            sender_name="Test User",
        )

        # Проверки
        assert result.success is True
        assert result.status.status == "processed"
        assert result.message_id == 12345
        assert result.chat_id == -1001234567890
        assert result.status.filtered is False
        assert result.status.pending is False
        assert result.status.duplicate is False
        assert result.status.updated is False

    @pytest.mark.asyncio
    async def test_EnsureChatMonitored_True(self, external_saver, mock_pool):
        """Проверка мониторинга чата — возвращает ChatFilterConfig."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            "is_monitored": True,
            "filter_bots": True,
            "filter_actions": True,
            "filter_min_length": 15,
            "filter_ads": True,
        })
        mock_conn.execute = AsyncMock()

        async def mock_acquire():
            return mock_conn

        mock_pool.acquire = mock_acquire

        from src.domain.models.chat_filter_config import ChatFilterConfig

        result = await external_saver._ensure_chat_monitored(mock_conn, -1001234567890)
        assert isinstance(result, ChatFilterConfig)
        assert result.filter_bots is True

    @pytest.mark.asyncio
    async def test_EnsureChatMonitored_False(self, external_saver, mock_pool):
        """Проверка мониторинга чата — None при is_monitored=False."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            "is_monitored": False,
            "filter_bots": True,
            "filter_actions": True,
            "filter_min_length": 15,
            "filter_ads": True,
        })
        mock_conn.execute = AsyncMock()

        async def mock_acquire():
            return mock_conn

        mock_pool.acquire = mock_acquire

        result = await external_saver._ensure_chat_monitored(mock_conn, -1001234567890)
        assert result is None

    @pytest.mark.asyncio
    async def test_EnsureChatMonitored_NotFound_CreatesChat(self, external_saver, mock_pool):
        """Чат не найден — автоматически создаётся, возвращает ChatFilterConfig с defaults."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.execute = AsyncMock()

        async def mock_acquire():
            return mock_conn

        mock_pool.acquire = mock_acquire

        from src.domain.models.chat_filter_config import ChatFilterConfig

        result = await external_saver._ensure_chat_monitored(mock_conn, -1001234567890)
        assert isinstance(result, ChatFilterConfig)
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_CheckDuplicate_ExactMatch(self, external_saver, mock_pool):
        """Точный дубликат сообщения."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            "id": 12345,
            "message_text": "Тестовое сообщение"
        })

        result = await external_saver._check_duplicate(
            mock_conn,
            -1001234567890,
            "Тестовое сообщение",
            datetime(2026, 3, 22, 10, 30, 0, tzinfo=timezone.utc),
        )

        assert result.is_duplicate is True
        assert result.needs_update is False
        assert result.message_id == 12345

    @pytest.mark.asyncio
    async def test_CheckDuplicate_TextChanged(self, external_saver, mock_pool):
        """Текст изменён — нужно обновление."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            "id": 12345,
            "message_text": "Старый текст"
        })

        result = await external_saver._check_duplicate(
            mock_conn,
            -1001234567890,
            "Новый текст",
            datetime(2026, 3, 22, 10, 30, 0, tzinfo=timezone.utc),
        )

        assert result.is_duplicate is False
        assert result.needs_update is True
        assert result.message_id == 12345

    @pytest.mark.asyncio
    async def test_CheckDuplicate_NoDuplicate(self, external_saver, mock_pool):
        """Нет дубликата."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        result = await external_saver._check_duplicate(
            mock_conn,
            -1001234567890,
            "Тестовое сообщение",
            datetime(2026, 3, 22, 10, 30, 0, tzinfo=timezone.utc),
        )

        assert result.is_duplicate is False
        assert result.needs_update is False
        assert result.message_id is None

    @pytest.mark.asyncio
    async def test_FilterMessage_Advertisement(self, external_saver):
        """Фильтрация рекламы."""
        from src.ingestion.filters import should_process_message

        should_process, reason = should_process_message(
            "🔥 РЕКЛАМА: купи слона! Подписывайтесь на канал!",
            is_bot=False,
            is_action=False,
        )

        assert should_process is False
        assert reason == "advertisement"

    @pytest.mark.asyncio
    async def test_FilterMessage_Short(self, external_saver):
        """Фильтрация короткого сообщения."""
        from src.ingestion.filters import should_process_message

        should_process, reason = should_process_message(
            "Коротко",
            is_bot=False,
            is_action=False,
        )

        assert should_process is False
        assert "short" in reason

    @pytest.mark.asyncio
    async def test_SaveToPending_EmbeddingError(self, external_saver, mock_pool):
        """Сохранение в pending при ошибке векторизации."""
        mock_conn = AsyncMock()
        captured_data = {}

        async def capture_execute(query, *args):
            if "INSERT INTO pending_messages" in query:
                captured_data["message_data"] = args[0]
                captured_data["last_error"] = args[1]

        mock_conn.execute = capture_execute

        await external_saver._save_to_pending(
            conn=mock_conn,
            chat_id=-1001234567890,
            text="Тестовое сообщение",
            date=datetime(2026, 3, 22, 10, 30, 0, tzinfo=timezone.utc),
            sender_id=123456,
            sender_name="Test User",
            message_link=None,
            is_bot=False,
            is_action=False,
            error="Embedding service unavailable",
        )

        # Проверки
        assert captured_data.get("message_data")
        assert captured_data["last_error"] == "Embedding service unavailable"

    @pytest.mark.asyncio
    async def test_SaveToPending_DatabaseError(self, external_saver, mock_pool):
        """Сохранение в pending при ошибке БД."""
        mock_conn = AsyncMock()
        captured_data = {}

        async def capture_execute(query, *args):
            if "INSERT INTO pending_messages" in query:
                captured_data["message_data"] = args[0]
                captured_data["last_error"] = args[1]

        mock_conn.execute = capture_execute

        await external_saver._save_to_pending(
            conn=mock_conn,
            chat_id=-1001234567890,
            text="Тестовое сообщение",
            date=datetime(2026, 3, 22, 10, 30, 0, tzinfo=timezone.utc),
            sender_id=123456,
            sender_name="Test User",
            message_link=None,
            is_bot=False,
            is_action=False,
            error="DB connection lost",
        )

        # Проверки
        assert captured_data.get("message_data")
        assert captured_data["last_error"] == "DB connection lost"

    @pytest.mark.asyncio
    async def test_UpdateMessage_Success(self, external_saver, mock_pool):
        """Обновление сообщения."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        await external_saver._update_message(
            conn=mock_conn,
            message_id=12345,
            text="Новый текст",
            embedding=[0.2] * 768,
        )

        # Проверка что execute был вызван
        assert mock_conn.execute.called

    @pytest.mark.asyncio
    async def test_SanitizeText_LongText(self, external_saver):
        """Санитизация длинного текста."""
        long_text = "A" * 5000
        sanitized = external_saver._sanitize_text(long_text)
        assert len(sanitized) <= 4096

    @pytest.mark.asyncio
    async def test_SanitizeSenderName_XSS(self, external_saver):
        """Санитизация имени отправителя (XSS)."""
        xss_payload = "<script>alert('XSS')</script>"
        sanitized = external_saver._sanitize_sender_name(xss_payload)
        assert "<script>" not in sanitized
        assert "&lt;" in sanitized

    @pytest.mark.asyncio
    async def test_GenerateMessageId_Consistent(self, external_saver):
        """Генерация ID — консистентность."""
        date = datetime(2026, 3, 22, 10, 30, 0, tzinfo=timezone.utc)
        id1 = external_saver._generate_message_id(-1001234567890, "Тест", date)
        id2 = external_saver._generate_message_id(-1001234567890, "Тест", date)
        assert id1 == id2

    @pytest.mark.asyncio
    async def test_GenerateMessageId_Unique(self, external_saver):
        """Генерация ID — уникальность."""
        date = datetime(2026, 3, 22, 10, 30, 0, tzinfo=timezone.utc)
        id1 = external_saver._generate_message_id(-1001234567890, "Тест 1", date)
        id2 = external_saver._generate_message_id(-1001234567890, "Тест 2", date)
        assert id1 != id2
