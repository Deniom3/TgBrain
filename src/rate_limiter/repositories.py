"""
Репозитории для Rate Limiter.

Работа с таблицами:
- request_statistics: Статистика запросов
- flood_wait_incidents: Инциденты FloodWait
"""

import logging
from datetime import datetime
from typing import List, Optional

import asyncpg

from .models import FloodWaitIncident, RequestStatistics, ThroughputStats

logger = logging.getLogger(__name__)


class RequestStatisticsRepository:
    """Репозиторий для статистики запросов."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        """
        Инициализировать репозиторий.

        Args:
            pool: Пул подключений к БД.
        """
        self._pool = pool

    async def save(self, stat: RequestStatistics) -> Optional[RequestStatistics]:
        """
        Сохранить статистику запроса.

        Args:
            stat: Статистика для сохранения.

        Returns:
            Сохранённая статистика или None.
        """
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(
                    """
                    INSERT INTO request_statistics (
                        method_name, chat_id, priority, execution_time_ms,
                        is_success, error_message
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING *
                    """,
                    stat.method_name,
                    stat.chat_id,
                    stat.priority,
                    stat.execution_time_ms,
                    stat.is_success,
                    stat.error_message,
                )
                if row:
                    return RequestStatistics(
                        id=row["id"],
                        method_name=row["method_name"],
                        chat_id=row["chat_id"],
                        priority=row["priority"],
                        execution_time_ms=row["execution_time_ms"],
                        is_success=row["is_success"],
                        error_message=row["error_message"],
                        created_at=row["created_at"],
                    )
                return None
            except Exception as e:
                logger.error(f"Ошибка сохранения статистики запроса: {e}")
                return None

    async def get_throughput(self, minutes: int = 60) -> ThroughputStats:
        """
        Получить статистику пропускной способности.

        Args:
            minutes: Период в минутах для статистики.

        Returns:
            Статистика пропускной способности.
        """
        async with self._pool.acquire() as conn:
            try:
                # Статистика за последнюю минуту
                minute_stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE is_success = TRUE) as success,
                        COUNT(*) FILTER (WHERE is_success = FALSE) as errors,
                        AVG(execution_time_ms) as avg_time
                    FROM request_statistics
                    WHERE created_at >= NOW() - INTERVAL '1 minute'
                """)

                # Статистика за последний час
                hour_stats = await conn.fetchrow("""
                    SELECT COUNT(*) as total
                    FROM request_statistics
                    WHERE created_at >= NOW() - INTERVAL '1 hour'
                """)

                # Количество инцидентов FloodWait за последний час
                flood_stats = await conn.fetchval("""
                    SELECT COUNT(*)
                    FROM flood_wait_incidents
                    WHERE created_at >= NOW() - INTERVAL '1 hour'
                """)

                return ThroughputStats(
                    requests_per_minute=minute_stats["total"] or 0,
                    requests_per_hour=hour_stats["total"] or 0,
                    success_count=minute_stats["success"] or 0,
                    error_count=minute_stats["errors"] or 0,
                    avg_execution_time_ms=float(minute_stats["avg_time"] or 0),
                    flood_wait_count=flood_stats or 0,
                )
            except Exception as e:
                logger.error(f"Ошибка получения статистики: {e}")
                return ThroughputStats()

    async def get_recent(self, limit: int = 100) -> List[RequestStatistics]:
        """
        Получить последние запросы.

        Args:
            limit: Максимальное количество записей.

        Returns:
            Список статистики запросов.
        """
        async with self._pool.acquire() as conn:
            try:
                rows = await conn.fetch(
                    """
                    SELECT * FROM request_statistics
                    ORDER BY created_at DESC
                    LIMIT $1
                    """,
                    limit
                )
                return [
                    RequestStatistics(
                        id=row["id"],
                        method_name=row["method_name"],
                        chat_id=row["chat_id"],
                        priority=row["priority"],
                        execution_time_ms=row["execution_time_ms"],
                        is_success=row["is_success"],
                        error_message=row["error_message"],
                        created_at=row["created_at"],
                    )
                    for row in rows
                ]
            except Exception as e:
                logger.error(f"Ошибка получения истории запросов: {e}")
                return []

    async def clear_old(self, days: int = 7) -> int:
        """
        Очистить старую статистику.

        Args:
            days: Удалять записи старше этого количества дней.

        Returns:
            Количество удалённых записей.
        """
        async with self._pool.acquire() as conn:
            try:
                result = await conn.execute(
                    """
                    DELETE FROM request_statistics
                    WHERE created_at < NOW() - ($1::integer * INTERVAL '1 day')
                    """,
                    days
                )
                # Возвращаем количество удалённых записей
                return int(result.split()[-1]) if result else 0
            except Exception as e:
                logger.error(f"Ошибка очистки старой статистики: {e}")
                return 0


