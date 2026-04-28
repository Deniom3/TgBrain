"""
Модульные тесты для TelegramClientFactory.

Тестируют:
- Happy path создания клиента из DB-backed сессии
- Отсутствие session_data → SessionNotConfiguredError
- Неавторизованный клиент → SessionNotAuthorizedError
- EncryptionKeyMismatchError → SessionDecryptionError с chaining
- Generic Exception при decrypt → SessionDecryptionError с chaining
- Cleanup временного файла
- Cleanup не удаляет symlink
- Независимость создаваемых клиентов
- Timeout при connect()
- Очистка temp file при ошибке создания TelegramClient
- Не зашифрованные данные передаются без расшифровки
- Зашифрованные данные без encryption_service → SessionDecryptionError
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.config import Settings
from src.infrastructure.exceptions import (
    SessionDecryptionError,
    SessionNotAuthorizedError,
    SessionNotConfiguredError,
)
from src.infrastructure.services.session_decryption_service import (
    SessionDecryptionService,
)
from src.infrastructure.telegram_client_factory import TelegramClientFactory
from src.settings.repositories.encryption_settings import (
    EncryptionKeyMismatchError,
    EncryptionService,
)
from src.settings.repositories.telegram_auth import TelegramAuthRepository


@pytest.fixture
def mock_telegram_auth_repo() -> AsyncMock:
    repo = AsyncMock(spec=TelegramAuthRepository)
    repo.get_session_data = AsyncMock(return_value=b"encrypted_session_data")
    return repo


@pytest.fixture
def mock_settings() -> MagicMock:
    settings = MagicMock(spec=Settings)
    settings.tg_api_id = 12345
    settings.tg_api_hash = "abcdef1234567890abcdef1234567890"
    return settings


@pytest.fixture
def mock_encryption_service() -> MagicMock:
    service = MagicMock(spec=EncryptionService)
    service.decrypt = MagicMock(return_value=b"decrypted_session_data")
    return service


@pytest.fixture
def factory(
    mock_telegram_auth_repo: AsyncMock,
    mock_settings: MagicMock,
    mock_encryption_service: MagicMock,
) -> TelegramClientFactory:
    return TelegramClientFactory(
        telegram_auth_repo=mock_telegram_auth_repo,
        settings=mock_settings,
        encryption_service=mock_encryption_service,
    )


class TestClientFactoryCreatesClient:
    """Тесты happy path создания клиента."""

    async def test_client_factory_creates_client_with_db_session(
        self,
        factory: TelegramClientFactory,
        mock_encryption_service: MagicMock,
    ) -> None:
        """Happy path: фабрика создаёт клиент с корректной сессией."""
        with (
            patch(
                "src.infrastructure.telegram_client_factory.SessionDecryptionService"
            ) as mock_sds,
            patch(
                "src.infrastructure.telegram_client_factory.SecureSessionFileService"
            ) as mock_ssfs,
            patch("src.infrastructure.telegram_client_factory.TelegramClient") as mock_tc,
        ):
            mock_sds.is_encrypted.return_value = True
            mock_ssfs.create_temp_session_file = AsyncMock(
                return_value="/tmp/test_session.session"
            )
            mock_tc_instance = AsyncMock()
            mock_tc.return_value = mock_tc_instance

            client, path = await factory.create_client()

            assert path == "/tmp/test_session.session"
            mock_sds.is_encrypted.assert_called_once_with(b"encrypted_session_data")
            mock_encryption_service.decrypt.assert_called_once_with(
                b"encrypted_session_data"
            )
            mock_tc.assert_called_once_with(
                "/tmp/test_session.session", 12345, "abcdef1234567890abcdef1234567890"
            )


class TestClientFactoryNoSessionData:
    """Тесты отсутствия session_data."""

    async def test_client_factory_no_session_data_raises_not_configured(
        self,
        factory: TelegramClientFactory,
        mock_telegram_auth_repo: AsyncMock,
    ) -> None:
        """Отсутствие session_data → SessionNotConfiguredError."""
        mock_telegram_auth_repo.get_session_data = AsyncMock(return_value=None)

        with pytest.raises(SessionNotConfiguredError):
            await factory.create_client()


class TestClientFactoryNotAuthorized:
    """Тесты неавторизованного клиента."""

    async def test_client_factory_not_authorized_raises_error(
        self,
        factory: TelegramClientFactory,
    ) -> None:
        """Неавторизованный клиент → SessionNotAuthorizedError."""
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.is_user_authorized = AsyncMock(return_value=False)

        with pytest.raises(SessionNotAuthorizedError):
            await factory.connect_client(mock_client)

        mock_client.connect.assert_called_once()


class TestClientFactoryKeyMismatch:
    """Тесты ошибки несовпадения ключа шифрования."""

    async def test_client_factory_key_mismatch_raises_decryption_error(
        self,
        factory: TelegramClientFactory,
        mock_encryption_service: MagicMock,
    ) -> None:
        """EncryptionKeyMismatchError → SessionDecryptionError с chaining."""
        mock_encryption_service.decrypt.side_effect = EncryptionKeyMismatchError(
            "Ключ не совпадает"
        )

        with (
            patch(
                "src.infrastructure.telegram_client_factory.SessionDecryptionService"
            ) as mock_sds,
        ):
            mock_sds.is_encrypted.return_value = True

            with pytest.raises(SessionDecryptionError) as exc_info:
                await factory.create_client()

            assert isinstance(exc_info.value.__cause__, EncryptionKeyMismatchError)


class TestClientFactoryGenericDecryptError:
    """Тесты generic Exception при расшифровке."""

    async def test_client_factory_generic_exception_raises_decryption_error_with_chain(
        self,
        factory: TelegramClientFactory,
        mock_encryption_service: MagicMock,
    ) -> None:
        """Generic Exception при decrypt → SessionDecryptionError с chaining."""
        mock_encryption_service.decrypt.side_effect = ValueError("unexpected error")

        with (
            patch(
                "src.infrastructure.telegram_client_factory.SessionDecryptionService"
            ) as mock_sds,
        ):
            mock_sds.is_encrypted.return_value = True

            with pytest.raises(SessionDecryptionError) as exc_info:
                await factory.create_client()

            assert isinstance(exc_info.value.__cause__, ValueError)


class TestClientFactoryCleanup:
    """Тесты очистки временных файлов."""

    def test_client_factory_cleanup_removes_temp_file(
        self,
        factory: TelegramClientFactory,
    ) -> None:
        """Cleanup удаляет существующий временный файл."""
        with patch("os.path.exists", return_value=True), \
             patch("os.path.islink", return_value=False), \
             patch("os.remove") as mock_remove:
            factory.cleanup("/tmp/test_session.session")
            mock_remove.assert_called_once_with("/tmp/test_session.session")

    def test_client_factory_cleanup_skips_nonexistent_file(
        self,
        factory: TelegramClientFactory,
    ) -> None:
        """Cleanup не вызывает os.remove для несуществующего файла."""
        with patch("os.path.exists", return_value=False), \
             patch("os.remove") as mock_remove:
            factory.cleanup("/tmp/nonexistent.session")
            mock_remove.assert_not_called()


class TestClientFactoryIndependentClients:
    """Тесты независимости создаваемых клиентов."""

    async def test_client_factory_creates_independent_clients(
        self,
        factory: TelegramClientFactory,
        mock_telegram_auth_repo: AsyncMock,
        mock_encryption_service: MagicMock,
    ) -> None:
        """Каждый вызов create_client создаёт независимый temp file."""
        with (
            patch(
                "src.infrastructure.telegram_client_factory.SessionDecryptionService"
            ) as mock_sds,
            patch(
                "src.infrastructure.telegram_client_factory.SecureSessionFileService"
            ) as mock_ssfs,
            patch("src.infrastructure.telegram_client_factory.TelegramClient"),
        ):
            mock_sds.is_encrypted.return_value = True
            mock_ssfs.create_temp_session_file = AsyncMock(
                side_effect=["/tmp/session_1.session", "/tmp/session_2.session"]
            )

            _, path1 = await factory.create_client()
            _, path2 = await factory.create_client()

            assert path1 != path2


class TestClientFactoryConnectTimeout:
    """Тесты timeout при connect."""

    async def test_client_factory_connect_timeout(
        self,
        factory: TelegramClientFactory,
    ) -> None:
        """Timeout при connect() пробрасывается как есть."""
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock(side_effect=TimeoutError("Connection timeout"))

        with pytest.raises(TimeoutError, match="Connection timeout"):
            await factory.connect_client(mock_client)


class TestClientFactoryTempFileCleanup:
    """Тесты очистки temp file при ошибке создания TelegramClient."""

    async def test_client_factory_cleans_temp_file_on_telegram_client_error(
        self,
        factory: TelegramClientFactory,
        mock_encryption_service: MagicMock,
    ) -> None:
        """Ошибка при создании TelegramClient → cleanup temp file."""
        with (
            patch(
                "src.infrastructure.telegram_client_factory.SessionDecryptionService"
            ) as mock_sds,
            patch(
                "src.infrastructure.telegram_client_factory.SecureSessionFileService"
            ) as mock_ssfs,
            patch(
                "src.infrastructure.telegram_client_factory.TelegramClient",
                side_effect=RuntimeError("client init failed"),
            ),
            patch("os.path.exists", return_value=True),
            patch("os.path.islink", return_value=False),
            patch("os.remove") as mock_remove,
        ):
            mock_sds.is_encrypted.return_value = False
            mock_ssfs.create_temp_session_file = AsyncMock(
                return_value="/tmp/failing_session.session"
            )

            with pytest.raises(RuntimeError, match="client init failed"):
                await factory.create_client()

            mock_remove.assert_called_once_with("/tmp/failing_session.session")


class TestClientFactoryUnencryptedSession:
    """Тесты для не зашифрованного session_data."""

    async def test_client_factory_unencrypted_data_passes_through(
        self,
        mock_telegram_auth_repo: AsyncMock,
        mock_settings: MagicMock,
        mock_encryption_service: MagicMock,
    ) -> None:
        """Не зашифрованные данные передаются без расшифровки."""
        unencrypted_data = b"raw_session_data"
        mock_telegram_auth_repo.get_session_data = AsyncMock(
            return_value=unencrypted_data
        )

        factory = TelegramClientFactory(
            mock_telegram_auth_repo, mock_settings, mock_encryption_service
        )

        with patch.object(SessionDecryptionService, "is_encrypted", return_value=False):
            result = factory._decrypt(unencrypted_data)

        assert result == unencrypted_data
        mock_encryption_service.decrypt.assert_not_called()

    async def test_client_factory_encrypted_without_service_raises(
        self,
        mock_telegram_auth_repo: AsyncMock,
        mock_settings: MagicMock,
    ) -> None:
        """Зашифрованные данные без encryption_service → SessionDecryptionError."""
        encrypted_data = b"gAAAAAencrypted_payload"
        mock_telegram_auth_repo.get_session_data = AsyncMock(
            return_value=encrypted_data
        )

        factory = TelegramClientFactory(
            mock_telegram_auth_repo, mock_settings, None
        )

        with patch.object(SessionDecryptionService, "is_encrypted", return_value=True):
            with pytest.raises(SessionDecryptionError):
                factory._decrypt(encrypted_data)


class TestClientFactoryCleanupSymlink:
    """Тесты symlink-проверки при cleanup."""

    def test_client_factory_cleanup_skips_symlink(
        self,
        factory: TelegramClientFactory,
    ) -> None:
        """Cleanup не удаляет symlink и логирует предупреждение."""
        with patch("os.path.exists", return_value=True), \
             patch("os.path.islink", return_value=True), \
             patch("os.remove") as mock_remove:
            factory.cleanup("/tmp/symlink_session.session")
            mock_remove.assert_not_called()

    def test_client_factory_cleanup_removes_regular_file(
        self,
        factory: TelegramClientFactory,
    ) -> None:
        """Cleanup удаляет обычный файл (не symlink)."""
        with patch("os.path.exists", return_value=True), \
             patch("os.path.islink", return_value=False), \
             patch("os.remove") as mock_remove:
            factory.cleanup("/tmp/regular_session.session")
            mock_remove.assert_called_once_with("/tmp/regular_session.session")
