"""
Репозиторий для массовых операций и управления мониторингом чатов.

Выделен из chat_settings.py для уменьшения размера модуля.
"""

import logging
from typing import Dict, List, Optional

import asyncpg

from ...models.data_models import ChatSetting
from ...models.sql import (
    SQL_BULK_UPSERT_CHAT_SETTINGS,
    SQL_DISABLE_CHAT_BY_ID,
    SQL_ENABLE_CHAT_BY_ID,
    SQL_GET_CHAT_SETTINGS_BY_ID,
    SQL_GET_MONITORED_CHATS,
    SQL_INSERT_CHAT_SETTING_SINGLE,
    SQL_TOGGLE_CHAT_MONITORING,
    SQL_UPDATE_CHAT_MONITORING,
)

logger = logging.getLogger(__name__)


class ChatSettingsBulkRepository:
    """Репозиторий для массовых операций с чатами."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        """
        Инициализация репозитория.

        Args:
            pool: Пул соединений БД.
        """
        self._pool = pool

    async def bulk_upsert_chat_settings(
        self,
        chats: List[Dict]
    ) -> List[ChatSetting]:
        """
        Массовое сохранение настроек чатов.

        Args:
            chats: Список словарей с ключами:
                - chat_id: int
                - title: str
                - type: str (по умолчанию 'private')
                - last_message_id: int (по умолчанию 0)
                - is_monitored: bool (по умолчанию True)
                - summary_enabled: bool (по умолчанию True)
                - filter_bots: bool (по умолчанию True)
                - filter_actions: bool (по умолчанию True)
                - filter_min_length: int (по умолчанию 15)
                - filter_ads: bool (по умолчанию True)

        Returns:
            Список сохранённых настроек.
        """
        async with self._pool.acquire() as conn:
            try:
                if not chats:
                    return []

                chat_ids = [c["chat_id"] for c in chats]
                titles = [c.get("title", "") for c in chats]
                types = [c.get("type", "private") for c in chats]
                last_message_ids = [c.get("last_message_id", 0) for c in chats]
                is_monitored_list = [c.get("is_monitored", True) for c in chats]
                summary_enabled_list = [c.get("summary_enabled", True) for c in chats]
                filter_bots_list = [c.get("filter_bots", True) for c in chats]
                filter_actions_list = [c.get("filter_actions", True) for c in chats]
                filter_min_length_list = [c.get("filter_min_length", 15) for c in chats]
                filter_ads_list = [c.get("filter_ads", True) for c in chats]

                rows = await conn.fetch(
                    SQL_BULK_UPSERT_CHAT_SETTINGS,
                    chat_ids,
                    titles,
                    types,
                    last_message_ids,
                    is_monitored_list,
                    summary_enabled_list,
                    filter_bots_list,
                    filter_actions_list,
                    filter_min_length_list,
                    filter_ads_list,
                )
                return [ChatSetting(**dict(row)) for row in rows]
            except Exception as e:
                logger.error(f"Ошибка массового сохранения настроек чатов: {e}")
                return []

    async def get_monitored_chats(self) -> List[ChatSetting]:
        """
        Получить настройки monitored чатов.

        Returns:
            Список настроек monitored чатов.
        """
        async with self._pool.acquire() as conn:
            try:
                rows = await conn.fetch(SQL_GET_MONITORED_CHATS)
                return [ChatSetting(**dict(row)) for row in rows]
            except Exception as e:
                logger.error(f"Ошибка получения monitored чатов: {e}")
                return []

    async def get_chat_settings_by_id(self, chat_id: int) -> Optional[ChatSetting]:
        """
        Получить настройки чата по ID.

        Args:
            chat_id: ID чата

        Returns:
            Настройки чата или None.
        """
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(SQL_GET_CHAT_SETTINGS_BY_ID, chat_id)
                if row:
                    return ChatSetting(**dict(row))
                return None
            except Exception as e:
                logger.error(f"Ошибка получения настроек чата {chat_id}: {e}")
                return None

    async def set_chat_monitoring(
        self,
        chat_id: int,
        is_monitored: bool
    ) -> Optional[ChatSetting]:
        """
        Включить/отключить мониторинг чата.

        Args:
            chat_id: ID чата
            is_monitored: Включить (True) или отключить (False)

        Returns:
            Обновлённые настройки или None.
        """
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(
                    SQL_UPDATE_CHAT_MONITORING,
                    chat_id, is_monitored,
                )
                if row:
                    return ChatSetting(**dict(row))
                return None
            except Exception as e:
                logger.error(f"Ошибка обновления мониторинга чата {chat_id}: {e}")
                return None

    async def toggle_chat_monitoring(self, chat_id: int) -> Optional[ChatSetting]:
        """
        Переключить состояние мониторинга чата.

        Args:
            chat_id: ID чата

        Returns:
            Обновлённые настройки или None.
        """
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(SQL_TOGGLE_CHAT_MONITORING, chat_id)
                if row:
                    return ChatSetting(**dict(row))
                return None
            except Exception as e:
                logger.error(f"Ошибка переключения мониторинга чата {chat_id}: {e}")
                return None

    async def enable_chat(self, chat_id: int) -> Optional[ChatSetting]:
        """
        Включить мониторинг чата.

        Args:
            chat_id: ID чата

        Returns:
            Обновлённые настройки или None.
        """
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(SQL_ENABLE_CHAT_BY_ID, chat_id)
                if row:
                    return ChatSetting(**dict(row))
                return None
            except Exception as e:
                logger.error(f"Ошибка включения чата {chat_id}: {e}")
                return None

    async def disable_chat(self, chat_id: int) -> Optional[ChatSetting]:
        """
        Отключить мониторинг чата.

        Args:
            chat_id: ID чата

        Returns:
            Обновлённые настройки или None.
        """
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(SQL_DISABLE_CHAT_BY_ID, chat_id)
                if row:
                    return ChatSetting(**dict(row))
                return None
            except Exception as e:
                logger.error(f"Ошибка отключения чата {chat_id}: {e}")
                return None

    async def initialize_from_env(
        self,
        enable_list: List[int],
        disable_list: List[int]
    ) -> Dict[str, int]:
        """
        Инициализировать настройки чатов из переменных окружения.

        Применяет настройки из TG_CHAT_ENABLE и TG_CHAT_DISABLE:
        - Для чатов из enable_list устанавливается is_monitored=True
        - Для чатов из disable_list устанавливается is_monitored=False

        Args:
            enable_list: Список ID чатов для включения
            disable_list: Список ID чатов для отключения

        Returns:
            Статистика: {"enabled": count, "disabled": count}
        """
        from .chat_settings_base import ChatSettingsBaseRepository

        stats = {"enabled": 0, "disabled": 0}
        base_repo = ChatSettingsBaseRepository(self._pool)

        # Включаем чаты из enable_list
        for chat_id in enable_list:
            result = await self.enable_chat(chat_id)
            if result:
                stats["enabled"] += 1
                logger.info(f"Чат {chat_id} включён для мониторинга")
            else:
                # Если чат ещё не в БД, создаём запись
                await base_repo.upsert(
                    chat_id=chat_id,
                    title=f"Chat {chat_id}",
                    is_monitored=True,
                    summary_enabled=True,
                )
                stats["enabled"] += 1
                logger.info(f"Чат {chat_id} добавлен и включён для мониторинга")

        # Отключаем чаты из disable_list
        for chat_id in disable_list:
            result = await self.disable_chat(chat_id)
            if result:
                stats["disabled"] += 1
                logger.info(f"Чат {chat_id} отключён от мониторинга")
            else:
                # Если чат ещё не в БД, создаём запись с is_monitored=False
                await base_repo.upsert(
                    chat_id=chat_id,
                    title=f"Chat {chat_id}",
                    is_monitored=False,
                    summary_enabled=False,
                )
                stats["disabled"] += 1
                logger.info(f"Чат {chat_id} добавлен и отключён от мониторинга")

        return stats

    async def upsert_single_chat(
        self,
        chat_id: int,
        title: Optional[str] = None,
        is_monitored: bool = True,
        summary_enabled: bool = True,
        custom_prompt: Optional[str] = None,
        filter_bots: bool = True,
        filter_actions: bool = True,
        filter_min_length: int = 15,
        filter_ads: bool = True,
    ) -> Optional[ChatSetting]:
        """
        Сохранить или обновить настройки одного чата (альтернативный метод).

        Args:
            chat_id: ID чата
            title: Заголовок чата
            is_monitored: Мониторить ли чат
            summary_enabled: Включена ли сводка
            custom_prompt: Кастомный промпт
            filter_bots: Фильтровать сообщения ботов
            filter_actions: Фильтровать служебные действия
            filter_min_length: Минимальная длина сообщения
            filter_ads: Фильтровать рекламные сообщения

        Returns:
            Сохранённые настройки или None.
        """
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(
                    SQL_INSERT_CHAT_SETTING_SINGLE,
                    chat_id, title, "private", is_monitored, summary_enabled,
                    custom_prompt, filter_bots, filter_actions,
                    filter_min_length, filter_ads,
                )
                if row:
                    return ChatSetting(**dict(row))
                return None
            except Exception as e:
                logger.error(f"Ошибка сохранения настроек чата {chat_id}: {e}")
                return None
