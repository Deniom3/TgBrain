"""
RAG (Retrieval-Augmented Generation) — векторный поиск.

Модуль предоставляет класс RAGSearch для выполнения векторного поиска
по базе сообщений с поддержкой фильтрации по чатам и расширения контекста.
"""

import logging
from datetime import datetime
from typing import Any, Optional

import asyncpg

from ..config import Settings
from ..domain.value_objects import MessageText, SenderName, ChatTitle
from ..models import MessageRecord
from ..models.sql.rag import (
    SQL_SEARCH_SIMILAR_WITH_CHAT_FILTER,
    SQL_GET_MESSAGES_BY_PERIOD,
    SQL_GET_MESSAGES_BY_PERIOD_RANGE,
)
from .context_expander import ContextExpander
from .exceptions import DatabaseQueryError
from ..settings.repositories.embedding_providers import EmbeddingProvidersRepository

logger = logging.getLogger(__name__)

# =============================================================================
# Константы
# =============================================================================

MAX_TOP_K: int = 100
"""Максимальное количество результатов поиска."""

MIN_EMBEDDING_DIM: int = 384
"""Минимальная размерность вектора эмбеддинга."""

SHORT_MESSAGE_THRESHOLD: int = 15
"""Порог короткого сообщения для расширения контекста."""

GROUPING_WINDOW_MINUTES: int = 5
"""Окно группировки последовательных сообщений."""


