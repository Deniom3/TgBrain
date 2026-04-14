"""
SessionLifecycleManager — управление жизненным циклом сессии Telegram.

SECURITY:
- Все session_data шифруются перед записью в БД
- Временные файлы создаются с правами 600
- Пути к файлам не логируются
"""

import logging
import os
from typing import Optional

from telethon import TelegramClient

from ..config import Settings
from .session_manager import SessionManager
from .telegram_connection import TelegramConnection

logger = logging.getLogger(__name__)


class SessionLifecycleManager:
    """
    Управление жизненным циклом сессии Telegram.

    Отвечает за:
    - Загрузку сессии из БД и расшифровку
    - Создание временного файла сессии
    - Подключение/отключение от Telegram
    - Очистку orphaned файлов
    - Мягкую перезагрузку сессии
    """

    def __init__(
        self,
        config: Settings,
        session_manager: SessionManager,
        telegram_connection: TelegramConnection
    ):
        self.config = config
        self.session_manager = session_manager
        self.telegram_connection = telegram_connection
        self._temp_session_file: Optional[str] = None

    async def load_session(self) -> bool:
        """
        Загрузка сессии из БД и подготовка к подключению.

        Returns:
            True если сессия успешно загружена
        """
        session_data = await self.session_manager.load_session_data()
        if not session_data:
            logger.error("session_data не найдена в БД")
            return False

        decrypted_data = await self.session_manager.decrypt_session_data(session_data)

        temp_file_path = await self.session_manager.create_temp_session_file(decrypted_data)
        self._temp_session_file = temp_file_path

        logger.info("Сессия загружена из БД")
        return True

    async def connect(self) -> bool:
        """
        Подключение к Telegram.

        Returns:
            True если подключение успешно
        """
        if not self._temp_session_file:
            logger.error("Временный файл сессии не создан")
            return False

        connected = await self.telegram_connection.connect()
        if not connected:
            logger.error("Не удалось подключиться к Telegram")
            return False

        logger.info("Подключение к Telegram установлено")
        return True

    async def disconnect(self) -> None:
        """Отключение от Telegram."""
        if self.telegram_connection:
            await self.telegram_connection.disconnect()
            logger.info("Отключение от Telegram выполнено")

    async def cleanup(self) -> None:
        """Очистка временного файла сессии."""
        if self._temp_session_file:
            try:
                os.unlink(self._temp_session_file)
                logger.debug("Временный файл сессии удалён")
            except FileNotFoundError:
                pass
            except Exception as e:
                logger.error(f"Ошибка удаления временного файла: {e}")
            self._temp_session_file = None

    async def reload_session(self) -> bool:
        """
        Мягкая перезагрузка сессии Telegram.

        SECURITY:
        - Атомарное удаление старого файла через os.unlink()
        - Использует безопасное создание файла
        - Не логирует пути к файлам

        Returns:
            True если сессия успешно обновлена и авторизована
        """
        logger.info("🔄 Мягкая перезагрузка сессии Telegram...")

        try:
            decrypted_data = await self.session_manager.reload_session()
            if not decrypted_data:
                logger.error("Не удалось перезагрузить сессию")
                return False

            if self._temp_session_file:
                try:
                    os.unlink(self._temp_session_file)
                    logger.debug("✅ Старый файл удалён")
                except FileNotFoundError:
                    pass
                except Exception as e:
                    logger.error(f"Ошибка удаления старого файла: {e}")
                    return False
                self._temp_session_file = None

            temp_file_path = await self.session_manager.create_temp_session_file(decrypted_data)
            self._temp_session_file = temp_file_path

            await self.telegram_connection.disconnect()

            connected = await self.telegram_connection.connect()
            if not connected:
                return False

            logger.info("✅ Сессия успешно обновлена")
            return True

        except Exception as e:
            logger.error(f"Ошибка перезагрузки сессии: {e}", exc_info=True)
            return False

    def get_client(self) -> Optional[TelegramClient]:
        """Получить клиент Telegram."""
        return self.telegram_connection.get_client()

    def is_connected(self) -> bool:
        """Проверка подключения к Telegram."""
        return self.telegram_connection.is_connected()

    def _get_temp_file_path(self) -> Optional[str]:
        """
        Получить путь к временному файлу сессии (private).

        SECURITY: ⚠️ Только для внутреннего использования!
        Не логировать и не передавать наружу.

        Returns:
            Путь к временному файлу или None.
        """
        return self._temp_session_file

    def set_temp_session_file(self, temp_file_path: str) -> None:
        """
        Установить временный файл сессии.

        Args:
            temp_file_path: Путь к временному файлу сессии.
        """
        self._temp_session_file = temp_file_path
