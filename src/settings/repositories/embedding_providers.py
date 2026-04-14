"""
Репозиторий для управления провайдерами эмбеддингов.
"""

import logging
from typing import List, Optional

import asyncpg

from ...models.data_models import EmbeddingProvider
from ...models.sql import (
    SQL_INSERT_EMBEDDING_PROVIDER,
    SQL_GET_EMBEDDING_PROVIDER,
    SQL_GET_ALL_EMBEDDING_PROVIDERS,
    SQL_GET_ACTIVE_EMBEDDING_PROVIDER,
    SQL_UPDATE_EMBEDDING_PROVIDER,
    SQL_SET_ACTIVE_EMBEDDING_PROVIDER,
    SQL_DELETE_EMBEDDING_PROVIDER,
)

logger = logging.getLogger(__name__)


class EmbeddingProvidersRepository:
    """Репозиторий для управления провайдерами эмбеддингов."""

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
        embedding_dim: int = 768,
        max_retries: int = 3,
        timeout: int = 30,
        normalize: bool = False,
    ) -> Optional[EmbeddingProvider]:
        """
        Сохранить или обновить настройки провайдера эмбеддингов.

        Args:
            name: Название провайдера
            is_active: Активен ли провайдер
            api_key: API ключ (опционально для локальных провайдеров)
            base_url: Базовый URL
            model: Модель
            is_enabled: Включён ли провайдер
            priority: Приоритет
            description: Описание
            embedding_dim: Размерность вектора эмбеддинга
            max_retries: Максимальное количество попыток
            timeout: Таймаут запроса в секундах
            normalize: Нормализовать векторы

        Returns:
            Сохранённые настройки или None.
        """
        async with self._pool.acquire() as conn:
            try:
                # Сначала снимаем флаг active со всех если этот активный
                if is_active:
                    await conn.execute(SQL_SET_ACTIVE_EMBEDDING_PROVIDER, -1)

                row = await conn.fetchrow(
                    SQL_INSERT_EMBEDDING_PROVIDER,
                    name, is_active, api_key, base_url, model, is_enabled, priority, description,
                    embedding_dim, max_retries, timeout, normalize,
                )
                if row:
                    return EmbeddingProvider(**dict(row))
                return None
            except Exception as e:
                logger.error(f"Ошибка сохранения провайдера эмбеддингов {name}: {e}")
                return None

    async def get(self, name: str) -> Optional[EmbeddingProvider]:
        """
        Получить настройки провайдера эмбеддингов.

        Args:
            name: Название провайдера

        Returns:
            Настройки провайдера или None.
        """
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(SQL_GET_EMBEDDING_PROVIDER, name)
                if row:
                    return EmbeddingProvider(**dict(row))
                return None
            except Exception as e:
                logger.error(f"Ошибка получения провайдера эмбеддингов {name}: {e}")
                return None

    async def get_all(self) -> List[EmbeddingProvider]:
        """
        Получить настройки всех провайдеров эмбеддингов.

        Returns:
            Список настроек провайдеров.
        """
        async with self._pool.acquire() as conn:
            try:
                rows = await conn.fetch(SQL_GET_ALL_EMBEDDING_PROVIDERS)
                return [EmbeddingProvider(**dict(row)) for row in rows]
            except Exception as e:
                logger.error(f"Ошибка получения провайдеров эмбеддингов: {e}")
                return []

    async def get_active(self) -> Optional[EmbeddingProvider]:
        """
        Получить активный провайдер эмбеддингов.

        Returns:
            Настройки активного провайдера или None.
        """
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(SQL_GET_ACTIVE_EMBEDDING_PROVIDER)
                if row:
                    return EmbeddingProvider(**dict(row))
                return None
            except Exception as e:
                logger.error(f"Ошибка получения активного провайдера эмбеддингов: {e}")
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
        embedding_dim: int = 768,
        max_retries: int = 3,
        timeout: int = 30,
        normalize: bool = False,
    ) -> Optional[EmbeddingProvider]:
        """
        Обновить настройки провайдера эмбеддингов.

        Args:
            name: Название провайдера
            is_active: Активен ли провайдер
            api_key: API ключ
            base_url: Базовый URL
            model: Модель
            is_enabled: Включён ли провайдер
            priority: Приоритет
            description: Описание
            embedding_dim: Размерность вектора
            max_retries: Максимальное количество попыток
            timeout: Таймаут запроса
            normalize: Нормализовать векторы

        Returns:
            Обновлённые настройки или None.
        """
        async with self._pool.acquire() as conn:
            try:
                # Если устанавливаем active, снимаем со всех остальных
                if is_active:
                    await conn.execute(SQL_SET_ACTIVE_EMBEDDING_PROVIDER, -1)

                row = await conn.fetchrow(
                    SQL_UPDATE_EMBEDDING_PROVIDER,
                    name, is_active, api_key, base_url, model, is_enabled, priority, description,
                    embedding_dim, max_retries, timeout, normalize,
                )
                if row:
                    return EmbeddingProvider(**dict(row))
                return None
            except Exception as e:
                logger.error(f"Ошибка обновления провайдера эмбеддингов {name}: {e}")
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
                await conn.execute(SQL_SET_ACTIVE_EMBEDDING_PROVIDER, -1)
                # Устанавливаем active для указанного
                await conn.execute(
                    "UPDATE embedding_providers SET is_active = TRUE WHERE name = $1",
                    name
                )
                return True
            except Exception as e:
                logger.error(f"Ошибка установки активного провайдера эмбеддингов: {e}")
                return False

    async def delete(self, name: str) -> bool:
        """
        Удалить провайдер эмбеддингов.

        Args:
            name: Название провайдера

        Returns:
            True если успешно.
        """
        async with self._pool.acquire() as conn:
            try:
                await conn.execute(SQL_DELETE_EMBEDDING_PROVIDER, name)
                return True
            except Exception as e:
                logger.error(f"Ошибка удаления провайдера эмбеддингов {name}: {e}")
                return False