class RAGSearch:
    """Векторный поиск для RAG."""

    def __init__(
        self,
        config: Settings,
        db_pool: asyncpg.Pool,
        embedding_repo: Optional[EmbeddingProvidersRepository] = None,
    ):
        self.config = config
        self.db_pool = db_pool
        self.expander = ContextExpander(db_pool, embedding_repo=embedding_repo)

    @classmethod
    async def create(cls, config: Settings, db_pool: asyncpg.Pool) -> "RAGSearch":
        """
        Создать и инициализировать RAGSearch.

        Args:
            config: Конфигурация приложения.
            db_pool: Пул подключений к БД.

        Returns:
            Инициализированный экземпляр RAGSearch.
        """
        instance = cls(config, db_pool)
        await instance.initialize()
        return instance

    async def initialize(self) -> bool:
        """Инициализация RAGSearch и ContextExpander."""
        return await self.expander.initialize()

    async def search_similar(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        chat_id: Optional[int] = None
    ) -> list[MessageRecord]:
        """
        Векторный поиск с опциональной фильтрацией по чату.

        Args:
            query_embedding: Вектор запроса
            top_k: Количество результатов
            chat_id: ID чата для фильтрации (None = поиск по всем чатам)

        Returns:
            Список MessageRecord, отсортированных по similarity_score
        """
        if not query_embedding:
            logger.error("Empty query_embedding")
            return []

        if len(query_embedding) < MIN_EMBEDDING_DIM:
            logger.error("Embedding dimension too small: %d", len(query_embedding))
            return []

        if top_k <= 0:
            top_k = 5
        elif top_k > MAX_TOP_K:
            top_k = MAX_TOP_K

        logger.info("Поиск похожих сообщений, top_k=%d, chat_id=%s", top_k, chat_id)

        async with self.db_pool.acquire() as conn:
            try:
                rows = await conn.fetch(
                    SQL_SEARCH_SIMILAR_WITH_CHAT_FILTER,
                    query_embedding,
                    top_k,
                    chat_id
                )
            except asyncpg.PostgresError as e:
                logger.error("Ошибка БД при поиске: %s", e)
                raise DatabaseQueryError(f"Ошибка выполнения запроса к БД: {e}") from e

            results = [self._row_to_message_record(row) for row in rows]
            logger.info("Найдено %d релевантных сообщений", len(results))
            return results

    async def expand_search_results(
        self,
        messages: list[MessageRecord],
        chat_id: Optional[int] = None,
        expand_context: bool = True,
        context_window: int = 2
    ) -> list[MessageRecord]:
        """
        Расширение результатов поиска контекстом.

        Для коротких сообщений (< 15 символов) получает соседние.
        Для длинных — группирует последовательные сообщения.

        Args:
            messages: Результаты поиска
            chat_id: ID чата (обязателен для расширения)
            expand_context: Флаг расширения (по умолчанию True)
            context_window: Количество соседей (по умолчанию 2)

        Returns:
            Список сообщений с расширенным контекстом
        """
        if not expand_context or not chat_id:
            return messages

        logger.info("Расширение контекста для %d сообщений", len(messages))

        expanded_results: list[MessageRecord] = []

        for msg in messages:
            if len(str(msg.text)) < SHORT_MESSAGE_THRESHOLD:
                neighbors = await self.expander.expand_with_neighbors(
                    message_id=msg.id,
                    chat_id=chat_id,
                    sender_id=msg.sender_id,
                    before=context_window,
                    after=context_window
                )

                if neighbors:
                    msg.expand_with(neighbors)
                    logger.debug("Сообщение %d расширено %d соседями", msg.id, len(neighbors))

            expanded_results.append(msg)

        if expanded_results:
            groups = await self.expander.group_consecutive_messages(
                chat_id=chat_id,
                messages=expanded_results,
                window_minutes=GROUPING_WINDOW_MINUTES
            )

            if groups:
                logger.info("Сгруппировано %d групп сообщений", len(groups))

        return expanded_results

    def _row_to_message_record(self, row: Any) -> MessageRecord:
        """Конвертация строки БД в MessageRecord."""
        return MessageRecord(
            id=row["id"],
            text=MessageText(row["message_text"] or ""),
            date=row["message_date"],
            chat_title=ChatTitle(row["chat_title"]),
            link=row["message_link"] or "",
            sender_name=SenderName(row["sender_name"]),
            sender_id=row["sender_id"] or 0,
            similarity_score=float(row["similarity_score"]) if row["similarity_score"] else 0.0
        )

    async def get_messages_by_period(
        self,
        period_hours: int,
        max_messages: int,
        chat_id: Optional[int] = None,
        *,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> list[MessageRecord]:
        """
        Получение сообщений за период.

        Args:
            period_hours: Период в часах. Должен быть > 0.
            max_messages: Максимум сообщений. Должен быть > 0.
            chat_id: ID чата для фильтрации (опционально).
            period_start: Начало периода (альтернатива period_hours).
            period_end: Конец периода (альтернатива period_hours).

        Returns:
            Список MessageRecord.

        Raises:
            ValueError: Если period_hours <= 0 или max_messages <= 0.
        """
        if period_hours <= 0:
            raise ValueError("period_hours должен быть больше 0")
        if max_messages <= 0:
            raise ValueError("max_messages должен быть больше 0")

        async with self.db_pool.acquire() as conn:
            try:
                if period_start is not None and period_end is not None:
                    rows = await conn.fetch(
                        SQL_GET_MESSAGES_BY_PERIOD_RANGE,
                        period_start,
                        period_end,
                        max_messages,
                        chat_id,
                    )
                else:
                    rows = await conn.fetch(
                        SQL_GET_MESSAGES_BY_PERIOD,
                        period_hours,
                        max_messages,
                        chat_id,
                    )
            except asyncpg.PostgresError as e:
                logger.error("Ошибка получения сообщений за период: %s", e)
                raise DatabaseQueryError(f"Ошибка выполнения запроса к БД: {e}") from e

            return [
                MessageRecord(
                    id=row["id"],
                    text=MessageText(row["message_text"] or ""),
                    date=row["message_date"],
                    chat_title=ChatTitle(row["chat_title"]),
                    link=row["message_link"] or "",
                    sender_name=SenderName(row["sender_name"]),
                    sender_id=row["sender_id"] or 0,
                    similarity_score=0.0,
                )
                for row in rows
            ]
