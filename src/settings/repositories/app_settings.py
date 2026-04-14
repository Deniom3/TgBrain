"""
Репозиторий для управления общими настройками приложения.
"""

import logging
from typing import Any, Dict, List, Optional

import asyncpg

from ...models.data_models import AppSetting
from ...models.sql import (
    SQL_INSERT_APP_SETTING,
    SQL_INSERT_APP_SETTING_IF_NOT_EXISTS,
    SQL_GET_APP_SETTING,
    SQL_GET_ALL_APP_SETTINGS,
    SQL_UPDATE_APP_SETTING,
    SQL_DELETE_APP_SETTING,
)

logger = logging.getLogger(__name__)


class AppSettingsRepository:
    """Репозиторий для управления общими настройками приложения."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        """
        Инициализировать репозиторий.

        Args:
            pool: Пул подключений к БД.
        """
        self._pool = pool

    async def upsert(
        self,
        key: str,
        value: Optional[str] = None,
        value_type: str = "string",
        description: Optional[str] = None,
        is_sensitive: bool = False,
    ) -> Optional[AppSetting]:
        """
        Сохранить или обновить настройку.

        Args:
            key: Ключ настройки
            value: Значение
            value_type: Тип значения
            description: Описание
            is_sensitive: Чувствительные данные

        Returns:
            Сохранённые настройки или None.
        """
        async with self._pool.acquire() as conn:
            try:
                logger.debug(
                    "Upsert настройки: key=%s, value=%s, value_type=%s, description=%s, is_sensitive=%s",
                    key, value, value_type, description, is_sensitive,
                )
                row = await conn.fetchrow(
                    SQL_INSERT_APP_SETTING,
                    key, value, value_type, description, is_sensitive,
                )
                logger.debug("Результат upsert: %s", row)
                if row:
                    return AppSetting(**dict(row))
                logger.warning("Upsert вернул None для key=%s", key)
                return None
            except Exception:
                logger.exception("Ошибка сохранения настройки %s", key)
                return None

    async def upsert_if_not_exists(
        self,
        key: str,
        value: Optional[str] = None,
        value_type: str = "string",
        description: Optional[str] = None,
        is_sensitive: bool = False,
    ) -> Optional[AppSetting]:
        """
        Сохранить настройку только если она не существует.
        Используется при инициализации для создания значений по умолчанию.

        Args:
            key: Ключ настройки
            value: Значение
            value_type: Тип значения
            description: Описание
            is_sensitive: Чувствительные данные

        Returns:
            Сохранённые настройки или None.
        """
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(
                    SQL_INSERT_APP_SETTING_IF_NOT_EXISTS,
                    key, value, value_type, description, is_sensitive,
                )
                if row:
                    return AppSetting(**dict(row))
                return None
            except Exception:
                logger.exception("Ошибка сохранения настройки %s", key)
                return None

    async def get(self, key: str) -> Optional[AppSetting]:
        """
        Получить настройку.

        Args:
            key: Ключ настройки

        Returns:
            Настройка или None.
        """
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(SQL_GET_APP_SETTING, key)
                if row:
                    return AppSetting(**dict(row))
                return None
            except Exception:
                logger.exception("Ошибка получения настройки %s", key)
                return None

    async def get_all(self) -> List[AppSetting]:
        """
        Получить все настройки.

        Returns:
            Список настроек.
        """
        async with self._pool.acquire() as conn:
            try:
                rows = await conn.fetch(SQL_GET_ALL_APP_SETTINGS)
                return [AppSetting(**dict(row)) for row in rows]
            except Exception:
                logger.exception("Ошибка получения настроек")
                return []

    async def update(self, key: str, value: Optional[str]) -> Optional[AppSetting]:
        """
        Обновить настройку.

        Args:
            key: Ключ настройки
            value: Значение

        Returns:
            Обновлённая настройка или None.
        """
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(SQL_UPDATE_APP_SETTING, key, value)
                if row:
                    return AppSetting(**dict(row))
                return None
            except Exception:
                logger.exception("Ошибка обновления настройки %s", key)
                return None

    async def delete(self, key: str) -> bool:
        """
        Удалить настройку.

        Args:
            key: Ключ настройки

        Returns:
            True если успешно.
        """
        async with self._pool.acquire() as conn:
            try:
                await conn.execute(SQL_DELETE_APP_SETTING, key)
                return True
            except Exception:
                logger.exception("Ошибка удаления настройки %s", key)
                return False

    async def get_value(self, key: str, default: Any = None) -> Any:
        """
        Получить значение настройки.

        Args:
            key: Ключ настройки
            default: Значение по умолчанию

        Returns:
            Значение настройки с приведением к типу.
        """
        setting = await self.get(key)
        if setting:
            return setting.get_typed_value()
        return default

    async def get_dict(self) -> Dict[str, Any]:
        """
        Получить все настройки как словарь.

        Returns:
            Словарь {key: typed_value}.
        """
        settings = await self.get_all()
        return {s.key: s.get_typed_value() for s in settings}
