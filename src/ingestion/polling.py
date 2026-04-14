"""
Ingestion — polling логика для Telegram.
"""

import asyncio
import logging
from typing import Dict, List, Optional

import asyncpg
from telethon import TelegramClient
from telethon.tl.types import Message as TLMessage

from ..config import Settings
from ..settings import ChatSettingsRepository
from .models import IngestionMessage
from .saver import MessageSaver

logger = logging.getLogger(__name__)


class PollingService:
    """Polling сервис для опроса чатов."""

    def __init__(
        self,
        client: TelegramClient,
        config: Settings,
        saver: MessageSaver,
        pool: asyncpg.Pool
    ):
        self.client = client
        self.config = config
        self.saver = saver
        self.pool = pool
        self._running = False
        self._last_message_ids: Dict[int, int] = {}
        self._processing_lock = asyncio.Lock()
        self.processed_count = 0
        self._monitored_chat_ids: List[int] = []

    async def _get_monitored_chat_ids(self) -> List[int]:
        """Получение списка чатов для мониторинга из БД."""
        if not self._monitored_chat_ids:
            repo = ChatSettingsRepository(self.pool)
            self._monitored_chat_ids = await repo.get_monitored_chat_ids()
            logger.info(f"Загружено {len(self._monitored_chat_ids)} чатов для мониторинга")
        return self._monitored_chat_ids

    async def load_last_message_ids(self) -> None:
        """Загрузка последних ID сообщений для каждого чата."""
        chat_ids = await self._get_monitored_chat_ids()
        for chat_id in chat_ids:
            try:
                last_id = await self.fetch_last_message_id(chat_id)
                self._last_message_ids[chat_id] = last_id
                logger.info(f"Чат {chat_id}: последний обработанный ID = {last_id}")
            except Exception as e:
                logger.error(f"Ошибка получения ID для чата {chat_id}: {e}")
                self._last_message_ids[chat_id] = 0

    async def polling_loop(self) -> None:
        """Цикл опроса чатов с интервалом."""
        while self._running:
            try:
                await self.poll_messages()
            except Exception as e:
                logger.error(f"Ошибка в polling: {e}")
            await asyncio.sleep(5)

    async def poll_messages(self) -> None:
        """Опрос чатов на наличие новых сообщений."""
        chat_ids = await self._get_monitored_chat_ids()
        for chat_id in chat_ids:
            try:
                messages = await self.client.get_messages(chat_id, limit=10)

                for msg in reversed(messages):
                    async with self._processing_lock:
                        last_id = self._last_message_ids.get(chat_id, 0)
                        if msg.id > last_id:
                            logger.debug(f"Чат {chat_id}: новое сообщение {msg.id}")
                            self._last_message_ids[chat_id] = msg.id
                            should_process = True
                        else:
                            should_process = False

                    if should_process:
                        await self._process_message(msg)

            except Exception as e:
                logger.error(f"Ошибка опроса чата {chat_id}: {e}")

    async def _process_message(self, tl_message: TLMessage) -> None:
        """Обработка одного сообщения."""
        message = await self._parse_message(tl_message)

        if message:
            logger.info(f"Обработка сообщения {message.id} из {message.chat_title}...")
            success = await self.saver.save_message(message)
            if success:
                self.processed_count += 1
                await self.saver.update_chat_progress(
                    message.chat_id,
                    message.chat_title,
                    message.chat_type,
                    message.id
                )
                logger.info(f"✅ Сообщение {message.id} обработано")
            else:
                logger.warning(f"❌ Сообщение {message.id} не обработано")
        else:
            logger.warning(f"Не удалось распарсить сообщение {tl_message.id}")

    async def _parse_message(self, tl_message: TLMessage) -> Optional[IngestionMessage]:
        """Парсинг сообщения Telethon."""
        try:
            chat = await tl_message.get_chat()
            chat_title = getattr(chat, 'title', f"Chat {chat.id}")
            chat_type = getattr(chat, 'type', 'private')

            sender = await tl_message.get_sender()
            sender_id = sender.id if sender else None
            sender_name = None
            is_bot = False

            if sender:
                is_bot = getattr(sender, 'bot', False)
                if hasattr(sender, 'username') and sender.username:
                    sender_name = f"@{sender.username}"
                elif hasattr(sender, 'first_name'):
                    sender_name = sender.first_name

            text = tl_message.text or ""
            if not text and tl_message.media:
                text = f"[media: {type(tl_message.media).__name__}]"

            message_link = None
            if tl_message.is_channel:
                message_link = f"https://t.me/c/{str(tl_message.chat_id)[4:]}/{tl_message.id}"

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
                is_action=bool(tl_message.action)
            )
        except Exception as e:
            logger.error(f"Ошибка парсинга сообщения: {e}")
            return None

    async def fetch_last_message_id(self, chat_id: int) -> int:
        """Получение последнего обработанного message_id для чата."""
        record = await self.pool.fetchrow("""
            SELECT last_message_id FROM chat_settings WHERE chat_id = $1
        """, chat_id)
        return record['last_message_id'] if record else 0

    def stop(self) -> None:
        """Остановка polling."""
        self._running = False

    def start(self) -> None:
        """Запуск polling."""
        self._running = True
