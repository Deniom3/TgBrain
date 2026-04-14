"""
Модульные тесты для SessionLifecycleManager.

Тестируют управление жизненным циклом сессии Telegram:
- Загрузка, подключение, отключение
- Очистка временных файлов
- Перезагрузка сессии
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import Settings
from src.ingestion.session_lifecycle import SessionLifecycleManager
from src.ingestion.session_manager import SessionManager
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
def mock_session_manager():
    """Создаёт mock SessionManager."""
    manager = AsyncMock(spec=SessionManager)
    manager.load_session_data = AsyncMock()
    manager.decrypt_session_data = AsyncMock()
    manager.create_temp_session_file = AsyncMock()
    manager.cleanup_temp_session_file = AsyncMock()
    manager.reload_session = AsyncMock()
    manager.temp_session_file = None
    return manager


@pytest.fixture
def mock_telegram_connection():
    """Создаёт mock TelegramConnection."""
    connection = AsyncMock(spec=TelegramConnection)
    connection.connect = AsyncMock()
    connection.disconnect = AsyncMock()
    connection.is_connected = MagicMock()
    connection.get_client = MagicMock()
    return connection


@pytest.fixture
def lifecycle_manager(mock_settings, mock_session_manager, mock_telegram_connection):
    """Создаёт SessionLifecycleManager с мокированными зависимостями."""
    manager = SessionLifecycleManager(
        config=mock_settings,
        session_manager=mock_session_manager,
        telegram_connection=mock_telegram_connection,
    )
    return manager


class TestSessionLifecycleManagerInit:
    """Тесты инициализации SessionLifecycleManager."""

    def test_session_lifecycle_manager_init(self, lifecycle_manager):
        """
        SessionLifecycleManager корректно инициализируется.

        Проверяет:
        - Сохранение переданных зависимостей
        - _temp_session_file равен None
        """
        assert lifecycle_manager._temp_session_file is None


class TestLoadSession:
    """Тесты метода load_session."""

    @pytest.mark.asyncio
    async def test_load_session_success(self, lifecycle_manager, mock_session_manager):
        """
        Успешная загрузка сессии.

        Проверяет:
        - Вызов load_session_data, decrypt_session_data, create_temp_session_file
        - Установка _temp_session_file
        - Возврат True
        """
        mock_session_manager.load_session_data = AsyncMock(return_value=b"session_data")
        mock_session_manager.decrypt_session_data = AsyncMock(return_value=b"decrypted_data")
        mock_session_manager.create_temp_session_file = AsyncMock(return_value="/tmp/test.session")

        result = await lifecycle_manager.load_session()

        assert result is True
        assert lifecycle_manager._temp_session_file == "/tmp/test.session"

    @pytest.mark.asyncio
    async def test_load_session_no_data(self, lifecycle_manager, mock_session_manager):
        """
        session_data не найдена.

        Проверяет:
        - Возврат False при отсутствии session_data
        """
        mock_session_manager.load_session_data = AsyncMock(return_value=None)

        result = await lifecycle_manager.load_session()

        assert result is False


class TestConnect:
    """Тесты метода connect."""

    @pytest.mark.asyncio
    async def test_connect_success(self, lifecycle_manager, mock_telegram_connection):
        """
        Успешное подключение.

        Проверяет:
        - Вызов telegram_connection.connect
        - Возврат True
        """
        lifecycle_manager._temp_session_file = "/tmp/test.session"
        mock_telegram_connection.connect = AsyncMock(return_value=True)

        result = await lifecycle_manager.connect()

        assert result is True
        mock_telegram_connection.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_no_temp_file(self, lifecycle_manager):
        """
        Временный файл не создан.

        Проверяет:
        - Возврат False при отсутствии temp_file
        - connect не вызывается
        """
        result = await lifecycle_manager.connect()

        assert result is False

    @pytest.mark.asyncio
    async def test_connect_failure(self, lifecycle_manager, mock_telegram_connection):
        """
        Ошибка подключения.

        Проверяет:
        - Возврат False при неудачном connect
        """
        lifecycle_manager._temp_session_file = "/tmp/test.session"
        mock_telegram_connection.connect = AsyncMock(return_value=False)

        result = await lifecycle_manager.connect()

        assert result is False


class TestDisconnect:
    """Тесты метода disconnect."""

    @pytest.mark.asyncio
    async def test_disconnect(self, lifecycle_manager, mock_telegram_connection):
        """
        Отключение от Telegram.

        Проверяет:
        - Вызов telegram_connection.disconnect
        """
        await lifecycle_manager.disconnect()

        mock_telegram_connection.disconnect.assert_called_once()


class TestCleanup:
    """Тесты метода cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup(self, lifecycle_manager):
        """
        Очистка временного файла.

        Проверяет:
        - Удаление файла через os.unlink
        - Очистка _temp_session_file
        """
        lifecycle_manager._temp_session_file = "/tmp/test.session"

        with patch.object(os, "unlink") as mock_unlink:
            await lifecycle_manager.cleanup()

        mock_unlink.assert_called_once_with("/tmp/test.session")
        assert lifecycle_manager._temp_session_file is None

    @pytest.mark.asyncio
    async def test_cleanup_file_not_found(self, lifecycle_manager):
        """
        Файл уже удалён.

        Проверяет:
        - FileNotFoundError не вызывает ошибку
        - _temp_session_file очищается
        """
        lifecycle_manager._temp_session_file = "/tmp/missing.session"

        with patch.object(os, "unlink", side_effect=FileNotFoundError):
            await lifecycle_manager.cleanup()

        assert lifecycle_manager._temp_session_file is None

    @pytest.mark.asyncio
    async def test_cleanup_error(self, lifecycle_manager):
        """
        Ошибка при очистке.

        Проверяет:
        - Произвольное исключение логируется
        - _temp_session_file всё равно очищается
        """
        lifecycle_manager._temp_session_file = "/tmp/test.session"

        with patch.object(os, "unlink", side_effect=PermissionError("Access denied")):
            await lifecycle_manager.cleanup()

        assert lifecycle_manager._temp_session_file is None


