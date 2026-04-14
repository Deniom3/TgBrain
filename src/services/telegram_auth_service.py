"""
Telegram Auth Service — сервисный слой для управления авторизацией Telegram.

Обеспечивает разделение между API слоем и репозиторием.
"""

import logging
from typing import Optional

from ..domain.models.auth import TelegramAuth
from ..domain.value_objects import SessionData
from ..settings.repositories.telegram_auth import TelegramAuthRepository

logger = logging.getLogger(__name__)


class TelegramAuthService:
    """
    Сервис для управления авторизацией Telegram.

    Обеспечивает промежуточный слой между API и репозиторием.
    """

    def __init__(self, telegram_auth_repo: TelegramAuthRepository) -> None:
        """
        Инициализировать сервис.

        Args:
            telegram_auth_repo: Репозиторий для управления авторизацией.
        """
        self._telegram_auth_repo = telegram_auth_repo

    async def get_auth_data(self) -> Optional[TelegramAuth]:
        """
        Получить данные авторизации Telegram.

        Returns:
            Данные авторизации или None.
        """
        return await self._telegram_auth_repo.get()

    async def save_session_name(self, session_name: str) -> None:
        """
        Сохранить имя сессии в БД.

        Args:
            session_name: Имя сессии для сохранения.
        """
        auth = await self._telegram_auth_repo.get()

        if auth:
            await self._telegram_auth_repo.upsert(
                api_id=auth.api_id.value if auth.api_id else None,
                api_hash=auth.api_hash.value if auth.api_hash else None,
                phone_number=auth.phone_number.value if auth.phone_number else None,
                session_name=session_name,
            )
            logger.info(f"Session name сохранён в БД: {session_name}")
        else:
            logger.warning(f"Настройки Telegram не найдены в БД для сессии: {session_name}")

    async def save_session_data_vo(self, session_name: str, session_data_vo: SessionData) -> None:
        """
        Сохранить данные сессии в БД.

        Args:
            session_name: Имя сессии
            session_data_vo: Данные сессии (SessionData VO)
        """
        await self._telegram_auth_repo.save_session_data_vo(session_name, session_data_vo)
        logger.info(f"Session data сохранена в БД для {session_name}")

    async def is_session_active(self) -> bool:
        """
        Проверить наличие активной сессии.

        Returns:
            True если сессия активна.
        """
        return await self._telegram_auth_repo.is_session_active()

    async def logout(self) -> bool:
        """
        Выполнить logout (сброс сессии).

        Returns:
            True если успешно.
        """
        return await self._telegram_auth_repo.clear_session()

    async def is_configured(self) -> bool:
        """
        Проверить настроена ли авторизация.

        Returns:
            True если api_id и api_hash настроены.
        """
        return await self._telegram_auth_repo.is_configured()
