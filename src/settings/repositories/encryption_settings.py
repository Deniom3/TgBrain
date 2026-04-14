"""
Репозиторий для управления ключами шифрования сессий.

Использует Fernet (symmetric encryption) для шифрования session_data.
Ключ хранится в БД в таблице app_settings с флагом is_sensitive=True.
"""

import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from .app_settings import AppSettingsRepository

logger = logging.getLogger(__name__)

ENCRYPTION_KEY_KEY = "session.encryption_key"


class EncryptionKeyError(Exception):
    """Ошибка операции с ключом шифрования."""
    pass


class EncryptionKeyMismatchError(EncryptionKeyError):
    """Ошибка несоответствия ключа шифрования (InvalidToken)."""
    pass


class EncryptionService:
    """
    Сервис для шифрования/дешифрования данных сессии.

    Использует Fernet (AES-128-CBC) для симметричного шифрования.
    Ключ генерируется при первом запуске и сохраняется в БД.
    """

    def __init__(self, cipher: Optional[Fernet] = None):
        """
        Инициализация сервиса.

        Args:
            cipher: Fernet cipher для шифрования/дешифрования.
        """
        self._cipher = cipher

    @property
    def cipher(self) -> Fernet:
        """Получить Fernet cipher."""
        if self._cipher is None:
            raise EncryptionKeyError("Шифрование не инициализировано")
        return self._cipher

    @classmethod
    async def create(
        cls,
        app_settings_repo: AppSettingsRepository,
    ) -> "EncryptionService":
        """
        Создать и инициализировать сервис шифрования.

        Args:
            app_settings_repo: Репозиторий настроек приложения.

        Returns:
            Инициализированный EncryptionService.

        Raises:
            EncryptionKeyError: Если не удалось получить/создать ключ.
        """
        setting = await app_settings_repo.get(key=ENCRYPTION_KEY_KEY)

        if setting and setting.value:
            logger.debug("Ключ шифрования загружен из БД")
            key_bytes = setting.value.encode()
        else:
            logger.info("Генерация нового ключа шифрования...")
            key_bytes = Fernet.generate_key()
            key_str = key_bytes.decode()

            saved = await app_settings_repo.upsert(
                key=ENCRYPTION_KEY_KEY,
                value=key_str,
                value_type="string",
                description="Ключ шифрования для session_data (Fernet)",
                is_sensitive=True,
            )

            if not saved:
                raise EncryptionKeyError("Не удалось сохранить ключ шифрования в БД")

            logger.info("Ключ шифрования сгенерирован и сохранён в БД")

        cipher = Fernet(key_bytes)
        return cls(cipher)

    def encrypt(self, data: bytes) -> bytes:
        """
        Зашифровать данные.

        Args:
            data: Данные для шифрования

        Returns:
            Зашифрованные данные.

        Raises:
            EncryptionKeyError: Если сервис не инициализирован.
        """
        try:
            return self.cipher.encrypt(data)
        except Exception as e:
            raise EncryptionKeyError(f"Ошибка шифрования: {e}") from e

    def decrypt(self, encrypted_data: bytes) -> bytes:
        """
        Расшифровать данные.

        Args:
            encrypted_data: Зашифрованные данные

        Returns:
            Расшифрованные данные.

        Raises:
            EncryptionKeyMismatchError: Если ключ не совпадает (InvalidToken).
            EncryptionKeyError: Если сервис не инициализирован или другая ошибка.
        """
        try:
            return self.cipher.decrypt(encrypted_data)
        except InvalidToken as e:
            logger.error("InvalidToken: Ключ шифрования не совпадает")
            logger.debug(
                "Размер данных: %d байт. "
                "Возможные причины InvalidToken: "
                "1) Ключ в БД изменился (пересоздали БД или изменили ENCRYPTION_KEY), "
                "2) Данные повреждены, "
                "3) Данные не зашифрованы (старый формат)",
                len(encrypted_data),
            )
            raise EncryptionKeyMismatchError(
                "Ключ шифрования не совпадает. Требуется повторная авторизация через QR-код."
            ) from e
        except Exception as e:
            logger.error("Неожиданная ошибка дешифрования: %s", type(e).__name__, exc_info=True)
            raise EncryptionKeyError("Ошибка дешифрования данных сессии") from e

    async def migrate_unencrypted_data(
        self,
        session_data: bytes,
    ) -> bytes:
        """
        Миграция незашифрованных данных в зашифрованные.

        Если данные не зашифрованы (старый формат), зашифровать их.
        Если уже зашифрованы — вернуть как есть.

        Args:
            session_data: Данные сессии (возможно незашифрованные)

        Returns:
            Зашифрованные данные сессии.
        """
        try:
            encrypted_data = self.encrypt(session_data)
            logger.info("✅ Незашифрованные данные мигрированы в зашифрованный формат")
            return encrypted_data
        except Exception as e:
            logger.error("Ошибка миграции данных: %s", e, exc_info=True)
            raise


async def get_encryption_service(
    app_settings_repo: AppSettingsRepository,
) -> EncryptionService:
    """
    Получить сервис шифрования.

    Args:
        app_settings_repo: Репозиторий настроек приложения.

    Returns:
        Инициализированный EncryptionService.

    Raises:
        EncryptionKeyError: Если не удалось инициализировать сервис.
    """
    return await EncryptionService.create(app_settings_repo)
