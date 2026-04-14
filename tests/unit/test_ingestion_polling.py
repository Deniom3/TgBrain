"""
Модульные тесты для PollingService.

Тестируют polling логику для опроса чатов Telegram.
"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import Settings
from src.ingestion.polling import PollingService


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
def mock_client():
    """Создаёт mock TelegramClient."""
    client = AsyncMock()
    client.get_messages = AsyncMock(return_value=[])
    return client


@pytest.fixture
def mock_pool():
    """Создаёт mock asyncpg.Pool."""
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=None)
    pool.execute = AsyncMock()
    return pool


@pytest.fixture
def mock_saver():
    """Создаёт mock MessageSaver."""
    saver = AsyncMock()
    saver.save_message = AsyncMock(return_value=True)
    saver.update_chat_progress = AsyncMock()
    saver.get_stats = MagicMock(return_value={"filtered": 0, "errors": 0})
    return saver


@pytest.fixture
def polling_service(mock_client, mock_settings, mock_saver, mock_pool):
    """Создаёт PollingService с мокированными зависимостями."""
    service = PollingService(
        client=mock_client,
        config=mock_settings,
        saver=mock_saver,
        pool=mock_pool,
    )
    return service


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


class TestPollingServiceInit:
    """Тесты инициализации PollingService."""

    def test_polling_service_init(self, polling_service):
        """
        PollingService корректно инициализируется.

        Проверяет:
        - Сохранение переданных зависимостей
        - Начальные значения внутренних полей
        """
        assert polling_service._running is False
        assert polling_service._last_message_ids == {}
        assert polling_service.processed_count == 0
        assert polling_service._monitored_chat_ids == []


class TestPollingServiceStartStop:
    """Тесты start/stop методов."""

    def test_polling_service_start(self, polling_service):
        """
        start() устанавливает флаг _running.

        Проверяет:
        - _running становится True после вызова start()
        """
        polling_service.start()
        assert polling_service._running is True

    def test_polling_service_stop(self, polling_service):
        """
        stop() сбрасывает флаг _running.

        Проверяет:
        - _running становится False после вызова stop()
        """
        polling_service.start()
        polling_service.stop()
        assert polling_service._running is False


class TestPollingLoop:
    """Тесты polling цикла."""

    @pytest.mark.asyncio
    async def test_polling_loop_error_handling(self, polling_service):
        """
        Ошибка в polling цикле не ломает цикл.

        Проверяет:
        - Исключение в poll_messages логируется
        - Цикл продолжает работу после ошибки
        - asyncio.sleep вызывается между итерациями
        """
        polling_service.start()
        poll_call_count = 0

        async def failing_poll():
            nonlocal poll_call_count
            poll_call_count += 1
            if poll_call_count == 1:
                raise RuntimeError("Ошибка опроса")
            polling_service.stop()

        polling_service.poll_messages = AsyncMock(side_effect=failing_poll)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await polling_service.polling_loop()

        assert poll_call_count == 2
        mock_sleep.assert_called()


class TestPollMessages:
    """Тесты метода poll_messages."""

    @pytest.mark.asyncio
    async def test_poll_messages_chat_error(self, polling_service):
        """
        Ошибка опроса чата не ломает цикл.

        Проверяет:
        - Исключение при get_messages логируется
        - Обработка продолжается для других чатов
        """
        polling_service._monitored_chat_ids = [-1001234567890]
        polling_service._last_message_ids[-1001234567890] = 0

        with patch.object(
            PollingService,
            "_get_monitored_chat_ids",
            new=AsyncMock(return_value=[-1001234567890]),
        ):
            polling_service.client.get_messages = AsyncMock(side_effect=RuntimeError("Ошибка сети"))

            await polling_service.poll_messages()

        assert polling_service._last_message_ids[-1001234567890] == 0


class TestParseMessage:
    """Тесты метода _parse_message."""

    @pytest.mark.asyncio
    async def test_parse_message_success(self, polling_service):
        """
        Успешный парсинг TLMessage.

        Проверяет:
        - Создание IngestionMessage с правильными полями
        """
        tl_msg = make_tl_message(msg_id=42, text="Тестовое сообщение для проверки парсинга")

        result = await polling_service._parse_message(tl_msg)

        assert result is not None
        assert result.id == 42
        assert result.chat_id == 100
        assert result.chat_title == "Test Chat"
        assert result.chat_type == "supergroup"
        assert result.sender_id == 42
        assert result.sender_name == "@test_user"
        assert result.text == "Тестовое сообщение для проверки парсинга"
        assert result.is_bot is False
        assert result.is_action is False

    @pytest.mark.asyncio
    async def test_parse_message_error(self, polling_service):
        """
        Ошибка парсинга возвращает None.

        Проверяет:
        - Исключение в _parse_message → None
        """
        tl_msg = MagicMock()
        tl_msg.id = 99
        tl_msg.get_chat = AsyncMock(side_effect=RuntimeError("Ошибка получения чата"))

        result = await polling_service._parse_message(tl_msg)

        assert result is None


class TestFetchLastMessageId:
    """Тесты метода fetch_last_message_id."""

    @pytest.mark.asyncio
    async def test_fetch_last_message_id_found(self, polling_service, mock_pool):
        """
        ID найден в БД.

        Проверяет:
        - Возвращает last_message_id из записи
        """
        mock_pool.fetchrow = AsyncMock(return_value={"last_message_id": 12345})

        result = await polling_service.fetch_last_message_id(-1001234567890)

        assert result == 12345
        mock_pool.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_last_message_id_not_found(self, polling_service, mock_pool):
        """
        ID не найден в БД.

        Проверяет:
        - Возвращает 0 если запись отсутствует
        """
        mock_pool.fetchrow = AsyncMock(return_value=None)

        result = await polling_service.fetch_last_message_id(-1001234567890)

        assert result == 0


class TestProcessMessage:
    """Тесты метода _process_message."""

    @pytest.mark.asyncio
    async def test_process_message_success(self, polling_service):
        """
        Успешная обработка сообщения.

        Проверяет:
        - Увеличение processed_count
        - Вызов save_message и update_chat_progress
        """
        tl_msg = make_tl_message(msg_id=42, text="Тестовое сообщение для проверки обработки")

        await polling_service._process_message(tl_msg)

        assert polling_service.processed_count == 1
        polling_service.saver.save_message.assert_called_once()
        polling_service.saver.update_chat_progress.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_parse_error(self, polling_service):
        """
        Ошибка парсинга логируется.

        Проверяет:
        - При None из _parse_message обработчик не падает
        - processed_count не увеличивается
        """
        tl_msg = MagicMock()
        tl_msg.id = 99
        tl_msg.get_chat = AsyncMock(side_effect=RuntimeError("Ошибка"))

        await polling_service._process_message(tl_msg)

        assert polling_service.processed_count == 0
        polling_service.saver.save_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_message_save_failure(self, polling_service):
        """
        Ошибка сохранения сообщения логируется.

        Проверяет:
        - При save_message=False processed_count не увеличивается
        - update_chat_progress не вызывается
        """
        polling_service.saver.save_message = AsyncMock(return_value=False)

        tl_msg = make_tl_message(msg_id=42, text="Тестовое сообщение для проверки обработки")

        await polling_service._process_message(tl_msg)

        assert polling_service.processed_count == 0
        polling_service.saver.update_chat_progress.assert_not_called()


class TestLoadLastMessageIds:
    """Тесты метода load_last_message_ids."""

    @pytest.mark.asyncio
    async def test_load_last_message_ids(self, polling_service, mock_pool):
        """
        Загрузка последних ID сообщений для каждого чата.

        Проверяет:
        - Заполнение _last_message_ids из БД
        """
        mock_pool.fetchrow = AsyncMock(return_value={"last_message_id": 100})

        with patch.object(
            PollingService,
            "_get_monitored_chat_ids",
            new=AsyncMock(return_value=[-1001234567890, -1009876543210]),
        ):
            await polling_service.load_last_message_ids()

        assert polling_service._last_message_ids[-1001234567890] == 100
        assert polling_service._last_message_ids[-1009876543210] == 100
