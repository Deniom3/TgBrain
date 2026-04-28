"""
MessageProcessor — обработка и сохранение сообщений из Telegram.
"""

import asyncio
import logging
from typing import Optional

from telethon import TelegramClient
from telethon.tl.types import Message as TLMessage

from ..config import Settings
from ..database import get_pool
from ..domain.models.chat_filter_config import ChatFilterConfig
from ..rate_limiter import TelegramRateLimiter, RequestPriority
from ..settings import ChatSettingsRepository
from .models import IngestionMessage
from .pending_cleanup_service import PendingCleanupService
from .saver import MessageSaver

logger = logging.getLogger(__name__)


class MessageProcessor:
    """Обработка и сохранение сообщений из Telegram."""

    def __init__(
        self,
        config: Settings,
        saver: MessageSaver,
        pending_cleanup: PendingCleanupService,
    ):
        self.config = config
        self.saver = saver
        self.pending_cleanup = pending_cleanup
        self._processed_count = 0
        self._error_count = 0
        self._last_message_ids: dict[int, int] = {}
        self._processing_lock = asyncio.Lock()
        self._last_message_ids_lock = asyncio.Lock()
        self._monitored_chats_cache: set[int] = set()
        self._monitored_chats_cache_lock = asyncio.Lock()
        self._chat_filter_config: dict[int, ChatFilterConfig] = {}
        self._cache_refresh_counter = 0
        self._cache_refresh_interval = 6

    async def initialize_monitored_chats(self, monitored_chats: list[int]) -> None:
        async with self._monitored_chats_cache_lock:
            self._monitored_chats_cache = set(monitored_chats)
            pool = await get_pool()
            repo = ChatSettingsRepository(pool)
            self._chat_filter_config = await repo.get_chat_filter_configs()

        for chat_id in monitored_chats:
            try:
                db_last_id = await self.fetch_last_message_id(chat_id)
                async with self._last_message_ids_lock:
                    self._last_message_ids[chat_id] = db_last_id
                logger.debug(f"Чат {chat_id}: last_id={db_last_id} (из БД)")
            except Exception as e:
                logger.error(f"Ошибка получения ID для чата {chat_id}: {e}")
                async with self._last_message_ids_lock:
                    self._last_message_ids[chat_id] = 0

        logger.info(f"Инициализировано {len(monitored_chats)} чатов для polling")

    async def fetch_last_message_id(self, chat_id: int) -> int:
        pool = await get_pool()
        record = await pool.fetchrow(
            "SELECT last_message_id FROM chat_settings WHERE chat_id = $1", chat_id
        )
        return record["last_message_id"] if record else 0

    async def process_message(self, tl_message: TLMessage) -> None:
        message = await self._parse_message(tl_message)
        if not message:
            logger.warning(f"Не удалось распарсить сообщение {tl_message.id}")
            return

        logger.info(f"Обработка сообщения {message.id} из {message.chat_title}...")
        chat_config = self._chat_filter_config.get(message.chat_id)
        success = await self.saver.save_message(message, chat_config=chat_config)
        if success:
            self._processed_count += 1
            await self.saver.update_chat_progress(
                message.chat_id, message.chat_title, message.chat_type, message.id
            )
            logger.info(f"✅ Сообщение {message.id} обработано")
        else:
            self._error_count += 1
            logger.warning(f"❌ Сообщение {message.id} не обработано")

    async def _parse_message(self, tl_message: TLMessage) -> Optional[IngestionMessage]:
        try:
            chat = await tl_message.get_chat()
            chat_title = getattr(chat, "title", f"Chat {chat.id}")
            chat_type = getattr(chat, "type", "private")
            sender = await tl_message.get_sender()
            sender_id = sender.id if sender else None
            sender_name = None
            is_bot = getattr(sender, "bot", False) if sender else False

            if sender:
                sender_name = (
                    f"@{sender.username}"
                    if hasattr(sender, "username") and sender.username
                    else getattr(sender, "first_name", None)
                )

            text = tl_message.text or ""
            if not text and tl_message.media:
                text = f"[media: {type(tl_message.media).__name__}]"

            message_link = (
                f"https://t.me/c/{str(tl_message.chat_id)[4:]}/{tl_message.id}"
                if tl_message.is_channel
                else None
            )

            return IngestionMessage(
                id=tl_message.id,
                chat_id=tl_message.chat_id,
                chat_title=chat_title,
                chat_type=chat_type,
                sender_id=sender_id,
                sender_name=sender_name,
                text=text,
                date=tl_message.date,
                message_link=message_link,
                is_bot=is_bot,
                is_action=bool(tl_message.action),
            )
        except Exception as e:
            logger.error(f"Ошибка парсинга сообщения: {e}")
            return None

    async def handle_new_message(self, event) -> None:
        msg_id, chat_id = event.id, event.chat_id

        async with self._monitored_chats_cache_lock:
            if chat_id not in self._monitored_chats_cache:
                return

        if chat_id not in self._last_message_ids:
            async with self._last_message_ids_lock:
                if chat_id not in self._last_message_ids:
                    self._last_message_ids[chat_id] = await self.fetch_last_message_id(chat_id)
                    logger.info(f"Добавлен monitored чат {chat_id}")

        async with self._processing_lock:
            if msg_id <= self._last_message_ids.get(chat_id, 0):
                return
            self._last_message_ids[chat_id] = msg_id

        await self.process_message(event.message)

    async def poll_messages(
        self,
        client: TelegramClient,
        rate_limiter: Optional[TelegramRateLimiter] = None,
    ) -> None:
        self._cache_refresh_counter += 1
        if self._cache_refresh_counter >= self._cache_refresh_interval:
            self._cache_refresh_counter = 0
            pool = await get_pool()
            repo = ChatSettingsRepository(pool)
            current_monitored = await repo.get_monitored_chat_ids()
            async with self._monitored_chats_cache_lock:
                self._monitored_chats_cache = set(current_monitored)
                self._chat_filter_config = await repo.get_chat_filter_configs()
        else:
            async with self._monitored_chats_cache_lock:
                current_monitored = list(self._monitored_chats_cache)

        for chat_id in current_monitored:
            if chat_id not in self._last_message_ids:
                async with self._last_message_ids_lock:
                    if chat_id not in self._last_message_ids:
                        self._last_message_ids[chat_id] = await self.fetch_last_message_id(
                            chat_id
                        )

        async with self._last_message_ids_lock:
            snapshot = dict(self._last_message_ids)

        for chat_id in snapshot:
            if chat_id not in current_monitored:
                continue
            try:
                messages = (
                    await rate_limiter.execute(
                        RequestPriority.NORMAL, client.get_messages, chat_id, limit=10
                    )
                    if rate_limiter
                    else await client.get_messages(chat_id, limit=10)
                )

                for msg in reversed(messages):
                    async with self._processing_lock:
                        if msg.id > self._last_message_ids.get(chat_id, 0):
                            self._last_message_ids[chat_id] = msg.id
                            should_process = True
                        else:
                            should_process = False

                    if should_process:
                        await self.process_message(msg)
            except Exception as e:
                logger.error(f"Ошибка опроса чата {chat_id}: {e}")

    async def reload_monitored_chats(self) -> None:
        pool = await get_pool()
        repo = ChatSettingsRepository(pool)
        current_monitored = await repo.get_monitored_chat_ids()
        async with self._monitored_chats_cache_lock:
            self._monitored_chats_cache = set(current_monitored)
            self._chat_filter_config = await repo.get_chat_filter_configs()
        added, removed = 0, 0
        for chat_id in current_monitored:
            async with self._last_message_ids_lock:
                if chat_id not in self._last_message_ids:
                    self._last_message_ids[chat_id] = await self.fetch_last_message_id(
                        chat_id
                    )
                    added += 1

        async with self._last_message_ids_lock:
            for chat_id in list(self._last_message_ids.keys()):
                if chat_id not in current_monitored:
                    del self._last_message_ids[chat_id]
                    removed += 1
            total_count = len(self._last_message_ids)

        logger.info(
            f"Monitored чаты обновлены: +{added}, -{removed}, "
            f"всего {total_count}"
        )

    def get_stats(self) -> dict:
        saver_stats = self.saver.get_stats() if self.saver else {}
        return {
            "processed": self._processed_count,
            "filtered": saver_stats.get("filtered", 0),
            "errors": saver_stats.get("errors", self._error_count),
        }

    async def cleanup_old_pending_messages(self) -> int:
        return await self.pending_cleanup.cleanup_old_pending_messages()

    async def start_cleanup_task(self) -> None:
        await self.pending_cleanup.start_cleanup_task()
