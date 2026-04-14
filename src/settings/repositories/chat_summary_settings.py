"""
Репозиторий для управления summary настройками чатов.

Выделен из chat_settings.py для уменьшения размера модуля.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import asyncpg

from ...models.data_models import ChatSetting
from ...models.sql import (
    SQL_CLEAR_CUSTOM_PROMPT,
    SQL_CLEAR_SUMMARY_SCHEDULE,
    SQL_DISABLE_SUMMARY,
    SQL_ENABLE_SUMMARY,
    SQL_GET_CHATS_WITH_SCHEDULE,
    SQL_GET_CUSTOM_PROMPT,
    SQL_GET_ENABLED_SUMMARY_CHAT_IDS,
    SQL_GET_SUMMARY_SETTINGS,
    SQL_SET_CUSTOM_PROMPT,
    SQL_SET_SUMMARY_PERIOD,
    SQL_SET_SUMMARY_SCHEDULE,
    SQL_TOGGLE_SUMMARY,
    SQL_UPDATE_NEXT_SCHEDULE_RUN,
)
from .exceptions import ChatSettingsStorageError

logger = logging.getLogger(__name__)


class ChatSummarySettingsRepository:
    """Репозиторий для управления summary настройками чатов."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        """
        Инициализировать репозиторий.

        Args:
            pool: Pool соединений с БД.
        """
        self._pool = pool

    async def enable_summary(self, chat_id: int) -> Optional[ChatSetting]:
        """Включить генерацию summary для чата."""
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(SQL_ENABLE_SUMMARY, chat_id)
                if row:
                    return ChatSetting(**dict(row))
                return None
            except Exception as e:
                logger.error(f"Ошибка включения summary для чата {chat_id}: {e}")
                return None

    async def disable_summary(self, chat_id: int) -> Optional[ChatSetting]:
        """Отключить генерацию summary для чата."""
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(SQL_DISABLE_SUMMARY, chat_id)
                if row:
                    return ChatSetting(**dict(row))
                return None
            except Exception as e:
                logger.error(f"Ошибка отключения summary для чата {chat_id}: {e}")
                return None

    async def toggle_summary(self, chat_id: int) -> Optional[ChatSetting]:
        """Переключить статус генерации summary для чата."""
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(SQL_TOGGLE_SUMMARY, chat_id)
                if row:
                    return ChatSetting(**dict(row))
                return None
            except Exception as e:
                logger.error(f"Ошибка переключения summary для чата {chat_id}: {e}")
                return None

    async def set_summary_period(
        self,
        chat_id: int,
        minutes: int
    ) -> Optional[ChatSetting]:
        """Установить период сбора сообщений для summary."""
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(
                    SQL_SET_SUMMARY_PERIOD,
                    chat_id, minutes
                )
                if row:
                    return ChatSetting(**dict(row))
                return None
            except Exception as e:
                logger.error(f"Ошибка установки периода summary для чата {chat_id}: {e}")
                return None

    async def set_summary_schedule(
        self,
        chat_id: int,
        schedule: str
    ) -> Optional[ChatSetting]:
        """Установить расписание генерации summary."""
        from ...schedule.helpers import calculate_next_run

        async with self._pool.acquire() as conn:
            try:
                next_run = calculate_next_run(schedule)
                if next_run.tzinfo is not None:
                    next_run = next_run.replace(tzinfo=None)
                row = await conn.fetchrow(
                    SQL_SET_SUMMARY_SCHEDULE,
                    chat_id, schedule, next_run
                )
                if row:
                    return ChatSetting(**dict(row))
                return None
            except Exception as e:
                logger.error(f"Ошибка установки расписания summary для чата {chat_id}: {e}")
                return None

    async def clear_summary_schedule(self, chat_id: int) -> Optional[ChatSetting]:
        """Отключить расписание генерации summary."""
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(SQL_CLEAR_SUMMARY_SCHEDULE, chat_id)
                if row:
                    return ChatSetting(**dict(row))
                return None
            except Exception as e:
                logger.error(f"Ошибка очистки расписания summary для чата {chat_id}: {e}")
                return None

    async def get_summary_settings(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """Получить настройки summary для чата."""
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(SQL_GET_SUMMARY_SETTINGS, chat_id)
                if row:
                    return dict(row)
                return None
            except Exception as e:
                logger.error(f"Ошибка получения настроек summary для чата {chat_id}: {e}")
                return None

    async def set_custom_prompt(
        self,
        chat_id: int,
        prompt: str
    ) -> Optional[ChatSetting]:
        """Установить кастомный промпт для summary."""
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(
                    SQL_SET_CUSTOM_PROMPT,
                    chat_id, prompt
                )
                if row:
                    return ChatSetting(**dict(row))
                return None
            except Exception as e:
                logger.error(f"Ошибка установки кастомного промпта для чата {chat_id}: {e}")
                return None

    async def get_custom_prompt(self, chat_id: int) -> Optional[str]:
        """Получить кастомный промпт для чата."""
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(SQL_GET_CUSTOM_PROMPT, chat_id)
                if row and row['custom_prompt']:
                    return row['custom_prompt']
                return None
            except Exception as e:
                logger.error(f"Ошибка получения кастомного промпта для чата {chat_id}: {e}")
                return None

    async def clear_custom_prompt(self, chat_id: int) -> Optional[ChatSetting]:
        """Сбросить кастомный промпт на дефолтный."""
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(SQL_CLEAR_CUSTOM_PROMPT, chat_id)
                if row:
                    return ChatSetting(**dict(row))
                return None
            except Exception as e:
                logger.error(f"Ошибка очистки кастомного промпта для чата {chat_id}: {e}")
                return None

    async def get_chats_with_schedule(self) -> list[ChatSetting]:
        """
        Получить все чаты с активным расписанием, требующие обработки.

        Returns:
            Список ChatSetting с summary_schedule и next_schedule_run <= now.
        """
        async with self._pool.acquire() as conn:
            try:
                rows = await conn.fetch(SQL_GET_CHATS_WITH_SCHEDULE)
                return [ChatSetting(**dict(row)) for row in rows]
            except Exception as e:
                logger.error(f"Ошибка получения чатов с расписанием: {e}")
                return []

    async def update_next_schedule_run(
        self,
        chat_id: int,
        next_run: Any
    ) -> Optional[ChatSetting]:
        """
        Обновить следующее время запуска расписания для чата.

        Args:
            chat_id: ID чата.
            next_run: Следующее время запуска в UTC.

        Returns:
            Обновлённый ChatSetting или None.
        """
        async with self._pool.acquire() as conn:
            try:
                next_run_value = next_run
                if isinstance(next_run_value, datetime) and next_run_value.tzinfo is not None:
                    next_run_value = next_run_value.replace(tzinfo=None)
                row = await conn.fetchrow(
                    SQL_UPDATE_NEXT_SCHEDULE_RUN,
                    chat_id,
                    next_run_value,
                )
                if row:
                    return ChatSetting(**dict(row))
                return None
            except Exception as e:
                logger.error(
                    f"Ошибка обновления next_schedule_run для чата {chat_id}: {e}",
                    exc_info=True,
                )
                return None

    async def get_enabled_summary_chat_ids(self) -> List[int]:
        """
        Получить ID чатов с включённой генерацией summary.

        Returns:
            Список chat_id где summary_enabled = TRUE.

        Raises:
            ChatSettingsStorageError: При ошибке БД.
        """
        async with self._pool.acquire() as conn:
            try:
                rows = await conn.fetch(SQL_GET_ENABLED_SUMMARY_CHAT_IDS)
                return [row["chat_id"] for row in rows]
            except asyncpg.PostgresError as e:
                logger.error("Ошибка получения чатов с включённым summary", exc_info=True)
                raise ChatSettingsStorageError("Ошибка получения чатов с включённым summary") from e
