"""
Chat Sync Service - сервис синхронизации чатов из Telegram.

Получает список всех доступных диалогов из Telegram и сохраняет их в БД.
"""

import logging
from typing import Any, Dict, List, Optional

import asyncpg
from telethon import TelegramClient
from telethon.tl.types import Chat, Channel, User

from ..settings import ChatSettingsRepository

logger = logging.getLogger(__name__)


def normalize_chat_id(entity_id: int, is_channel: bool) -> int:
    """
    Нормализация ID чата.
    
    В Telegram:
    - Личные чаты: положительный ID (123456789)
    - Группы: отрицательный ID (-123456789)  
    - Каналы/супергруппы: -100XXXXXXXXX
    
    Args:
        entity_id: ID сущности из Telegram API
        is_channel: True если это канал/супергруппа
    
    Returns:
        Нормализованный ID для хранения в БД
    """
    # Для каналов и супергрупп добавляем -100 если нужно
    if is_channel:
        # Каналы всегда должны иметь префикс -100
        if entity_id > 0:
            return -1000000000000 + entity_id
        elif str(entity_id).startswith('-100'):
            return entity_id  # Уже с префиксом
        else:
            # Отрицательный но без -100
            return -1000000000000 + abs(entity_id)
    
    # Для групп и личных чатов возвращаем как есть
    return entity_id


