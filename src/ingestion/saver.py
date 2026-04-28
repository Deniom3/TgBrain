"""
Ingestion — сохранение сообщений в БД.
"""

import json
import logging
from typing import Optional, Protocol, runtime_checkable

import asyncpg

from ..config import Settings
from ..domain.models.chat_filter_config import ChatFilterConfig
from ..embeddings import EmbeddingsClient
from .filters import should_process_message
from .models import IngestionMessage

logger = logging.getLogger(__name__)


@runtime_checkable
class IMessageSaver(Protocol):
    """Интерфейс для сохранения сообщений."""

    embeddings: EmbeddingsClient

    async def get_embedding(self, text: str) -> list[float]:
        """Получение эмбеддинга."""
        ...

    def get_model_name(self) -> str:
        """Получение имени модели эмбеддингов."""
        ...


class MessageSaver:
    """Сохранение сообщений в базу данных."""

    def __init__(
        self,
        config: Settings,
        pool: asyncpg.Pool,
        embeddings_client: EmbeddingsClient,
    ) -> None:
        self.config = config
        self.pool = pool
        self.embeddings = embeddings_client
        self.filtered_count = 0
        self.error_count = 0

    async def save_message(
        self,
        message: IngestionMessage,
        embedding: Optional[list[float]] = None,
        chat_config: Optional[ChatFilterConfig] = None,
    ) -> bool:
        """
        Сохранение сообщения в БД.

        Args:
            message: Сообщение для сохранения.
            embedding: Вектор эмбеддинга (опционально).
            chat_config: Конфигурация фильтров чата (опционально).

        Returns:
            True если успешно.
        """
        if chat_config:
            should_process, reason = should_process_message(
                message.text,
                message.is_bot,
                message.is_action,
                filter_bots=chat_config.filter_bots,
                filter_actions=chat_config.filter_actions,
                filter_min_length=chat_config.filter_min_length,
                filter_ads=chat_config.filter_ads,
            )
        else:
            should_process, reason = should_process_message(
                message.text,
                message.is_bot,
                message.is_action,
            )

        if not should_process:
            logger.debug("Сообщение %s отфильтровано: %s", message.id, reason)
            self.filtered_count += 1
            return True

        # Векторизация если не передан
        if embedding is None:
            try:
                embedding = await self.embeddings.get_embedding(message.text)
            except Exception as e:
                logger.warning("Ошибка векторизации сообщения %s: %s", message.id, e)
                await self.save_pending(message, str(e))
                self.error_count += 1
                return False

        # Сохранение в БД
        try:
            await self._save_to_db(message, embedding)
            return True
        except Exception as e:
            logger.error("Ошибка сохранения сообщения %s: %s", message.id, e)
            await self.save_pending(message, f"DB error: {e}")
            self.error_count += 1
            return False

    async def _save_to_db(
        self,
        message: IngestionMessage,
        embedding: list[float]
    ) -> None:
        """Сохранение в таблицу messages."""
        # Создаём запись в chat_settings (если нет)
        await self.pool.execute("""
            INSERT INTO chat_settings (chat_id, title, type, last_message_id, is_monitored, summary_enabled, filter_bots, filter_actions, filter_min_length, filter_ads)
            VALUES ($1, $2, $3, 0, TRUE, TRUE, TRUE, TRUE, 15, TRUE)
            ON CONFLICT (chat_id) DO UPDATE SET
                title = EXCLUDED.title,
                type = EXCLUDED.type,
                updated_at = NOW()
        """, message.chat_id, message.chat_title, message.chat_type)

        embedding_model = self.embeddings.get_model_name()

        await self.pool.execute("""
            INSERT INTO messages (
                id, chat_id, sender_id, sender_name, message_text,
                message_date, message_link, embedding, embedding_model, is_processed, is_bot
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::VECTOR, $9, $10, $11)
            ON CONFLICT (id) DO UPDATE SET
                embedding = EXCLUDED.embedding,
                embedding_model = EXCLUDED.embedding_model,
                is_processed = EXCLUDED.is_processed,
                sender_name = EXCLUDED.sender_name,
                is_bot = EXCLUDED.is_bot
        """,
            message.id,
            message.chat_id,
            message.sender_id,
            message.sender_name,
            message.text,
            message.date,
            message.message_link,
            embedding,
            embedding_model,
            True,
            message.is_bot,
        )

        logger.debug("Сообщение %s сохранено в БД", message.id)

    async def update_chat_progress(
        self,
        chat_id: int,
        chat_title: str,
        chat_type: str,
        last_message_id: int
    ) -> None:
        """Обновление прогресса чата."""
        await self.pool.execute("""
            UPDATE chat_settings
            SET last_message_id = $4, title = $2, type = $3, updated_at = NOW()
            WHERE chat_id = $1
        """, chat_id, chat_title, chat_type, last_message_id)

    async def save_pending(
        self,
        message: IngestionMessage,
        error: str
    ) -> None:
        """Сохранение в pending_messages при ошибке."""
        message_data = {
            "id": message.id,
            "chat_id": message.chat_id,
            "chat_title": message.chat_title,
            "sender_id": message.sender_id,
            "sender_name": message.sender_name,
            "text": message.text,
            "date": message.date.isoformat(),
            "message_link": message.message_link
        }

        await self.pool.execute("""
            INSERT INTO pending_messages (message_data, retry_count, last_error)
            VALUES ($1::JSONB, 0, $2)
        """, json.dumps(message_data), error)

        logger.warning("Сообщение %s сохранено в pending: %s", message.id, error)

    def get_stats(self) -> dict[str, int]:
        """Статистика saver."""
        return {
            "filtered": self.filtered_count,
            "errors": self.error_count,
        }