class FloodWaitIncidentRepository:
    """Репозиторий для инцидентов FloodWait."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        """
        Инициализировать репозиторий.

        Args:
            pool: Пул подключений к БД.
        """
        self._pool = pool

    async def save(self, incident: FloodWaitIncident) -> Optional[FloodWaitIncident]:
        """
        Сохранить инцидент FloodWait.

        Args:
            incident: Инцидент для сохранения.

        Returns:
            Сохранённый инцидент или None.
        """
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(
                    """
                    INSERT INTO flood_wait_incidents (
                        method_name, chat_id, error_seconds, actual_wait_seconds,
                        batch_size_before, batch_size_after, resolved_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING *
                    """,
                    incident.method_name,
                    incident.chat_id,
                    incident.error_seconds,
                    incident.actual_wait_seconds,
                    incident.batch_size_before,
                    incident.batch_size_after,
                    incident.resolved_at or datetime.now(),
                )
                if row:
                    return FloodWaitIncident(
                        id=row["id"],
                        method_name=row["method_name"],
                        chat_id=row["chat_id"],
                        error_seconds=row["error_seconds"],
                        actual_wait_seconds=row["actual_wait_seconds"],
                        batch_size_before=row["batch_size_before"],
                        batch_size_after=row["batch_size_after"],
                        resolved_at=row["resolved_at"],
                        created_at=row["created_at"],
                    )
                return None
            except Exception as e:
                logger.error(f"Ошибка сохранения инцидента FloodWait: {e}")
                return None

    async def get_recent(self, limit: int = 50) -> List[FloodWaitIncident]:
        """
        Получить последние инциденты.

        Args:
            limit: Максимальное количество записей.

        Returns:
            Список инцидентов.
        """
        async with self._pool.acquire() as conn:
            try:
                rows = await conn.fetch(
                    """
                    SELECT * FROM flood_wait_incidents
                    ORDER BY created_at DESC
                    LIMIT $1
                    """,
                    limit
                )
                return [
                    FloodWaitIncident(
                        id=row["id"],
                        method_name=row["method_name"],
                        chat_id=row["chat_id"],
                        error_seconds=row["error_seconds"],
                        actual_wait_seconds=row["actual_wait_seconds"],
                        batch_size_before=row["batch_size_before"],
                        batch_size_after=row["batch_size_after"],
                        resolved_at=row["resolved_at"],
                        created_at=row["created_at"],
                    )
                    for row in rows
                ]
            except Exception as e:
                logger.error(f"Ошибка получения истории инцидентов: {e}")
                return []

    async def get_count(self, hours: int = 24) -> int:
        """
        Получить количество инцидентов за период.

        Args:
            hours: Период в часах.

        Returns:
            Количество инцидентов.
        """
        async with self._pool.acquire() as conn:
            try:
                count = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM flood_wait_incidents
                    WHERE created_at >= NOW() - ($1::integer * INTERVAL '1 hour')
                    """,
                    hours
                )
                return count or 0
            except Exception as e:
                logger.error(f"Ошибка подсчёта инцидентов: {e}")
                return 0

    async def get_stats(self, hours: int = 24) -> dict:
        """
        Получить статистику инцидентов.

        Args:
            hours: Период в часах.

        Returns:
            Словарь со статистикой.
        """
        async with self._pool.acquire() as conn:
            try:
                stats = await conn.fetchrow("""
                    SELECT
                        COUNT(*) as total,
                        AVG(error_seconds) as avg_error_seconds,
                        AVG(actual_wait_seconds) as avg_actual_wait,
                        MAX(error_seconds) as max_error_seconds
                    FROM flood_wait_incidents
                    WHERE created_at >= NOW() - ($1::integer * INTERVAL '1 hour')
                    """,
                    hours)

                return {
                    "total": stats["total"] or 0,
                    "avg_error_seconds": float(stats["avg_error_seconds"] or 0),
                    "avg_actual_wait": float(stats["avg_actual_wait"] or 0),
                    "max_error_seconds": stats["max_error_seconds"] or 0,
                }
            except Exception as e:
                logger.error(f"Ошибка получения статистики инцидентов: {e}")
                return {
                    "total": 0,
                    "avg_error_seconds": 0.0,
                    "avg_actual_wait": 0.0,
                    "max_error_seconds": 0,
                }