class ChatSyncService:
    """
    Сервис для синхронизации чатов из Telegram с базой данных.
    
    Получает список всех доступных диалогов, фильтрует их
    и сохраняет в таблицу chat_settings.
    """

    def __init__(self, pool: asyncpg.Pool):
        """
        Инициализация сервиса.
        
        Args:
            pool: Пул подключений к PostgreSQL.
        """
        self.pool = pool
        self._synced_count = 0
        self._filtered_count = 0
        self._updated_count = 0

    async def fetch_all_dialogs(
        self,
        client: TelegramClient,
        limit: int = 100,
        include_private: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Получение списка всех доступных диалогов из Telegram.

        Args:
            client: Telegram клиент.
            limit: Максимальное количество диалогов для получения.
            include_private: Включить личные сообщения (User).

        Returns:
            Список словарей с информацией о диалогах.
        """
        logger.info(f"Получение списка диалогов из Telegram (лимит: {limit}, "
                   f"private: {include_private})...")

        dialogs = []
        try:
            # Получаем диалоги через client.get_dialogs()
            async for dialog in client.iter_dialogs(limit=limit):
                entity = dialog.entity

                # Обработка личных сообщений (User)
                if isinstance(entity, User):
                    if not include_private:
                        # Личные сообщения исключены
                        self._filtered_count += 1
                        continue
                    
                    # Исключаем ботов
                    if getattr(entity, 'bot', False):
                        logger.debug(f"Пропущен бот: {entity.username or entity.id}")
                        self._filtered_count += 1
                        continue
                    
                    # Исключаем архивные
                    if getattr(dialog, 'archived', False):
                        logger.debug(f"Пропущен архивный пользователь: {entity.id}")
                        self._filtered_count += 1
                        continue
                    
                    # Формируем имя
                    name_parts = []
                    if getattr(entity, 'first_name', None):
                        name_parts.append(entity.first_name)
                    if getattr(entity, 'last_name', None):
                        name_parts.append(entity.last_name)
                    if getattr(entity, 'username', None):
                        name_parts.append(f"@{entity.username}")
                    
                    title = " ".join(name_parts) if name_parts else f"User {entity.id}"
                    
                    dialogs.append({
                        "chat_id": entity.id,
                        "title": title,
                        "type": "private",
                        "is_channel": False,
                        "is_group": False,
                        "is_private": True,
                        "username": getattr(entity, 'username', None),
                        "is_bot": False,
                    })
                    continue

                # Обработка групп и каналов (Chat, Channel)
                if isinstance(entity, (Chat, Channel)):
                    # Нормализация ID для каналов
                    is_channel = isinstance(entity, Channel)
                    raw_id = entity.id
                    
                    # Для каналов добавляем префикс -100 если его нет
                    if is_channel:
                        if raw_id > 0:
                            chat_id = -1000000000000 + raw_id
                        elif not str(raw_id).startswith('-100'):
                            chat_id = -1000000000000 + abs(raw_id)
                        else:
                            chat_id = raw_id  # Уже с префиксом -100
                    else:
                        chat_id = raw_id  # Для групп оставляем как есть
                    
                    title = str(getattr(entity, 'title', None) or getattr(entity, 'username', f'Chat {chat_id}'))
                    chat_type = self._get_chat_type(entity)

                    # Пропускаем архивные чаты
                    if getattr(dialog, 'archived', False):
                        logger.debug(f"Пропущен архивный чат: {title} ({chat_id})")
                        self._filtered_count += 1
                        continue

                    # Пропускаем чаты без названия
                    if not title:
                        logger.debug(f"Пропущен чат без названия: {chat_id}")
                        self._filtered_count += 1
                        continue

                    dialogs.append({
                        "chat_id": chat_id,
                        "title": str(title),
                        "type": chat_type,
                        "is_channel": isinstance(entity, Channel),
                        "is_group": isinstance(entity, Chat),
                        "is_private": False,
                        "participants_count": getattr(entity, 'participants_count', 0),
                    })
                    
        except Exception as e:
            logger.error(f"Ошибка получения диалогов: {e}", exc_info=True)
        
        logger.info(f"Получено {len(dialogs)} диалогов, отфильтровано {self._filtered_count}")
        return dialogs

    async def sync_chats_with_telegram(
        self,
        client: TelegramClient,
        limit: int = 100,
        preserve_existing: bool = True,
        include_private: bool = False
    ) -> Dict[str, int]:
        """
        Синхронизация чатов из Telegram с базой данных.

        Получает список диалогов из Telegram и сохраняет их в БД.

        Args:
            client: Telegram клиент.
            limit: Максимальное количество диалогов для получения.
            preserve_existing: Сохранять существующие настройки (is_monitored).
            include_private: Включить личные сообщения (User).

        Returns:
            Статистика: {"added": count, "updated": count, "filtered": count}
        """
        logger.info(f"Начало синхронизации чатов с Telegram (private: {include_private})...")

        # Получаем диалоги из Telegram
        dialogs = await self.fetch_all_dialogs(client, limit, include_private)

        if not dialogs:
            logger.warning("Нет диалогов для синхронизации")
            return {"added": 0, "updated": 0, "filtered": self._filtered_count}

        # Получаем существующие настройки из БД
        repo = ChatSettingsRepository(self.pool)
        existing_settings = await repo.get_all()
        existing_map = {s.chat_id: s for s in existing_settings}

        # Подготавливаем данные для массового сохранения
        chats_to_save = []
        for dialog in dialogs:
            chat_id = dialog["chat_id"]
            existing = existing_map.get(chat_id)

            # Если чат уже есть в БД, сохраняем его настройки
            if existing and preserve_existing:
                is_monitored = existing.is_monitored
                summary_enabled = existing.summary_enabled
            else:
                # Новые чаты по умолчанию не мониторятся
                # (пользователь должен явно включить их через API)
                is_monitored = False
                summary_enabled = True

            chats_to_save.append({
                "chat_id": chat_id,
                "title": dialog["title"],
                "is_monitored": is_monitored,
                "is_enabled": summary_enabled,
            })
        
        # Массовое сохранение в БД
        if chats_to_save:
            saved_chats = await repo.bulk_upsert_chat_settings(chats_to_save)
            self._synced_count = len(saved_chats)
            
            # Подсчитываем новые и обновлённые
            new_count = sum(1 for c in chats_to_save if c["chat_id"] not in existing_map)
            updated_count = len(chats_to_save) - new_count
            
            logger.info(f"Синхронизировано {len(saved_chats)} чатов "
                       f"(новых: {new_count}, обновлено: {updated_count})")
            
            return {
                "added": new_count,
                "updated": updated_count,
                "filtered": self._filtered_count,
                "total": len(saved_chats),
            }
        
        return {"added": 0, "updated": 0, "filtered": self._filtered_count, "total": 0}

    async def apply_env_initialization(
        self,
        enable_list: List[int],
        disable_list: List[int]
    ) -> Dict[str, int]:
        """
        Применение настроек из переменных окружения.
        
        Args:
            enable_list: Список ID чатов для включения.
            disable_list: Список ID чатов для отключения.
            
        Returns:
            Статистика: {"enabled": count, "disabled": count}
        """
        logger.info(f"Применение настроек из .env: "
                   f"enable={len(enable_list)}, disable={len(disable_list)}")
        
        repo = ChatSettingsRepository(self.pool)
        stats = await repo.initialize_from_env(
            enable_list,
            disable_list
        )
        
        logger.info(f"Настройки применены: {stats}")
        return stats

    async def get_chat_info(
        self,
        client: TelegramClient,
        chat_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Получение информации о конкретном чате из Telegram.

        Args:
            client: Telegram клиент.
            chat_id: ID чата.

        Returns:
            Информация о чате или None.
        """
        try:
            entity = await client.get_entity(chat_id)

            if isinstance(entity, User):
                # Личный чат (пользователь)
                name_parts = []
                if getattr(entity, 'first_name', None):
                    name_parts.append(entity.first_name)
                if getattr(entity, 'last_name', None):
                    name_parts.append(entity.last_name)
                if getattr(entity, 'username', None):
                    name_parts.append(f"@{entity.username}")
                
                title = " ".join(name_parts) if name_parts else f"User {entity.id}"
                
                return {
                    "chat_id": entity.id,
                    "title": title,
                    "type": "private",
                    "is_channel": False,
                    "is_group": False,
                    "is_private": True,
                    "username": getattr(entity, 'username', None),
                    "is_bot": getattr(entity, 'bot', False),
                }
            
            elif isinstance(entity, (Chat, Channel)):
                # Нормализация ID для каналов
                is_channel = isinstance(entity, Channel)
                raw_id = entity.id
                
                if is_channel:
                    if raw_id > 0:
                        chat_id = -1000000000000 + raw_id
                    elif not str(raw_id).startswith('-100'):
                        chat_id = -1000000000000 + abs(raw_id)
                    else:
                        chat_id = raw_id
                else:
                    chat_id = raw_id
                
                return {
                    "chat_id": chat_id,
                    "title": getattr(entity, 'title', None) or getattr(entity, 'username', f'Chat {chat_id}'),
                    "type": self._get_chat_type(entity),
                    "is_channel": is_channel,
                    "is_group": isinstance(entity, Chat),
                    "is_private": False,
                    "participants_count": getattr(entity, 'participants_count', 0),
                }
        except Exception as e:
            logger.error(f"Ошибка получения информации о чате {chat_id}: {e}")
        
        return None

    async def get_user_info_by_username(
        self,
        client: TelegramClient,
        username: str
    ) -> Optional[Dict[str, Any]]:
        """
        Получение информации о пользователе по username.

        Args:
            client: Telegram клиент.
            username: Username пользователя (с @ или без).

        Returns:
            Информация о пользователе или None.
        """
        try:
            # Удаляем @ если есть
            username = username.lstrip('@')
            
            # Получаем сущность
            entity = await client.get_entity(username)
            
            if isinstance(entity, User):
                name_parts = []
                if getattr(entity, 'first_name', None):
                    name_parts.append(entity.first_name)
                if getattr(entity, 'last_name', None):
                    name_parts.append(entity.last_name)
                if getattr(entity, 'username', None):
                    name_parts.append(f"@{entity.username}")
                
                title = " ".join(name_parts) if name_parts else f"User {entity.id}"
                
                return {
                    "chat_id": entity.id,
                    "title": title,
                    "type": "private",
                    "username": getattr(entity, 'username', None),
                    "is_bot": getattr(entity, 'bot', False),
                }
            
            logger.warning(f"Сущность {username} не является пользователем")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения информации о пользователе {username}: {e}")
            return None

    def _get_chat_type(self, entity: Any) -> str:
        """
        Определение типа чата.
        
        Args:
            entity: Сущность Telegram.
            
        Returns:
            Строка с типом чата.
        """
        if isinstance(entity, Channel):
            if getattr(entity, 'broadcast', False):
                return "channel"
            elif getattr(entity, 'megagroup', False):
                return "supergroup"
            else:
                return "channel"
        elif isinstance(entity, Chat):
            return "group"
        else:
            return "private"

    def get_stats(self) -> Dict[str, int]:
        """
        Получение статистики синхронизации.
        
        Returns:
            Статистика: {"synced": count, "filtered": count, "updated": count}
        """
        return {
            "synced": self._synced_count,
            "filtered": self._filtered_count,
            "updated": self._updated_count,
        }

    def reset_stats(self) -> None:
        """Сброс статистики."""
        self._synced_count = 0
        self._filtered_count = 0
        self._updated_count = 0
