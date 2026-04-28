"""
Фабрика создания авторизованного TelegramClient из DB-backed сессии.

Использует EncryptionService для расшифровки session_data
и SecureSessionFileService для создания временных файлов.
"""

import logging
import os

from telethon import TelegramClient

from src.config import Settings
from src.infrastructure.exceptions import (
    SessionDecryptionError,
    SessionNotAuthorizedError,
    SessionNotConfiguredError,
)
from src.infrastructure.services.secure_session_file_service import (
    SecureSessionFileService,
)
from src.infrastructure.services.session_decryption_service import (
    SessionDecryptionService,
)
from src.settings.repositories.encryption_settings import (
    EncryptionKeyMismatchError,
    EncryptionService,
)
from src.settings.repositories.telegram_auth import TelegramAuthRepository

logger = logging.getLogger(__name__)


class TelegramClientFactory:
    """Фабрика для создания авторизованного TelegramClient из DB-backed session_data."""

    def __init__(
        self,
        telegram_auth_repo: TelegramAuthRepository,
        settings: Settings,
        encryption_service: EncryptionService | None = None,
    ) -> None:
        self._repo = telegram_auth_repo
        self._settings = settings
        self._encryption_service = encryption_service

    def _decrypt(self, session_data: bytes) -> bytes:
        """Расшифровать session_data через EncryptionService."""
        if SessionDecryptionService.is_encrypted(session_data):
            if not self._encryption_service:
                raise SessionDecryptionError()
            try:
                return self._encryption_service.decrypt(session_data)
            except EncryptionKeyMismatchError as e:
                logger.warning("Ключ шифрования не совпадает: %s", type(e).__name__)
                raise SessionDecryptionError() from e
            except Exception as e:
                logger.warning("Ошибка расшифровки session_data: %s", type(e).__name__)
                raise SessionDecryptionError() from e
        return session_data

    async def _create_temp_session(self, decrypted: bytes) -> str:
        """Создать temp file через SecureSessionFileService."""
        return await SecureSessionFileService.create_temp_session_file(decrypted)

    async def create_client(self) -> tuple[TelegramClient, str]:
        """
        Создать авторизованный TelegramClient из session_data в БД.

        Returns:
            tuple[TelegramClient, session_file_path] — клиент и путь к tempfile

        Raises:
            SessionNotConfiguredError: session_data отсутствует
            SessionDecryptionError: ошибка расшифровки
        """
        session_data = await self._repo.get_session_data()
        if not session_data:
            raise SessionNotConfiguredError()

        decrypted = self._decrypt(session_data)
        session_file_path = await self._create_temp_session(decrypted)

        try:
            client = TelegramClient(
                session_file_path,
                self._settings.tg_api_id,
                self._settings.tg_api_hash,
            )
        except Exception as e:
            logger.warning("Ошибка создания TelegramClient: %s", type(e).__name__)
            self.cleanup(session_file_path)
            raise

        return client, session_file_path

    async def connect_client(self, client: TelegramClient) -> None:
        """
        Подключить и проверить авторизацию.

        Raises:
            SessionNotAuthorizedError: клиент не авторизован
        """
        await client.connect()
        if not await client.is_user_authorized():
            raise SessionNotAuthorizedError()

    def cleanup(self, session_file_path: str) -> None:
        """Удалить temp session file."""
        try:
            if os.path.exists(session_file_path):
                if os.path.islink(session_file_path):
                    logger.warning(
                        "Symlink detected в session file: %s", session_file_path
                    )
                    return
                os.remove(session_file_path)
        except OSError:
            logger.warning(
                "Не удалось удалить временный файл сессии: %s", session_file_path
            )
