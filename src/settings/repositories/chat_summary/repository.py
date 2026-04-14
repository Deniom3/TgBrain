"""
Репозиторий для управления результатами суммаризации.

✨ CRUD операции для кэширования summary по params_hash.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import asyncpg

from ....domain.value_objects import ChatTitle
from ....models.data_models import ChatSummary, SummaryRecord, SummaryStatus
from ....models.sql.summaries import (
    SQL_CLEANUP_OLD_TASKS,
    SQL_CREATE_SUMMARY_TASK,
    SQL_GET_CACHED_SUMMARY,
    SQL_GET_PENDING_TASK,
    SQL_GET_SUMMARY_TASK,
    SQL_UPDATE_SUMMARY_STATUS,
)
from .utils import _row_to_chat_summary

logger = logging.getLogger(__name__)


class ChatSummaryRepository:
    """Репозиторий для работы с результатами суммаризации."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        """
        Инициализация репозитория.

        Args:
            pool: Пул соединений БД.
        """
        self._pool = pool

    # ==================== Управление задачами ====================

    async def create_summary_task(
        self,
        conn: asyncpg.Connection,
        chat_id: int,
        period_start: datetime,
        period_end: datetime,
        params_hash: str,
        metadata: Optional[dict] = None,
    ) -> Optional[Tuple[int, datetime, SummaryStatus]]:
        """
        Создать новую задачу генерации summary.

        Returns:
            (task_id, created_at, status) или None если ошибка.
        """
        try:
            metadata_json = json.dumps(metadata) if metadata else None
            row = await conn.fetchrow(
                SQL_CREATE_SUMMARY_TASK,
                chat_id,
                period_start,
                period_end,
                params_hash,
                metadata_json,
            )
            if row:
                status = SummaryStatus(row["status"])
                return row["id"], row["created_at"], status
        except Exception:
            logger.exception("Ошибка создания задачи summary для чата %s", chat_id)
        return None

    async def update_summary_status(
        self,
        conn: asyncpg.Connection,
        summary_id: int,
        status: SummaryStatus,
        result_text: Optional[str] = None,
        messages_count: Optional[int] = None,
        metadata: Optional[dict] = None,
        embedding: Optional[list[float]] = None,
        embedding_model: Optional[str] = None,
    ) -> bool:
        """Обновить статус задачи."""
        try:
            metadata_json = json.dumps(metadata) if metadata else None
            # Если переданы эмбеддинги, используем SQL с обновлением embedding
            if embedding is not None or embedding_model is not None:
                query = """
                UPDATE chat_summaries
                SET status = $1, updated_at = NOW(),
                    result_text = $2,
                    messages_count = COALESCE($3, messages_count),
                    metadata = $4::JSONB,
                    embedding = COALESCE($5::VECTOR, embedding),
                    embedding_model = COALESCE($6, embedding_model)
                WHERE id = $7
                """
                await conn.execute(
                    query,
                    status.value,
                    result_text,
                    messages_count,
                    metadata_json,
                    embedding,
                    embedding_model,
                    summary_id,
                )
            else:
                await conn.execute(
                    SQL_UPDATE_SUMMARY_STATUS,
                    status.value,
                    result_text,
                    messages_count,
                    metadata_json,
                    summary_id,
                )
            return True
        except Exception:
            logger.exception("Ошибка обновления статуса задачи %s", summary_id)
            return False

    async def get_cached_summary_by_hash(
        self,
        conn: asyncpg.Connection,
        params_hash: str,
        cache_ttl_minutes: Optional[int] = None,
    ) -> Optional[ChatSummary]:
        """
        Получить кэшированное summary по хешу параметров.

        Args:
            cache_ttl_minutes: TTL для кэша (None = без ограничений).
        """
        try:
            if cache_ttl_minutes:
                row = await conn.fetchrow("""
                    SELECT id, status, result_text, created_at, updated_at
                    FROM chat_summaries
                    WHERE params_hash = $1
                      AND status = 'completed'
                      AND created_at >= NOW() - MAKE_INTERVAL(mins => $2)
                    ORDER BY created_at DESC
                    LIMIT 1
                """, params_hash, cache_ttl_minutes)
            else:
                row = await conn.fetchrow(SQL_GET_CACHED_SUMMARY, params_hash)
            
            if row:
                # Для кэшированного summary возвращаем минимальную информацию
                return ChatSummary(
                    id=row["id"],
                    chat_id=0,  # Не используется для кэша
                    status=SummaryStatus(row["status"]),
                    created_at=row["created_at"],
                    result_text=row.get("result_text", ""),  # ✨ Используем только result_text
                    period_start=datetime.min.replace(tzinfo=None),
                    period_end=datetime.min.replace(tzinfo=None),
                    updated_at=row.get("updated_at"),
                )
        except Exception:
            logger.exception("Ошибка получения кэшированного summary по хешу %s", params_hash[:8])
        return None

    async def get_pending_task_by_hash(
        self,
        conn: asyncpg.Connection,
        params_hash: str,
    ) -> Optional[Dict[str, Any]]:
        """Получить активную задачу (pending/processing) по хешу."""
        try:
            row = await conn.fetchrow(SQL_GET_PENDING_TASK, params_hash)
            if row:
                return dict(row)
        except Exception:
            logger.exception("Ошибка получения активной задачи по хешу %s", params_hash[:8])
        return None

    async def get_summary_task(
        self,
        conn: asyncpg.Connection,
        task_id: int,
    ) -> Optional[ChatSummary]:
        """Получить задачу/summary по ID."""
        try:
            row = await conn.fetchrow(SQL_GET_SUMMARY_TASK, task_id)
            return _row_to_chat_summary(row) if row else None
        except Exception:
            logger.exception("Ошибка получения задачи %s", task_id)
            return None

    async def cleanup_old_tasks(
        self,
        conn: asyncpg.Connection,
        older_than_hours: int = 24,
    ) -> int:
        """Удалить старые неудачные/зависшие задачи."""
        try:
            result = await conn.execute(SQL_CLEANUP_OLD_TASKS, older_than_hours)
            parts = result.split()
            return int(parts[1]) if len(parts) > 1 else 0
        except Exception:
            logger.exception("Ошибка очистки старых задач")
            return 0

    async def cleanup_old_failed_tasks(
        self,
        conn: asyncpg.Connection,
        chat_id: int,
        older_than_hours: int = 24,
    ) -> int:
        """Удалить failed-задачи конкретного чата старше указанного времени."""
        query = """
        DELETE FROM chat_summaries
        WHERE chat_id = $1
          AND status = 'failed'
          AND created_at < NOW() - INTERVAL '1 hour' * $2
        """
        try:
            result = await conn.execute(query, chat_id, older_than_hours)
            parts = result.split()
            return int(parts[1]) if len(parts) > 1 else 0
        except Exception:
            logger.exception("Ошибка очистки failed задач для чата %s", chat_id)
            return 0

    # ==================== Мапперы для SummaryRecord (application слой) ====================

    @staticmethod
    def _to_summary_record_from_chat_summary(
        summary: ChatSummary,
        chat_id: int,
    ) -> SummaryRecord:
        """Преобразует ChatSummary в SummaryRecord."""
        return SummaryRecord(
            id=summary.id or 0,
            chat_id=chat_id,
            chat_title=ChatTitle(f"Chat {chat_id}"),
            result_text=summary.result_text or "",
            period_start=summary.period_start,
            period_end=summary.period_end,
            messages_count=0,
            created_at=summary.created_at,
        )

    @staticmethod
    def _to_summary_record_from_dict(
        data: Dict[str, Any],
    ) -> SummaryRecord:
        """Преобразует dict из pending-задачи в SummaryRecord."""
        chat_id = int(data.get("chat_id", 0))
        period_start_raw = data.get("period_start")
        period_end_raw = data.get("period_end")
        period_start: datetime = period_start_raw if isinstance(period_start_raw, datetime) else datetime.min
        period_end: datetime = period_end_raw if isinstance(period_end_raw, datetime) else datetime.min
        return SummaryRecord(
            id=int(data.get("id", 0)),
            chat_id=chat_id,
            chat_title=ChatTitle(f"Chat {chat_id}"),
            result_text="",
            period_start=period_start,
            period_end=period_end,
            messages_count=int(data.get("messages_count", 0)),
            created_at=data.get("created_at"),
        )

    async def get_cached_summary_record_by_hash(
        self,
        conn: asyncpg.Connection,
        params_hash: str,
        cache_ttl_minutes: Optional[int] = None,
    ) -> Optional[SummaryRecord]:
        """Получить кэшированное summary как SummaryRecord."""
        cached = await self.get_cached_summary_by_hash(conn, params_hash, cache_ttl_minutes)
        if cached is None:
            return None
        return self._to_summary_record_from_chat_summary(cached, cached.chat_id or 0)

    async def get_pending_task_record_by_hash(
        self,
        conn: asyncpg.Connection,
        params_hash: str,
    ) -> Optional[SummaryRecord]:
        """Получить pending-задачу как SummaryRecord."""
        pending = await self.get_pending_task_by_hash(conn, params_hash)
        if pending is None:
            return None
        return self._to_summary_record_from_dict(pending)

    async def create_summary_task_with_parsed_dates(
        self,
        conn: asyncpg.Connection,
        chat_id: int,
        period_start_str: str,
        period_end_str: str,
        params_hash: str,
        metadata: Optional[dict] = None,
    ) -> Optional[Tuple[int, datetime, SummaryStatus]]:
        """Создать задачу summary с парсингом дат из строк."""
        try:
            period_start = datetime.fromisoformat(period_start_str)
            period_end = datetime.fromisoformat(period_end_str)
        except (ValueError, TypeError):
            period_start = datetime.now()
            period_end = period_start
        return await self.create_summary_task(
            conn, chat_id, period_start, period_end, params_hash, metadata,
        )

    async def update_status(
        self,
        conn: asyncpg.Connection,
        task_id: int,
        status: str,
        result_text: str | None,
        metadata: dict[str, Any] | None,
        messages_count: int | None = None,
    ) -> None:
        """Обновляет статус задачи (принимает строку, совместимо с протоколом)."""
        try:
            metadata_json = json.dumps(metadata) if metadata else None
            await conn.execute(
                SQL_UPDATE_SUMMARY_STATUS,
                status,
                result_text,
                messages_count,
                metadata_json,
                task_id,
            )
        except Exception:
            logger.exception("Ошибка обновления статуса задачи %s", task_id)

    # ==================== Методы для API (чтение summary) ====================

    async def get_summaries_by_chat(
        self,
        conn: asyncpg.Connection,
        chat_id: int,
        limit: int = 10,
        offset: int = 0,
    ) -> List[ChatSummary]:
        """Получить summary для чата с пагинацией."""
        query = """
        SELECT id, chat_id, created_at, updated_at, period_start, period_end,
               status, params_hash, result_text,
               messages_count, embedding, embedding_model, generated_by, metadata
        FROM chat_summaries
        WHERE chat_id = $1
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """
        try:
            rows = await conn.fetch(query, chat_id, limit, offset)
            return [_row_to_chat_summary(row) for row in rows]
        except Exception:
            logger.exception("Ошибка получения summary для чата %s", chat_id)
            return []

    async def get_latest_summary(
        self, conn: asyncpg.Connection, chat_id: int
    ) -> Optional[ChatSummary]:
        """Получить последнее summary для чата."""
        query = """
        SELECT id, chat_id, created_at, updated_at, period_start, period_end,
               status, params_hash, result_text,
               messages_count, embedding, embedding_model, generated_by, metadata
        FROM chat_summaries
        WHERE chat_id = $1
        ORDER BY created_at DESC
        LIMIT 1
        """
        try:
            row = await conn.fetchrow(query, chat_id)
            return _row_to_chat_summary(row) if row else None
        except Exception:
            logger.exception("Ошибка получения последнего summary для чата %s", chat_id)
            return None

    async def get_summary_by_id(
        self, conn: asyncpg.Connection, summary_id: int
    ) -> Optional[ChatSummary]:
        """Получить summary по ID."""
        query = """
        SELECT id, chat_id, created_at, updated_at, period_start, period_end,
               status, params_hash, result_text,
               messages_count, embedding, embedding_model, generated_by, metadata
        FROM chat_summaries
        WHERE id = $1
        """
        try:
            row = await conn.fetchrow(query, summary_id)
            return _row_to_chat_summary(row) if row else None
        except Exception:
            logger.exception("Ошибка получения summary по ID %s", summary_id)
            return None

    async def get_stats(self, conn: asyncpg.Connection) -> List[Dict[str, Any]]:
        """Получить статистику по summary."""
        query = """
        SELECT
            chat_id,
            COUNT(*) as total_summaries,
            MIN(created_at) as first_summary,
            MAX(created_at) as last_summary,
            AVG(messages_count)::INTEGER as avg_messages
        FROM chat_summaries
        GROUP BY chat_id
        ORDER BY chat_id
        """
        try:
            rows = await conn.fetch(query)
            return [dict(row) for row in rows]
        except Exception:
            logger.exception("Ошибка получения статистики summary")
            return []

    async def delete_summary_by_id(
        self, conn: asyncpg.Connection, summary_id: int
    ) -> bool:
        """Удалить summary по ID."""
        query = "DELETE FROM chat_summaries WHERE id = $1"
        try:
            result = await conn.execute(query, summary_id)
            return result == "DELETE 1"
        except Exception:
            logger.exception("Ошибка удаления summary %s", summary_id)
            return False

    async def delete_old_summaries(
        self, conn: asyncpg.Connection, chat_id: int, older_than: datetime
    ) -> int:
        """Удалить старые summary."""
        query = """
        DELETE FROM chat_summaries
        WHERE chat_id = $1 AND created_at < $2
        """
        try:
            result = await conn.execute(query, chat_id, older_than)
            parts = result.split()
            return int(parts[1]) if len(parts) > 1 else 0
        except Exception:
            logger.exception("Ошибка удаления старых summary для чата %s", chat_id)
            return 0

    async def check_summary_exists(
        self,
        conn: asyncpg.Connection,
        chat_id: int,
        period_start: datetime,
        period_end: datetime,
    ) -> bool:
        """Проверить существует ли summary за период."""
        query = """
        SELECT COUNT(*) as count
        FROM chat_summaries
        WHERE chat_id = $1
          AND period_start = $2
          AND period_end = $3
        """
        try:
            row = await conn.fetchrow(query, chat_id, period_start, period_end)
            return row["count"] > 0 if row else False
        except Exception:
            logger.exception("Ошибка проверки существования summary")
            return False

    # ==================== Обёртки для API (инкапсуляция _pool.acquire()) ====================

    async def get_summaries_by_chat_with_pool(
        self, chat_id: int, limit: int, offset: int
    ) -> List[ChatSummary]:
        """Получить summary для чата с пагинацией (с управлением пулом)."""
        async with self._pool.acquire() as conn:
            return await self.get_summaries_by_chat(conn, chat_id, limit, offset)

    async def get_latest_summary_with_pool(
        self, chat_id: int
    ) -> Optional[ChatSummary]:
        """Получить последнее summary для чата (с управлением пулом)."""
        async with self._pool.acquire() as conn:
            return await self.get_latest_summary(conn, chat_id)

    async def get_summary_task_with_pool(
        self, summary_id: int
    ) -> Optional[ChatSummary]:
        """Получить задачу/summary по ID (с управлением пулом)."""
        async with self._pool.acquire() as conn:
            return await self.get_summary_task(conn, summary_id)

    async def get_summary_by_id_with_pool(
        self, summary_id: int
    ) -> Optional[ChatSummary]:
        """Получить summary по ID (с управлением пулом)."""
        async with self._pool.acquire() as conn:
            return await self.get_summary_by_id(conn, summary_id)

    async def delete_summary_by_id_with_pool(
        self, summary_id: int
    ) -> bool:
        """Удалить summary по ID (с управлением пулом)."""
        async with self._pool.acquire() as conn:
            return await self.delete_summary_by_id(conn, summary_id)

    async def delete_old_summaries_with_pool(
        self, chat_id: int, cutoff: datetime
    ) -> int:
        """Удалить старые summary (с управлением пулом)."""
        async with self._pool.acquire() as conn:
            return await self.delete_old_summaries(conn, chat_id, cutoff)

    async def get_stats_with_pool(self) -> List[Dict[str, Any]]:
        """Получить статистику по summary (с управлением пулом)."""
        async with self._pool.acquire() as conn:
            return await self.get_stats(conn)