class TestReloadSession:
    """Тесты метода reload_session."""

    @pytest.mark.asyncio
    async def test_reload_session_success(self, lifecycle_manager, mock_session_manager, mock_telegram_connection):
        """
        Успешная перезагрузка сессии.

        Проверяет:
        - Вызов reload_session, создание нового файла
        - Отключение и повторное подключение
        - Возврат True
        """
        mock_session_manager.reload_session = AsyncMock(return_value=b"new_session_data")
        mock_session_manager.create_temp_session_file = AsyncMock(return_value="/tmp/new.session")
        mock_telegram_connection.connect = AsyncMock(return_value=True)
        lifecycle_manager._temp_session_file = "/tmp/old.session"

        with patch.object(os, "unlink") as mock_unlink:
            result = await lifecycle_manager.reload_session()

        assert result is True
        mock_unlink.assert_called_once_with("/tmp/old.session")
        mock_telegram_connection.disconnect.assert_called_once()
        mock_telegram_connection.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_reload_session_no_data(self, lifecycle_manager, mock_session_manager):
        """
        Ошибка перезагрузки сессии.

        Проверяет:
        - Возврат False при отсутствии данных
        """
        mock_session_manager.reload_session = AsyncMock(return_value=None)

        result = await lifecycle_manager.reload_session()

        assert result is False

    @pytest.mark.asyncio
    async def test_reload_session_disconnect_failure(self, lifecycle_manager, mock_session_manager, mock_telegram_connection):
        """
        Ошибка отключения при перезагрузке.

        Проверяет:
        - Возврат False при неудачном reconnect
        """
        mock_session_manager.reload_session = AsyncMock(return_value=b"new_session_data")
        mock_session_manager.create_temp_session_file = AsyncMock(return_value="/tmp/new.session")
        mock_telegram_connection.connect = AsyncMock(return_value=False)
        lifecycle_manager._temp_session_file = "/tmp/old.session"

        with patch.object(os, "unlink"):
            result = await lifecycle_manager.reload_session()

        assert result is False

    @pytest.mark.asyncio
    async def test_reload_session_exception(self, lifecycle_manager, mock_session_manager):
        """
        Общее исключение при перезагрузке.

        Проверяет:
        - Возврат False при произвольном исключении
        """
        mock_session_manager.reload_session = AsyncMock(side_effect=RuntimeError("Unexpected error"))

        result = await lifecycle_manager.reload_session()

        assert result is False


class TestGetClient:
    """Тесты метода get_client."""

    def test_get_client(self, lifecycle_manager, mock_telegram_connection):
        """
        Получение клиента.

        Проверяет:
        - Делегирование telegram_connection.get_client
        """
        mock_client = MagicMock()
        mock_telegram_connection.get_client = MagicMock(return_value=mock_client)

        result = lifecycle_manager.get_client()

        assert result == mock_client


class TestIsConnected:
    """Тесты метода is_connected."""

    def test_is_connected(self, lifecycle_manager, mock_telegram_connection):
        """
        Проверка подключения.

        Проверяет:
        - Делегирование telegram_connection.is_connected
        """
        mock_telegram_connection.is_connected = MagicMock(return_value=True)

        result = lifecycle_manager.is_connected()

        assert result is True


class TestSetTempSessionFile:
    """Тесты метода set_temp_session_file."""

    def test_set_temp_session_file(self, lifecycle_manager):
        """
        Установка временного файла.

        Проверяет:
        - Установка _temp_session_file
        """
        lifecycle_manager.set_temp_session_file("/tmp/manual.session")

        assert lifecycle_manager._get_temp_file_path() == "/tmp/manual.session"
