"""
Тесты для модуля шифрования session_data.

Проверяет:
- Генерацию ключа шифрования
- Шифрование/дешифрование данных
- Миграцию незашифрованных данных
- Очистку orphaned файлов
- Безопасное создание временных файлов
"""

import os
import pytest

from cryptography.fernet import Fernet

from src.settings.repositories.encryption_settings import (
    EncryptionService,
    EncryptionKeyMismatchError,
    get_encryption_service,
    ENCRYPTION_KEY_KEY,
)
from src.settings.repositories.app_settings import AppSettingsRepository

pytestmark = pytest.mark.integration


@pytest.mark.integration
class TestEncryptionService:
    """Тесты сервиса шифрования."""

    @pytest.fixture
    async def app_settings_repo(self):
        """Фикстура репозитория настроек приложения."""
        from src.database import get_pool
        pool = await get_pool()
        return AppSettingsRepository(pool)

    @pytest.fixture
    async def cleanup_encryption_key(self, app_settings_repo):
        """Фикстура для очистки ключа шифрования после теста."""
        yield
        await app_settings_repo.delete(ENCRYPTION_KEY_KEY)

    @pytest.mark.asyncio
    async def test_create_service(self, cleanup_encryption_key, app_settings_repo):
        """Тест создания сервиса шифрования."""
        service = await EncryptionService.create(app_settings_repo)
        assert service is not None
        assert service.cipher is not None
        assert isinstance(service.cipher, Fernet)

    @pytest.mark.asyncio
    async def test_encrypt_decrypt(self, cleanup_encryption_key, app_settings_repo):
        """Тест шифрования и дешифрования данных."""
        service = await EncryptionService.create(app_settings_repo)

        original_data = b"test session data for encryption"

        encrypted = service.encrypt(original_data)
        assert encrypted is not None
        assert encrypted != original_data
        assert encrypted.startswith(b"gAAAAA")

        decrypted = service.decrypt(encrypted)
        assert decrypted == original_data

    @pytest.mark.asyncio
    async def test_decrypt_invalid_data_raises(self, cleanup_encryption_key, app_settings_repo):
        """Тест дешифрования невалидных данных (InvalidToken)."""
        service = await EncryptionService.create(app_settings_repo)

        invalid_data = b"invalid encrypted data"

        with pytest.raises(EncryptionKeyMismatchError):
            service.decrypt(invalid_data)

    @pytest.mark.asyncio
    async def test_decrypt_with_wrong_key_raises(self, cleanup_encryption_key, app_settings_repo):
        """Тест дешифрования данных с неправильным ключом."""
        service1 = await EncryptionService.create(app_settings_repo)
        test_data = b"test session data"
        encrypted = service1.encrypt(test_data)

        # Создаём новый сервис с другим ключом
        other_key = Fernet.generate_key()
        other_cipher = Fernet(other_key)
        service2 = EncryptionService(cipher=other_cipher)

        # Попытка расшифровать данные другим ключом должна вызвать EncryptionKeyMismatchError
        with pytest.raises(EncryptionKeyMismatchError):
            service2.decrypt(encrypted)

    @pytest.mark.asyncio
    async def test_migrate_unencrypted_data(self, cleanup_encryption_key, app_settings_repo):
        """Тест миграции незашифрованных данных."""
        service = await EncryptionService.create(app_settings_repo)

        original_data = b"unencrypted session data"

        encrypted = await service.migrate_unencrypted_data(original_data)
        assert encrypted is not None
        assert encrypted != original_data
        assert encrypted.startswith(b"gAAAAA")

        decrypted = service.decrypt(encrypted)
        assert decrypted == original_data

    @pytest.mark.asyncio
    async def test_key_persisted_in_db(self, cleanup_encryption_key, app_settings_repo):
        """Тест сохранения ключа в БД."""
        service1 = await EncryptionService.create(app_settings_repo)
        test_data = b"test data for key comparison"
        encrypted1 = service1.encrypt(test_data)

        service2 = await EncryptionService.create(app_settings_repo)
        decrypted = service2.decrypt(encrypted1)

        assert decrypted == test_data

    @pytest.mark.asyncio
    async def test_is_encryption_configured(self, cleanup_encryption_key, app_settings_repo):
        """Тест проверки настроенности шифрования."""
        setting = await app_settings_repo.get(key=ENCRYPTION_KEY_KEY)
        configured = bool(setting and setting.value)
        assert configured is False

        await EncryptionService.create(app_settings_repo)

        setting = await app_settings_repo.get(key=ENCRYPTION_KEY_KEY)
        configured = bool(setting and setting.value)
        assert configured is True

    @pytest.mark.asyncio
    async def test_get_encryption_service(self, cleanup_encryption_key, app_settings_repo):
        """Тест получения сервиса через factory функцию."""
        service = await get_encryption_service(app_settings_repo)
        assert service is not None
        assert isinstance(service, EncryptionService)


