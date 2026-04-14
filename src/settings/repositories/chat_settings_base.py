"""
Базовый репозиторий для CRUD операций с настройками чатов.

Выделен из chat_settings.py для уменьшения размера модуля.
"""

import logging
from typing import List, Optional

import asyncpg

from ...models.data_models import ChatSetting
from ...models.sql import (
    SQL_DELETE_CHAT_SETTING,
    SQL_GET_ALL_CHAT_SETTINGS,
    SQL_GET_CHAT_SETTING,
    SQL_INSERT_CHAT_SETTING,
)

logger = logging.getLogger(__name__)


class ChatSettingsBaseRepository:
    """Базовый репозиторий для CRUD операций с чатами."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        """
        Инициализация репозитория.

        Args:
            pool: Пул соединений БД.
        """
        self._pool = pool

    async def upsert(
        self,
        chat_id: int,
        title: Optional[str] = None,
        is_monitored: bool = True,
        summary_enabled: bool = True,
        custom_prompt: Optional[str] = None,
    ) -> Optional[ChatSetting]:
        """
        Сохранить или обновить настройки чата.

        Args:
            chat_id: ID чата
            title: Заголовок чата
            is_monitored: Мониторить ли чат
            summary_enabled: Включена ли сводка
            custom_prompt: Кастомный промпт

        Returns:
            Сохранённые настройки или None.
        """
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(
                    SQL_INSERT_CHAT_SETTING,
                    chat_id, title, is_monitored, summary_enabled, custom_prompt,
                )
                if row:
                    return ChatSetting(**dict(row))
                return None
            except Exception as e:
                logger.error(f"Ошибка сохранения настроек чата {chat_id}: {e}")
                return None

    async def get(self, chat_id: int) -> Optional[ChatSetting]:
        """
        Получить настройки чата.

        Args:
            chat_id: ID чата

        Returns:
            Настройки чата или None.
        """
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(SQL_GET_CHAT_SETTING, chat_id)
                if row:
                    return ChatSetting(**dict(row))
                return None
            except Exception as e:
                logger.error(f"Ошибка получения настроек чата {chat_id}: {e}")
                return None

    async def get_all(self) -> List[ChatSetting]:
        """
        Получить настройки всех чатов.

        Returns:
            Список настроек чатов.
        """
        async with self._pool.acquire() as conn:
            try:
                rows = await conn.fetch(SQL_GET_ALL_CHAT_SETTINGS)
                return [ChatSetting(**dict(row)) for row in rows]
            except Exception as e:
                logger.error(f"Ошибка получения настроек чатов: {e}")
                return []

    async def update(
        self,
        chat_id: int,
        is_monitored: Optional[bool] = None,
        summary_enabled: Optional[bool] = None,
        custom_prompt: Optional[str] = None,
    ) -> Optional[ChatSetting]:
        """
        Частично обновить настройки чата. None = пропустить поле.

        Args:
            chat_id: ID чата
            is_monitored: Мониторить ли чат
            summary_enabled: Включена ли сводка
            custom_prompt: Кастомный промпт

        Returns:
            Обновлённые настройки или None.
        """
        async with self._pool.acquire() as conn:
            try:
                existing = await conn.fetchrow(SQL_GET_CHAT_SETTING, chat_id)
                if not existing:
                    return None

                values: list = [chat_id]
                set_clauses: list = []
                param_index = 2

                if is_monitored is not None:
                    set_clauses.append(f"is_monitored = ${param_index}")
                    values.append(is_monitored)
                    param_index += 1
                if summary_enabled is not None:
                    set_clauses.append(f"summary_enabled = ${param_index}")
                    values.append(summary_enabled)
                    param_index += 1
                if custom_prompt is not None:
                    set_clauses.append(f"custom_prompt = ${param_index}")
                    values.append(custom_prompt)
                    param_index += 1

                if not set_clauses:
                    return ChatSetting(**dict(existing))

                set_sql = ", ".join(set_clauses)
                sql = f"UPDATE chat_settings SET {set_sql} WHERE chat_id = $1 RETURNING *"

                row = await conn.fetchrow(sql, *values)
                if row:
                    return ChatSetting(**dict(row))
                return None
            except Exception as e:
                logger.error(f"Ошибка обновления настроек чата {chat_id}: {e}")
                return None

    async def delete(self, chat_id: int) -> bool:
        """
        Удалить настройки чата.

        Args:
            chat_id: ID чата

        Returns:
            True если успешно.
        """
        async with self._pool.acquire() as conn:
            try:
                await conn.execute(SQL_DELETE_CHAT_SETTING, chat_id)
                return True
            except Exception as e:
                logger.error(f"Ошибка удаления настроек чата {chat_id}: {e}")
                return False
