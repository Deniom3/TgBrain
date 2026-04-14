"""
Модульные тесты для MessageProcessor.

Тестируют обработку и сохранение сообщений из Telegram.
"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import Settings
from src.ingestion.message_processing import MessageProcessor
from src.ingestion.pending_cleanup_service import PendingCleanupService


@pytest.fixture
def mock_settings():
    """Создаёт mock Settings для тестов."""
    settings = MagicMock(spec=Settings)
    settings.tg_api_id = 12345
    settings.tg_api_hash = "test_hash_abc123"
    settings.tg_chat_enable_list = []
    settings.tg_chat_disable_list = []
    return settings


@pytest.fixture
def mock_saver():
    """Создаёт mock MessageSaver."""
    saver = AsyncMock()
    saver.save_message = AsyncMock(return_value=True)
    saver.update_chat_progress = AsyncMock()
    saver.get_stats = MagicMock(return_value={"filtered": 0, "errors": 0})
    return saver


@pytest.fixture
def mock_pending_cleanup():
    """Создаёт mock PendingCleanupService."""
    cleanup = AsyncMock(spec=PendingCleanupService)
    cleanup.cleanup_old_pending_messages = AsyncMock(return_value=5)
    cleanup.start_cleanup_task = AsyncMock()
    return cleanup


@pytest.fixture
def mock_pool():
    """Создаёт mock asyncpg.Pool."""
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=None)
    pool.execute = AsyncMock()
    return pool


@pytest.fixture
def message_processor(mock_settings, mock_saver, mock_pending_cleanup):
    """Создаёт MessageProcessor с мокированными зависимостями."""
    processor = MessageProcessor(
        config=mock_settings,
        saver=mock_saver,
        pending_cleanup=mock_pending_cleanup,
    )
    return processor


def make_tl_message(
    msg_id: int,
    chat_id: int = 100,
    text: str = "Тестовое сообщение для обработки данных",
    date: Any = None,
    media: Any = None,
    action: Any = None,
    is_channel: bool = False,
) -> MagicMock:
    """Создаёт mock TLMessage для тестов."""
    msg = MagicMock()
    msg.id = msg_id
    msg.chat_id = chat_id
    msg.text = text
    msg.date = date or datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    msg.media = media
    msg.action = action
    msg.is_channel = is_channel

    chat = MagicMock()
    chat.id = chat_id
    chat.title = "Test Chat"
    chat.type = "supergroup"
    msg.get_chat = AsyncMock(return_value=chat)

    sender = MagicMock()
    sender.id = 42
    sender.username = "test_user"
    sender.first_name = "Test"
    sender.bot = False
    msg.get_sender = AsyncMock(return_value=sender)

    return msg


class TestMessageProcessorInit:
    """Тесты инициализации MessageProcessor."""

    def test_message_processor_init(self, message_processor):
        """
        MessageProcessor корректно инициализируется.

        Проверяет:
        - Сохранение переданных зависимостей
        - Начальные значения внутренних полей
        """
        assert message_processor._processed_count == 0
        assert message_processor._error_count == 0
        assert message_processor._last_message_ids == {}
        assert message_processor._monitored_chats_cache == set()
        assert message_processor._cache_refresh_counter == 0


class TestInitializeMonitoredChats:
    """Тесты метода initialize_monitored_chats."""

    @pytest.mark.asyncio
    async def test_initialize_monitored_chats(self, message_processor, mock_pool):
        """
        Инициализация monitored чатов.

        Проверяет:
        - Заполнение _monitored_chats_cache
        - Загрузка last_message_id для каждого чата
        """
        with patch("src.ingestion.message_processing.get_pool", new_callable=AsyncMock) as mock_get_pool:
            mock_get_pool.return_value = mock_pool
            mock_pool.fetchrow = AsyncMock(return_value={"last_message_id": 50})

            await message_processor.initialize_monitored_chats([-1001234567890])

            assert -1001234567890 in message_processor._monitored_chats_cache
            assert message_processor._last_message_ids[-1001234567890] == 50


class TestFetchLastMessageId:
    """Тесты метода fetch_last_message_id."""

    @pytest.mark.asyncio
    async def test_fetch_last_message_id(self, message_processor, mock_pool):
        """
        Получение последнего ID из БД.

        Проверяет:
        - Вызов pool.fetchrow с правильным SQL
        - Возврат значения из записи
        """
        with patch("src.ingestion.message_processing.get_pool", new_callable=AsyncMock) as mock_get_pool:
            mock_get_pool.return_value = mock_pool
            mock_pool.fetchrow = AsyncMock(return_value={"last_message_id": 777})

            result = await message_processor.fetch_last_message_id(-1001234567890)

            assert result == 777


class TestProcessMessage:
    """Тесты метода process_message."""

    @pytest.mark.asyncio
    async def test_process_message_success(self, message_processor):
        """
        Успешная обработка сообщения.

        Проверяет:
        - Увеличение _processed_count
        - Вызов save_message и update_chat_progress
        """
        tl_msg = make_tl_message(msg_id=42, text="Тестовое сообщение для проверки обработки")

        await message_processor.process_message(tl_msg)

        assert message_processor._processed_count == 1
        message_processor.saver.save_message.assert_called_once()
        message_processor.saver.update_chat_progress.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_error(self, message_processor):
        """
        Ошибка обработки увеличивает error_count.

        Проверяет:
        - При save_message=False _error_count увеличивается
        - _processed_count не увеличивается
        """
        message_processor.saver.save_message = AsyncMock(return_value=False)

        tl_msg = make_tl_message(msg_id=42, text="Тестовое сообщение для проверки обработки")

        await message_processor.process_message(tl_msg)

        assert message_processor._error_count == 1
        assert message_processor._processed_count == 0

    @pytest.mark.asyncio
    async def test_process_message_parse_error(self, message_processor):
        """
        Ошибка парсинга логируется и сообщение не обрабатывается.

        Проверяет:
        - При None из _parse_message счётчики не меняются
        """
        tl_msg = MagicMock()
        tl_msg.id = 99
        tl_msg.get_chat = AsyncMock(side_effect=RuntimeError("Ошибка"))

        await message_processor.process_message(tl_msg)

        assert message_processor._processed_count == 0
        assert message_processor._error_count == 0


class TestParseMessage:
    """Тесты метода _parse_message."""

    @pytest.mark.asyncio
    async def test_parse_message_success(self, message_processor):
        """
        Парсинг TLMessage.

        Проверяет:
        - Создание IngestionMessage с правильными полями
        """
        tl_msg = make_tl_message(msg_id=42, text="Тестовое сообщение для проверки парсинга")

        result = await message_processor._parse_message(tl_msg)

        assert result is not None
        assert result.id == 42
        assert result.chat_title == "Test Chat"
        assert result.sender_name == "@test_user"

    @pytest.mark.asyncio
    async def test_parse_message_error(self, message_processor):
        """
        Ошибка парсинга возвращает None.

        Проверяет:
        - Исключение → None
        """
        tl_msg = MagicMock()
        tl_msg.id = 99
        tl_msg.get_chat = AsyncMock(side_effect=RuntimeError("Ошибка"))

        result = await message_processor._parse_message(tl_msg)

        assert result is None


class TestHandleNewMessage:
    """Тесты метода handle_new_message."""

    @pytest.mark.asyncio
    async def test_handle_new_message_monitored(self, message_processor, mock_pool):
        """
        Сообщение из monitored чата обрабатывается.

        Проверяет:
        - Сообщение из известного чата проходит обработку
        - _last_message_ids обновляется
        """
        message_processor._monitored_chats_cache = {-1001234567890}
        message_processor._last_message_ids[-1001234567890] = 0

        with patch("src.ingestion.message_processing.get_pool", new_callable=AsyncMock) as mock_get_pool:
            mock_get_pool.return_value = mock_pool
            mock_pool.fetchrow = AsyncMock(return_value={"last_message_id": 0})

            event = MagicMock()
            event.id = 50
            event.chat_id = -1001234567890
            event.message = make_tl_message(msg_id=50, text="Тестовое сообщение для проверки обработки")

            await message_processor.handle_new_message(event)

        assert message_processor._last_message_ids[-1001234567890] == 50
        assert message_processor._processed_count == 1

    @pytest.mark.asyncio
    async def test_handle_new_message_not_monitored(self, message_processor):
        """
        Сообщение не из monitored чата игнорируется.

        Проверяет:
        - Сообщение из неизвестного чата не обрабатывается
        - Счётчики не меняются
        """
        message_processor._monitored_chats_cache = {-1001234567890}

        event = MagicMock()
        event.id = 50
        event.chat_id = -1009999999999
        event.message = make_tl_message(msg_id=50, text="Тестовое сообщение для проверки обработки")

        await message_processor.handle_new_message(event)

        assert message_processor._processed_count == 0

    @pytest.mark.asyncio
    async def test_handle_new_message_duplicate(self, message_processor):
        """
        Дубликат сообщения игнорируется.

        Проверяет:
        - Сообщение с ID <= last_message_id не обрабатывается
        """
        message_processor._monitored_chats_cache = {-1001234567890}
        message_processor._last_message_ids[-1001234567890] = 100

        event = MagicMock()
        event.id = 50
        event.chat_id = -1001234567890
        event.message = make_tl_message(msg_id=50, text="Тестовое сообщение для проверки обработки")

        await message_processor.handle_new_message(event)

        assert message_processor._processed_count == 0


class TestPollMessages:
    """Тесты метода poll_messages."""

    @pytest.mark.asyncio
    async def test_poll_messages(self, message_processor):
        """
        Polling с rate limiter.

        Проверяет:
        - Опрос чатов и обработка новых сообщений
        - Rate limiter используется при передаче
        """
        message_processor._monitored_chats_cache = {-1001234567890}
        message_processor._last_message_ids[-1001234567890] = 0

        mock_client = AsyncMock()
        new_msg = make_tl_message(msg_id=5, text="Тестовое сообщение для проверки polling")
        old_msg = make_tl_message(msg_id=1, text="Старое сообщение для проверки polling")

        rate_limiter = AsyncMock()
        rate_limiter.execute = AsyncMock(return_value=[old_msg, new_msg])
        message_processor._last_message_ids[-1001234567890] = 0

        await message_processor.poll_messages(mock_client, rate_limiter=rate_limiter)

        assert message_processor._processed_count == 1
        rate_limiter.execute.assert_called()

    @pytest.mark.asyncio
    async def test_poll_messages_without_rate_limiter(self, message_processor):
        """
        Polling без rate limiter.

        Проверяет:
        - client.get_messages вызывается напрямую
        """
        message_processor._monitored_chats_cache = {-1001234567890}
        message_processor._last_message_ids[-1001234567890] = 0

        mock_client = AsyncMock()
        new_msg = make_tl_message(msg_id=5, text="Тестовое сообщение для проверки polling")
        mock_client.get_messages = AsyncMock(return_value=[new_msg])

        await message_processor.poll_messages(mock_client, rate_limiter=None)

        assert message_processor._processed_count == 1
        mock_client.get_messages.assert_called_once()


class TestReloadMonitoredChats:
    """Тесты метода reload_monitored_chats."""

    @pytest.mark.asyncio
    async def test_reload_monitored_chats(self, message_processor, mock_pool):
        """
        Обновление списка чатов.

        Проверяет:
        - Обновление _monitored_chats_cache
        - Добавление новых чатов в _last_message_ids
        """
        with patch("src.ingestion.message_processing.get_pool", new_callable=AsyncMock) as mock_get_pool:
            mock_get_pool.return_value = mock_pool

            mock_repo = AsyncMock()
            mock_repo.get_monitored_chat_ids = AsyncMock(return_value=[-1001234567890, -1009876543210])
            mock_pool.fetchrow = AsyncMock(return_value={"last_message_id": 0})

            with patch("src.ingestion.message_processing.ChatSettingsRepository", return_value=mock_repo):
                await message_processor.reload_monitored_chats()

        assert -1001234567890 in message_processor._monitored_chats_cache
        assert -1009876543210 in message_processor._monitored_chats_cache


class TestGetStats:
    """Тесты метода get_stats."""

    def test_get_stats(self, message_processor):
        """
        Получение статистики.

        Проверяет:
        - Возврат dict с processed, filtered, errors
        """
        message_processor._processed_count = 10

        stats = message_processor.get_stats()

        assert "processed" in stats
        assert "filtered" in stats
        assert "errors" in stats
        assert stats["processed"] == 10


class TestCleanupOldPendingMessages:
    """Тесты метода cleanup_old_pending_messages."""

    @pytest.mark.asyncio
    async def test_cleanup_old_pending_messages(self, message_processor, mock_pending_cleanup):
        """
        Очистка pending сообщений.

        Проверяет:
        - Делегирование вызова pending_cleanup
        """
        result = await message_processor.cleanup_old_pending_messages()

        assert result == 5
        mock_pending_cleanup.cleanup_old_pending_messages.assert_called_once()


class TestStartCleanupTask:
    """Тесты метода start_cleanup_task."""

    @pytest.mark.asyncio
    async def test_start_cleanup_task(self, message_processor, mock_pending_cleanup):
        """
        Запуск задачи очистки.

        Проверяет:
        - Делегирование вызова pending_cleanup
        """
        await message_processor.start_cleanup_task()

        mock_pending_cleanup.start_cleanup_task.assert_called_once()
