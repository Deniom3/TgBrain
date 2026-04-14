"""
Репозиторий для управления LLM провайдерами.
"""

import logging
from typing import List, Optional

import asyncpg

from ...models.data_models import LLMProvider
from ...models.sql import (
    SQL_INSERT_LLM_PROVIDER,
    SQL_GET_LLM_PROVIDER,
    SQL_GET_ALL_LLM_PROVIDERS,
    SQL_GET_ACTIVE_LLM_PROVIDER,
    SQL_UPDATE_LLM_PROVIDER,
    SQL_SET_ACTIVE_PROVIDER,
    SQL_DELETE_LLM_PROVIDER,
)

logger = logging.getLogger(__name__)


class LLMProvidersRepository:
    """Репозиторий для управления LLM провайдерами."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        """
        Инициализировать репозиторий.

        Args:
            pool: Пул подключений к БД.
        """
        self._pool = pool

    async def upsert(
        self,
        name: str,
        is_active: bool = False,
        api_key: Optional[str] = None,
        base_url: str = "",
        model: str = "",
        is_enabled: bool = True,
        priority: int = 0,
        description: Optional[str] = None,
    ) -> Optional[LLMProvider]:
        """
        Сохранить или обновить настройки провайдера.

        Args:
            name: Название провайдера
            is_active: Активен ли провайдер
            api_key: API ключ
            base_url: Базовый URL
            model: Модель
            is_enabled: Включён ли провайдер
            priority: Приоритет
            description: Описание

        Returns:
            Сохранённые настройки или None.
        """
        async with self._pool.acquire() as conn:
            try:
                # Сначала снимаем флаг active со всех если этот активный
                if is_active:
                    await conn.execute(SQL_SET_ACTIVE_PROVIDER, -1)  # dummy value

                row = await conn.fetchrow(
                    SQL_INSERT_LLM_PROVIDER,
                    name, is_active, api_key, base_url, model, is_enabled, priority, description,
                )
                if row:
                    return LLMProvider(**dict(row))
                return None
            except Exception as e:
                logger.error(f"Ошибка сохранения провайдера {name}: {e}")
                return None

    async def get(self, name: str) -> Optional[LLMProvider]:
        """
        Получить настройки провайдера.

        Args:
            name: Название провайдера

        Returns:
            Настройки провайдера или None.
        """
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(SQL_GET_LLM_PROVIDER, name)
                if row:
                    return LLMProvider(**dict(row))
                return None
            except Exception as e:
                logger.error(f"Ошибка получения провайдера {name}: {e}")
                return None

    async def get_all(self) -> List[LLMProvider]:
        """
        Получить настройки всех провайдеров.

        Returns:
            Список настроек провайдеров.
        """
        async with self._pool.acquire() as conn:
            try:
                rows = await conn.fetch(SQL_GET_ALL_LLM_PROVIDERS)
                return [LLMProvider(**dict(row)) for row in rows]
            except Exception as e:
                logger.error(f"Ошибка получения провайдеров: {e}")
                return []

    async def get_active(self) -> Optional[LLMProvider]:
        """
        Получить активный провайдер.

        Returns:
            Настройки активного провайдера или None.
        """
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(SQL_GET_ACTIVE_LLM_PROVIDER)
                if row:
                    return LLMProvider(**dict(row))
                return None
            except Exception as e:
                logger.error(f"Ошибка получения активного провайдера: {e}")
                return None

    async def update(
        self,
        name: str,
        is_active: bool,
        api_key: Optional[str] = None,
        base_url: str = "",
        model: str = "",
        is_enabled: bool = True,
        priority: int = 0,
        description: Optional[str] = None,
    ) -> Optional[LLMProvider]:
        """
        Обновить настройки провайдера.

        Args:
            name: Название провайдера
            is_active: Активен ли провайдер
            api_key: API ключ
            base_url: Базовый URL
            model: Модель
            is_enabled: Включён ли провайдер
            priority: Приоритет
            description: Описание

        Returns:
            Обновлённые настройки или None.
        """
        async with self._pool.acquire() as conn:
            try:
                # Если устанавливаем active, снимаем со всех остальных
                if is_active:
                    await conn.execute(SQL_SET_ACTIVE_PROVIDER, -1)

                row = await conn.fetchrow(
                    SQL_UPDATE_LLM_PROVIDER,
                    name, is_active, api_key, base_url, model, is_enabled, priority, description,
                )
                if row:
                    return LLMProvider(**dict(row))
                return None
            except Exception as e:
                logger.error(f"Ошибка обновления провайдера {name}: {e}")
                return None

    async def set_active(self, name: str) -> bool:
        """
        Установить провайдер как активный.

        Args:
            name: Название провайдера

        Returns:
            True если успешно.
        """
        async with self._pool.acquire() as conn:
            try:
                # Снимаем active со всех
                await conn.execute(SQL_SET_ACTIVE_PROVIDER, -1)
                # Устанавливаем active для указанного
                await conn.execute(
                    "UPDATE llm_providers SET is_active = TRUE WHERE name = $1",
                    name
                )
                return True
            except Exception as e:
                logger.error(f"Ошибка установки активного провайдера: {e}")
                return False

    async def delete(self, name: str) -> bool:
        """
        Удалить провайдер.

        Args:
            name: Название провайдера

        Returns:
            True если успешно.
        """
        async with self._pool.acquire() as conn:
            try:
                await conn.execute(SQL_DELETE_LLM_PROVIDER, name)
                return True
            except Exception as e:
                logger.error(f"Ошибка удаления провайдера {name}: {e}")
                return False

