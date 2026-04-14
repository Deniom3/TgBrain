"""
Модульные тесты для SessionManager.

Тестируют управление сессиями Telegram:
- Загрузка session_data из БД
- Расшифрование session_data
- Создание и очистка временных файлов
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import Settings
from src.infrastructure.services import SecureSessionFileService, SessionDecryptionService
from src.ingestion.session_manager import SessionManager
from src.settings.repositories.encryption_settings import EncryptionKeyMismatchError
from src.settings.repositories.telegram_auth import TelegramAuthRepository


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
def mock_telegram_auth_repo():
    """Создаёт mock TelegramAuthRepository."""
    repo = MagicMock(spec=TelegramAuthRepository)
    repo.get = AsyncMock()
    repo.get_session_data = AsyncMock()
    repo.save_session_data_v2 = AsyncMock()
    return repo


@pytest.fixture
def mock_app_settings_repo():
    """Создаёт mock AppSettingsRepository."""
    repo = AsyncMock()
    repo.get = AsyncMock(return_value=None)
    repo.get_value = AsyncMock(return_value=None)
    repo.upsert = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def session_manager(mock_settings, mock_telegram_auth_repo, mock_app_settings_repo):
    """Создаёт SessionManager с мокированными зависимостями."""
    manager = SessionManager(
        config=mock_settings,
        telegram_auth_repo=mock_telegram_auth_repo,
        app_settings_repo=mock_app_settings_repo,
    )
    return manager


class TestSessionManagerInit:
    """Тесты инициализации SessionManager."""

    def test_session_manager_init(self, session_manager):
        """
        SessionManager корректно инициализируется.

        Проверяет:
        - Сохранение переданных зависимостей
        - temp_session_file равен None
        """
        assert session_manager.temp_session_file is None


class TestLoadSessionData:
    """Тесты метода load_session_data."""

    @pytest.mark.asyncio
    async def test_load_session_data_success(self, session_manager, mock_telegram_auth_repo):
        """
        Успешная загрузка session_data.

        Проверяет:
        - Возврат session_data из репозитория
        """
        mock_auth = MagicMock()
        mock_auth.session_name = "test_session"
        mock_telegram_auth_repo.get = AsyncMock(return_value=mock_auth)
        mock_telegram_auth_repo.get_session_data = AsyncMock(return_value=b"raw_session_data")

        result = await session_manager.load_session_data()

        assert result == b"raw_session_data"
        mock_telegram_auth_repo.get.assert_called_once()
        mock_telegram_auth_repo.get_session_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_session_data_no_session_name(self, session_manager, mock_telegram_auth_repo):
        """
        session_name не установлен.

        Проверяет:
        - Возврат None при отсутствии session_name
        """
        mock_auth = MagicMock()
        mock_auth.session_name = None
        mock_telegram_auth_repo.get = AsyncMock(return_value=mock_auth)

        result = await session_manager.load_session_data()

        assert result is None
        mock_telegram_auth_repo.get_session_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_session_data_no_auth(self, session_manager, mock_telegram_auth_repo):
        """
        Авторизация не найдена.

        Проверяет:
        - Возврат None при отсутствии auth
        """
        mock_telegram_auth_repo.get = AsyncMock(return_value=None)

        result = await session_manager.load_session_data()

        assert result is None

    @pytest.mark.asyncio
    async def test_load_session_data_no_session_data(self, session_manager, mock_telegram_auth_repo):
        """
        session_data не найдена в БД.

        Проверяет:
        - Возврат None при отсутствии session_data
        """
        mock_auth = MagicMock()
        mock_auth.session_name = "test_session"
        mock_telegram_auth_repo.get = AsyncMock(return_value=mock_auth)
        mock_telegram_auth_repo.get_session_data = AsyncMock(return_value=None)

        result = await session_manager.load_session_data()

        assert result is None


class TestDecryptSessionData:
    """Тесты метода decrypt_session_data."""

    @pytest.mark.asyncio
    async def test_decrypt_session_data_encrypted(self, session_manager):
        """
        Расшифрование зашифрованных данных.

        Проверяет:
        - Вызов encryption_service.decrypt для зашифрованных данных
        - Возврат расшифрованных данных
        """
        encrypted_data = b"\x80encrypted_gZ\x80"
        decrypted_data = b"decrypted_session_bytes_data"

        with patch.object(SessionDecryptionService, "is_encrypted", return_value=True):
            mock_encryption_service = MagicMock()
            mock_encryption_service.decrypt = MagicMock(return_value=decrypted_data)

            with patch(
                "src.ingestion.session_manager.EncryptionService.create",
                new_callable=AsyncMock,
                return_value=mock_encryption_service,
            ):
                result = await session_manager.decrypt_session_data(encrypted_data)

        assert result == decrypted_data

    @pytest.mark.asyncio
    async def test_decrypt_session_data_not_encrypted_migration(self, session_manager, mock_telegram_auth_repo):
        """
        Миграция незашифрованных данных.

        Проверяет:
        - Шифрование и сохранение в БД
        - Возврат оригинальных данных
        """
        raw_data = b"raw_session_bytes_data"
        encrypted_data = b"encrypted_result_data"

        with patch.object(SessionDecryptionService, "is_encrypted", return_value=False):
            mock_encryption_service = MagicMock()
            mock_encryption_service.encrypt = MagicMock(return_value=encrypted_data)

            with patch(
                "src.ingestion.session_manager.EncryptionService.create",
                new_callable=AsyncMock,
                return_value=mock_encryption_service,
            ):
                result = await session_manager.decrypt_session_data(raw_data)

        assert result == raw_data
        mock_telegram_auth_repo.save_session_data_v2.assert_called_once_with(encrypted_data)

    @pytest.mark.asyncio
    async def test_decrypt_session_data_key_mismatch(self, session_manager):
        """
        Несовпадение ключа шифрования.

        Проверяет:
        - Вызов save_session_data_v2 не происходит
        - Исключение EncryptionKeyMismatchError пробрасывается
        """
        encrypted_data = b"\x80bad_key_gZ\x80"

        with patch.object(SessionDecryptionService, "is_encrypted", return_value=True):
            mock_encryption_service = MagicMock()
            mock_encryption_service.decrypt = MagicMock(
                side_effect=EncryptionKeyMismatchError("Ключ не совпадает")
            )

            with patch(
                "src.ingestion.session_manager.EncryptionService.create",
                new_callable=AsyncMock,
                return_value=mock_encryption_service,
            ):
                with pytest.raises(EncryptionKeyMismatchError):
                    await session_manager.decrypt_session_data(encrypted_data)

    @pytest.mark.asyncio
    async def test_decrypt_session_data_error(self, session_manager):
        """
        Ошибка расшифрования.

        Проверяет:
        - Произвольное исключение пробрасывается
        """
        encrypted_data = b"\x80corrupt_gZ\x80"

        with patch.object(SessionDecryptionService, "is_encrypted", return_value=True):
            mock_encryption_service = MagicMock()
            mock_encryption_service.decrypt = MagicMock(side_effect=ValueError("Bad data"))

            with patch(
                "src.ingestion.session_manager.EncryptionService.create",
                new_callable=AsyncMock,
                return_value=mock_encryption_service,
            ):
                with pytest.raises(ValueError):
                    await session_manager.decrypt_session_data(encrypted_data)


class TestCreateTempSessionFile:
    """Тесты метода create_temp_session_file."""

    @pytest.mark.asyncio
    async def test_create_temp_session_file(self, session_manager, tmp_path):
        """
        Создание временного файла сессии.

        Проверяет:
        - Возврат пути к файлу
        - Установка temp_session_file
        """
        test_data = b"session_binary_data_content"
        temp_file = str(tmp_path / "test.session")

        with patch.object(
            SecureSessionFileService,
            "create_temp_session_file",
            new_callable=AsyncMock,
            return_value=temp_file,
        ):
            result = await session_manager.create_temp_session_file(test_data)

        assert result == temp_file
        assert session_manager.temp_session_file == temp_file


class TestCleanupTempSessionFile:
    """Тесты метода cleanup_temp_session_file."""

    @pytest.mark.asyncio
    async def test_cleanup_temp_session_file_exists(self, session_manager):
        """
        Очистка существующего файла.

        Проверяет:
        - Вызов delete_temp_session_file
        - Очистка temp_session_file в None
        """
        session_manager.temp_session_file = "/tmp/test.session"

        with patch.object(
            SecureSessionFileService,
            "delete_temp_session_file",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_delete:
            await session_manager.cleanup_temp_session_file()

        mock_delete.assert_called_once_with("/tmp/test.session")
        assert session_manager.temp_session_file is None

    @pytest.mark.asyncio
    async def test_cleanup_temp_session_file_not_exists(self, session_manager):
        """
        Файл уже удалён.

        Проверяет:
        - delete возвращает False
        - temp_session_file всё равно очищается
        """
        session_manager.temp_session_file = "/tmp/missing.session"

        with patch.object(
            SecureSessionFileService,
            "delete_temp_session_file",
            new_callable=AsyncMock,
            return_value=False,
        ):
            await session_manager.cleanup_temp_session_file()

        assert session_manager.temp_session_file is None


class TestHasTempSessionFile:
    """Тесты метода has_temp_session_file."""

    def test_has_temp_session_file_true(self, session_manager):
        """
        Файл существует.

        Проверяет:
        - Возврат True при существующем файле
        """
        session_manager.temp_session_file = "/tmp/test.session"

        with patch.object(SecureSessionFileService, "exists", return_value=True):
            result = session_manager.has_temp_session_file()

        assert result is True

    def test_has_temp_session_file_false(self, session_manager):
        """
        Файл не существует.

        Проверяет:
        - Возврат False при temp_session_file = None
        """
        session_manager.temp_session_file = None

        result = session_manager.has_temp_session_file()

        assert result is False


class TestReloadSession:
    """Тесты метода reload_session."""

    @pytest.mark.asyncio
    async def test_reload_session_success(self, session_manager):
        """
        Перезагрузка сессии.

        Проверяет:
        - Вызов load_session_data и decrypt_session_data
        - Возврат расшифрованных данных
        """
        decrypted = b"reloaded_session_data"

        with patch.object(
            session_manager,
            "load_session_data",
            new=AsyncMock(return_value=b"raw_data"),
        ):
            with patch.object(
                session_manager,
                "decrypt_session_data",
                new=AsyncMock(return_value=decrypted),
            ):
                result = await session_manager.reload_session()

        assert result == decrypted

    @pytest.mark.asyncio
    async def test_reload_session_failure(self, session_manager):
        """
        Ошибка перезагрузки сессии.

        Проверяет:
        - Возврат None при отсутствии session_data
        """
        with patch.object(
            session_manager,
            "load_session_data",
            new=AsyncMock(return_value=None),
        ):
            result = await session_manager.reload_session()

        assert result is None
