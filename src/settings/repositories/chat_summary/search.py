"""
Векторный поиск по результатам суммаризации.

RAG-поиск по сохранённым дайджестам.
"""

import logging
from typing import List, Optional

import asyncpg

from ....domain.value_objects import ChatTitle
from ....models.data_models import SummaryRecord

logger = logging.getLogger(__name__)


class ChatSummarySearchService:
    """Сервис для векторного поиска по summary."""

    def __init__(self, db_pool: asyncpg.Pool):
        """
        Инициализация сервиса поиска по summary.

        Args:
            db_pool: Пул подключений к PostgreSQL.
        """
        self.db_pool = db_pool

    async def search_summaries(
        self,
        query_embedding: List[float],
        limit: int = 5,
        chat_id: Optional[int] = None
    ) -> List[SummaryRecord]:
        """
        Векторный поиск по summary.

        Args:
            query_embedding: Вектор запроса.
            limit: Лимит результатов.
            chat_id: ID чата для фильтрации (None = поиск по всем чатам).

        Returns:
            Список SummaryRecord с similarity_score.
        """
        if chat_id:
            query = """
            SELECT
                cs.id,
                cs.chat_id,
                cs.created_at,
                cs.period_start,
                cs.period_end,
                cs.result_text,
                cs.messages_count,
                cs.generated_by,
                1 - (cs.embedding <=> $1::VECTOR) as similarity_score,
                cht.title as chat_title
            FROM chat_summaries cs
            LEFT JOIN chat_settings cht ON cs.chat_id = cht.chat_id
            WHERE cs.embedding IS NOT NULL
              AND cs.chat_id = $3
            ORDER BY similarity_score DESC
            LIMIT $2
            """
            params: tuple = (query_embedding, limit, chat_id)
        else:
            query = """
            SELECT
                cs.id,
                cs.chat_id,
                cs.created_at,
                cs.period_start,
                cs.period_end,
                cs.result_text,
                cs.messages_count,
                cs.generated_by,
                1 - (cs.embedding <=> $1::VECTOR) as similarity_score,
                cht.title as chat_title
            FROM chat_summaries cs
            LEFT JOIN chat_settings cht ON cs.chat_id = cht.chat_id
            WHERE cs.embedding IS NOT NULL
            ORDER BY similarity_score DESC
            LIMIT $2
            """
            params = (query_embedding, limit)

        async with self.db_pool.acquire() as conn:
            try:
                rows = await conn.fetch(query, *params)
                return [
                    SummaryRecord(
                        id=row["id"],
                        chat_id=row["chat_id"],
                        chat_title=ChatTitle(row["chat_title"] or f"Chat {row['chat_id']}"),
                        result_text=row["result_text"],
                        period_start=row["period_start"],
                        period_end=row["period_end"],
                        messages_count=row["messages_count"],
                        similarity_score=float(row["similarity_score"]) if row["similarity_score"] else 0.0,
                        created_at=row["created_at"]
                    )
                    for row in rows
                ]
            except Exception as e:
                logger.error(f"Ошибка векторного поиска по summary: {e}")
                return []