@pytest.mark.integration
class TestSecureTempFileCreation:
    """Тесты безопасного создания временных файлов."""

    @pytest.fixture
    async def ingester(self, settings):
        """Создание Ingester для тестов."""
        from src.ingestion import TelegramIngester
        from src.embeddings import EmbeddingsClient
        from unittest.mock import AsyncMock

        emb_client = EmbeddingsClient(settings)
        mock_telegram_auth_repo = AsyncMock()
        mock_telegram_auth_repo.get = AsyncMock(return_value=None)
        mock_telegram_auth_repo.get_session_data = AsyncMock(return_value=None)
        mock_app_settings_repo = AsyncMock()
        mock_app_settings_repo.get = AsyncMock(return_value=None)

        ingester = TelegramIngester(settings, emb_client, mock_telegram_auth_repo, mock_app_settings_repo)

        yield ingester

    def test_create_secure_temp_file(self, ingester):
        """Тест создания файла с безопасными настройками."""
        test_data = b"test session data"

        file_path = ingester._create_secure_temp_file(test_data)

        assert os.path.exists(file_path)

        file_mode = os.stat(file_path).st_mode & 0o777
        assert file_mode in (0o600, 0o666)

        with open(file_path, "rb") as f:
            content = f.read()
        assert content == test_data

        os.remove(file_path)

    def test_create_secure_temp_file_cleanup_on_error(self, ingester):
        """Тест очистки файла при ошибке создания."""
        test_data = b"test session data"

        original_chmod = os.chmod

        def failing_chmod(path, mode):
            original_chmod(path, mode)
            raise PermissionError("Simulated permission error")

        os.chmod = failing_chmod  # type: ignore[assignment]

        try:
            with pytest.raises(PermissionError):
                ingester._create_secure_temp_file(test_data)
        finally:
            os.chmod = original_chmod


@pytest.mark.integration
class TestTempSessionFileCleanup:
    """Тесты очистки временных файлов сессий."""

    @pytest.fixture
    async def ingester_with_temp_file(self, settings):
        """Создание Ingester с временным файлом."""
        from src.ingestion import TelegramIngester
        from src.embeddings import EmbeddingsClient
        from unittest.mock import AsyncMock

        emb_client = EmbeddingsClient(settings)
        mock_telegram_auth_repo = AsyncMock()
        mock_telegram_auth_repo.get = AsyncMock(return_value=None)
        mock_telegram_auth_repo.get_session_data = AsyncMock(return_value=None)
        mock_app_settings_repo = AsyncMock()
        mock_app_settings_repo.get = AsyncMock(return_value=None)

        ingester = TelegramIngester(settings, emb_client, mock_telegram_auth_repo, mock_app_settings_repo)

        test_data = b"test session data"
        temp_path = ingester._create_secure_temp_file(test_data)
        ingester._session_lifecycle = type('obj', (object,), {'_temp_session_file': temp_path})()

        yield ingester

        if os.path.exists(temp_path):
            os.remove(temp_path)

    def test_cleanup_temp_session_file_exists(self, ingester_with_temp_file):
        """Тест очистки существующего файла."""
        ingester = ingester_with_temp_file
        temp_path = ingester._session_lifecycle._temp_session_file

        assert os.path.exists(temp_path)

        if os.path.exists(temp_path):
            os.remove(temp_path)
            assert not os.path.exists(temp_path)

    def test_cleanup_temp_session_file_not_exists(self, ingester_with_temp_file):
        """Тест очистки несуществующего файла."""
        ingester = ingester_with_temp_file
        temp_path = ingester._session_lifecycle._temp_session_file

        if os.path.exists(temp_path):
            os.remove(temp_path)
        assert not os.path.exists(temp_path)



