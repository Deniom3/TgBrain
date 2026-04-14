"""
Модульные тесты для TelegramConnection.

Тестируют подключение к Telegram:
- Создание клиента
- Подключение и отключение
- Проверка авторизации
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import Settings
from src.ingestion.telegram_connection import TelegramConnection


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
def session_file_path():
    """Путь к файлу сессии."""
    return "/tmp/test_telegram_connection.session"


@pytest.fixture
def telegram_connection(mock_settings, session_file_path):
    """Создаёт TelegramConnection с мокированными зависимостями."""
    connection = TelegramConnection(
        config=mock_settings,
        session_file_path=session_file_path,
    )
    return connection


class TestTelegramConnectionInit:
    """Тесты инициализации TelegramConnection."""

    def test_telegram_connection_init(self, telegram_connection, session_file_path):
        """
        TelegramConnection корректно инициализируется.

        Проверяет:
        - Сохранение config и session_file_path
        - client равен None
        """
        assert telegram_connection.session_file_path == session_file_path
        assert telegram_connection.client is None


class TestConnect:
    """Тесты метода connect."""

    @pytest.mark.asyncio
    async def test_connect_success(self, telegram_connection, mock_settings):
        """
        Успешное подключение и авторизация.

        Проверяет:
        - Создание TelegramClient
        - Вызов connect, is_user_authorized, get_me
        - Возврат True
        """
        mock_me = MagicMock()
        mock_me.username = "test_bot"
        mock_me.first_name = "Test"

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.is_user_authorized = AsyncMock(return_value=True)
        mock_client.get_me = AsyncMock(return_value=mock_me)
        mock_client.is_connected = MagicMock(return_value=True)

        with patch(
            "src.ingestion.telegram_connection.TelegramClient",
            return_value=mock_client,
        ) as mock_tc:
            result = await telegram_connection.connect()

        assert result is True
        mock_tc.assert_called_once_with(
            telegram_connection.session_file_path,
            mock_settings.tg_api_id,
            mock_settings.tg_api_hash,
        )
        mock_client.connect.assert_called_once()
        assert telegram_connection.client is mock_client

    @pytest.mark.asyncio
    async def test_connect_not_authorized(self, telegram_connection):
        """
        Клиент не авторизован.

        Проверяет:
        - Возврат False при is_user_authorized=False
        - Вызов disconnect
        """
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.is_user_authorized = AsyncMock(return_value=False)
        mock_client.disconnect = AsyncMock()

        with patch(
            "src.ingestion.telegram_connection.TelegramClient",
            return_value=mock_client,
        ):
            result = await telegram_connection.connect()

        assert result is False
        mock_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_exception(self, telegram_connection):
        """
        Ошибка подключения.

        Проверяет:
        - Возврат False при исключении
        """
        with patch(
            "src.ingestion.telegram_connection.TelegramClient",
            side_effect=ConnectionError("Network error"),
        ):
            result = await telegram_connection.connect()

        assert result is False


class TestDisconnect:
    """Тесты метода disconnect."""

    @pytest.mark.asyncio
    async def test_disconnect(self, telegram_connection):
        """
        Отключение от Telegram.

        Проверяет:
        - Вызов client.disconnect
        - Очистка client в None
        """
        mock_client = AsyncMock()
        mock_client.disconnect = AsyncMock()
        telegram_connection.client = mock_client

        await telegram_connection.disconnect()

        mock_client.disconnect.assert_called_once()
        assert telegram_connection.client is None

    @pytest.mark.asyncio
    async def test_disconnect_no_client(self, telegram_connection):
        """
        Отключение без клиента.

        Проверяет:
        - Отсутствие ошибок при client=None
        """
        await telegram_connection.disconnect()

        assert telegram_connection.client is None


class TestIsConnected:
    """Тесты метода is_connected."""

    def test_is_connected_true(self, telegram_connection):
        """
        Клиент подключён.

        Проверяет:
        - Возврат True при подключённом клиенте
        """
        mock_client = MagicMock()
        mock_client.is_connected = MagicMock(return_value=True)
        telegram_connection.client = mock_client

        result = telegram_connection.is_connected()

        assert result is True

    def test_is_connected_false_no_client(self, telegram_connection):
        """
        Клиент не подключён.

        Проверяет:
        - Возврат False при client=None
        """
        result = telegram_connection.is_connected()

        assert result is False

    def test_is_connected_false_disconnected(self, telegram_connection):
        """
        Клиент отключён.

        Проверяет:
        - Возврат False при is_connected=False
        """
        mock_client = MagicMock()
        mock_client.is_connected = MagicMock(return_value=False)
        telegram_connection.client = mock_client

        result = telegram_connection.is_connected()

        assert result is False


class TestIsAuthorized:
    """Тесты метода is_authorized."""

    @pytest.mark.asyncio
    async def test_is_authorized_true(self, telegram_connection):
        """
        Клиент авторизован.

        Проверяет:
        - Возврат True при авторизованном клиенте
        """
        mock_client = AsyncMock()
        mock_client.is_user_authorized = AsyncMock(return_value=True)
        telegram_connection.client = mock_client

        result = await telegram_connection.is_authorized()

        assert result is True

    @pytest.mark.asyncio
    async def test_is_authorized_false_no_client(self, telegram_connection):
        """
        Нет клиента.

        Проверяет:
        - Возврат False при client=None
        """
        result = await telegram_connection.is_authorized()

        assert result is False


class TestGetMe:
    """Тесты метода get_me."""

    @pytest.mark.asyncio
    async def test_get_me_success(self, telegram_connection):
        """
        Получение информации о пользователе.

        Проверяет:
        - Возврат dict с полями id, username, first_name, last_name
        """
        mock_me = MagicMock()
        mock_me.id = 12345
        mock_me.username = "test_user"
        mock_me.first_name = "Test"
        mock_me.last_name = "User"

        mock_client = AsyncMock()
        mock_client.get_me = AsyncMock(return_value=mock_me)
        telegram_connection.client = mock_client

        result = await telegram_connection.get_me()

        assert result == {
            "id": 12345,
            "username": "test_user",
            "first_name": "Test",
            "last_name": "User",
        }

    @pytest.mark.asyncio
    async def test_get_me_no_client(self, telegram_connection):
        """
        Нет клиента.

        Проверяет:
        - Возврат None при client=None
        """
        result = await telegram_connection.get_me()

        assert result is None


class TestGetClient:
    """Тесты метода get_client."""

    def test_get_client(self, telegram_connection):
        """
        Получение клиента.

        Проверяет:
        - Возврат объекта клиента
        """
        mock_client = MagicMock()
        telegram_connection.client = mock_client

        result = telegram_connection.get_client()

        assert result == mock_client

    def test_get_client_none(self, telegram_connection):
        """
        Клиент не инициализирован.

        Проверяет:
        - Возврат None при client=None
        """
        result = telegram_connection.get_client()

        assert result is None
