"""
Менеджер сессий Telegram.

Управление сессионными данными, создание и очистка временных файлов.
"""

import logging
from typing import Optional

from ..config import Settings
from ..infrastructure.services import SessionDecryptionService, SecureSessionFileService
from ..settings.repositories.app_settings import AppSettingsRepository
from ..settings.repositories.encryption_settings import (
    EncryptionService,
    EncryptionKeyMismatchError,
)
from ..settings.repositories.telegram_auth import TelegramAuthRepository

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Менеджер сессий Telegram.

    Отвечает за:
    - Загрузку session_data из БД
    - Расшифрование session_data
    - Создание временных файлов сессий
    - Очистку временных файлов

    Attributes:
        config: Настройки приложения
        temp_session_file: Путь к временному файлу сессии
    """

    def __init__(
        self,
        config: Settings,
        telegram_auth_repo: TelegramAuthRepository,
        app_settings_repo: AppSettingsRepository,
    ) -> None:
        """
        Инициализировать менеджер сессий.

        Args:
            config: Настройки приложения.
            telegram_auth_repo: Репозиторий авторизации Telegram.
            app_settings_repo: Репозиторий настроек приложения.
        """
        self.config = config
        self._telegram_auth_repo = telegram_auth_repo
        self._app_settings_repo = app_settings_repo
        self.temp_session_file: Optional[str] = None
    
    async def load_session_data(self) -> Optional[bytes]:
        """
        Загрузить session_data из БД.

        Returns:
            session_data или None если не найдена.
        """
        auth = await self._telegram_auth_repo.get()

        if not auth or not auth.session_name:
            logger.error("Session name не установлен")
            return None

        session_data = await self._telegram_auth_repo.get_session_data()

        if not session_data:
            logger.error("session_data не найдена в БД")
            return None

        logger.info("session_data загружена из БД")
        return session_data
    
    async def decrypt_session_data(self, session_data: bytes) -> bytes:
        """
        Расшифровать session_data.

        SECURITY: Если данные не зашифрованы (старый формат),
        зашифровать их и сохранить в БД.

        Args:
            session_data: Данные сессии (возможно зашифрованные)

        Returns:
            Расшифрованные данные.

        Raises:
            EncryptionKeyMismatchError: Если ключ шифрования не совпадает.
            Exception: Если произошла другая ошибка расшифрования.
        """
        encryption_service = await EncryptionService.create(self._app_settings_repo)

        try:
            if SessionDecryptionService.is_encrypted(session_data):
                try:
                    decrypted = encryption_service.decrypt(session_data)
                    logger.info("Session data расшифрованы")
                    return decrypted
                except EncryptionKeyMismatchError:
                    logger.error(
                        "Ключ шифрования не совпадает. "
                        "Сессия была зашифрована другим ключом. "
                        "Требуется повторная авторизация через QR-код."
                    )
                    raise
            else:
                logger.info("Session data не зашифрованы (старый формат), миграция...")
                encrypted = encryption_service.encrypt(session_data)
                await self._save_encrypted_session_data(encrypted)
                logger.info("Session data зашифрованы и сохранены в БД")
                return session_data
        except EncryptionKeyMismatchError:
            raise
        except Exception as e:
            logger.error(f"Критическая ошибка расшифрования: {type(e).__name__}: {e}")
            raise
    
    async def _save_encrypted_session_data(self, encrypted_data: bytes) -> None:
        """
        Сохранить зашифрованные session_data в БД.
        
        Args:
            encrypted_data: Зашифрованные данные сессии.
        """
        await self._telegram_auth_repo.save_session_data_v2(encrypted_data)
    
    async def create_temp_session_file(self, data: bytes) -> str:
        """
        Создать временный файл сессии.
        
        SECURITY:
        - Использует mkstemp() для атомарного создания
        - Устанавливает права 600 (только владелец)
        
        Args:
            data: Данные сессии для записи.
            
        Returns:
            Путь к созданному файлу.
        """
        self.temp_session_file = await SecureSessionFileService.create_temp_session_file(data)
        logger.info("Временный файл сессии создан")
        return self.temp_session_file
    
    async def cleanup_temp_session_file(self) -> None:
        """
        Очистить временный файл сессии.
        
        SECURITY: Проверяет что файл удалён, логирует ошибки.
        """
        if self.temp_session_file:
            deleted = await SecureSessionFileService.delete_temp_session_file(
                self.temp_session_file
            )
            if deleted:
                logger.info("Временные файлы очищены")
            else:
                logger.warning("Временный файл не найден (уже удалён?)")
            self.temp_session_file = None
    
    def has_temp_session_file(self) -> bool:
        """
        Проверить наличие временного файла сессии.
        
        Returns:
            True если файл существует.
        """
        if self.temp_session_file:
            return SecureSessionFileService.exists(self.temp_session_file)
        return False
    
    async def reload_session(self) -> Optional[bytes]:
        """
        Перезагрузить сессию из БД.
        
        Returns:
            Расшифрованные session_data или None.
        """
        session_data = await self.load_session_data()
        if not session_data:
            return None
        
        return await self.decrypt_session_data(session_data)
