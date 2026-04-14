"""
Репозитории для переиндексации.

Классы:
- ReindexSettingsRepository: Работа с настройками переиндексации
- ReindexTaskRepository: Работа с задачами переиндексации
"""

import logging
from typing import List, Optional

import asyncpg
from src.models.data_models import ReindexSettings, ReindexTask

logger = logging.getLogger(__name__)


class ReindexSettingsRepository:
    """Репозиторий для настроек переиндексации."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        """
        Инициализировать репозиторий.

        Args:
            pool: Пул подключений к БД.
        """
        self._pool = pool

    async def get(self) -> Optional[ReindexSettings]:
        """
        Получить настройки переиндексации.

        Returns:
            Настройки переиндексации или None.
        """
        record = await self._pool.fetchrow(
            "SELECT id, batch_size, delay_between_batches, "
            "low_priority_delay, normal_priority_delay, high_priority_delay, "
            "auto_reindex_on_model_change, last_reindex_model "
            "FROM reindex_settings LIMIT 1"
        )

        if not record:
            return None

        return ReindexSettings(
            batch_size=record["batch_size"],
            delay_between_batches=record["delay_between_batches"],
            low_priority_delay=record["low_priority_delay"],
            normal_priority_delay=record["normal_priority_delay"],
            high_priority_delay=record["high_priority_delay"],
            auto_reindex_on_model_change=record["auto_reindex_on_model_change"],
            last_reindex_model=record["last_reindex_model"],
        )

    async def upsert(self, settings: ReindexSettings) -> ReindexSettings:
        """
        Сохранить настройки переиндексации (insert или update).

        Args:
            settings: Настройки для сохранения.

        Returns:
            Сохранённые настройки.
        """
        await self._pool.execute(
            """
            INSERT INTO reindex_settings (
                batch_size,
                delay_between_batches,
                low_priority_delay,
                normal_priority_delay,
                high_priority_delay,
                auto_reindex_on_model_change,
                last_reindex_model
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (id) DO UPDATE SET
                batch_size = EXCLUDED.batch_size,
                delay_between_batches = EXCLUDED.delay_between_batches,
                low_priority_delay = EXCLUDED.low_priority_delay,
                normal_priority_delay = EXCLUDED.normal_priority_delay,
                high_priority_delay = EXCLUDED.high_priority_delay,
                auto_reindex_on_model_change = EXCLUDED.auto_reindex_on_model_change,
                last_reindex_model = EXCLUDED.last_reindex_model
            """,
            settings.batch_size,
            settings.delay_between_batches,
            settings.low_priority_delay,
            settings.normal_priority_delay,
            settings.high_priority_delay,
            settings.auto_reindex_on_model_change,
            settings.last_reindex_model,
        )

        return settings

    async def set_last_reindex_model(self, model_name: str) -> None:
        """
        Установить последнюю успешную модель переиндексации.

        Args:
            model_name: Имя модели.
        """
        await self._pool.execute(
            "UPDATE reindex_settings SET last_reindex_model = $1",
            model_name,
        )
        logger.info(f"last_reindex_model установлена: {model_name}")

    async def update_last_reindex_model(self, model_name: Optional[str]) -> None:
        """
        Обновить last_reindex_model (может быть None).

        Args:
            model_name: Имя модели или None для сброса.
        """
        await self._pool.execute(
            "UPDATE reindex_settings SET last_reindex_model = $1, updated_at = NOW()",
            model_name,
        )
        logger.info(f"last_reindex_model обновлена: {model_name}")


class ReindexTaskRepository:
    """Репозиторий для задач переиндексации."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        """
        Инициализировать репозиторий.

        Args:
            pool: Пул подключений к БД.
        """
        self._pool = pool

    async def save(self, task: ReindexTask) -> None:
        """
        Сохранить задачу переиндексации.

        Args:
            task: Задача для сохранения.
        """
        await self._pool.execute(
            """
            INSERT INTO reindex_tasks (
                id,
                status,
                priority,
                target_model,
                batch_size,
                delay_between_batches,
                total_messages,
                processed_count,
                failed_count,
                progress_percent,
                started_at,
                completed_at,
                error
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                priority = EXCLUDED.priority,
                target_model = EXCLUDED.target_model,
                batch_size = EXCLUDED.batch_size,
                delay_between_batches = EXCLUDED.delay_between_batches,
                total_messages = EXCLUDED.total_messages,
                processed_count = EXCLUDED.processed_count,
                failed_count = EXCLUDED.failed_count,
                progress_percent = EXCLUDED.progress_percent,
                started_at = EXCLUDED.started_at,
                completed_at = EXCLUDED.completed_at,
                error = EXCLUDED.error
            """,
            task.id,
            task.status,
            task.priority,
            task.target_model,
            task.batch_size,
            task.delay_between_batches,
            task.total_messages,
            task.processed_count,
            task.failed_count,
            task.progress_percent,
            task.started_at,
            task.completed_at,
            task.error,
        )

    async def update(self, task: ReindexTask) -> None:
        """
        Обновить прогресс задачи.

        Args:
            task: Задача для обновления.
        """
        await self._pool.execute(
            """
            UPDATE reindex_tasks
            SET
                status = $1,
                processed_count = $2,
                failed_count = $3,
                progress_percent = $4
            WHERE id = $5
            """,
            task.status,
            task.processed_count,
            task.failed_count,
            task.progress_percent,
            task.id,
        )

    async def get_history(self, limit: int = 10) -> List[ReindexTask]:
        """
        Получить историю задач.

        Args:
            limit: Количество задач.

        Returns:
            Список задач.
        """
        records = await self._pool.fetch(
            """
            SELECT id, status, priority, target_model, batch_size,
                   delay_between_batches, total_messages,
                   processed_count,
                   failed_count,
                   progress_percent, started_at, completed_at, error
            FROM reindex_tasks
            ORDER BY started_at DESC
            LIMIT $1
            """,
            limit,
        )

        tasks = []
        for record in records:
            tasks.append(ReindexTask(
                id=record["id"],
                status=record["status"],
                priority=record["priority"],
                target_model=record["target_model"],
                batch_size=record["batch_size"],
                delay_between_batches=record["delay_between_batches"],
                total_messages=record["total_messages"],
                total_summaries=0,
                processed_count=record["processed_count"],
                summaries_processed_count=0,
                failed_count=record["failed_count"],
                summaries_failed_count=0,
                progress_percent=record["progress_percent"],
                summaries_progress_percent=100.0,
                total_progress_percent=100.0,
                started_at=record["started_at"],
                completed_at=record["completed_at"],
                error=record["error"],
            ))

        return tasks

    async def get_by_id(self, task_id: str) -> Optional[ReindexTask]:
        """
        Получить задачу по ID.

        Args:
            task_id: ID задачи.

        Returns:
            Задача или None.
        """
        record = await self._pool.fetchrow(
            "SELECT id, status, priority, target_model, batch_size, "
            "delay_between_batches, total_messages, "
            "processed_count, "
            "failed_count, "
            "progress_percent, started_at, completed_at, error "
            "FROM reindex_tasks WHERE id = $1",
            task_id,
        )

        if not record:
            return None

        return ReindexTask(
            id=record["id"],
            status=record["status"],
            priority=record["priority"],
            target_model=record["target_model"],
            batch_size=record["batch_size"],
            delay_between_batches=record["delay_between_batches"],
            total_messages=record["total_messages"],
            total_summaries=0,
            processed_count=record["processed_count"],
            summaries_processed_count=0,
            failed_count=record["failed_count"],
            summaries_failed_count=0,
            progress_percent=record["progress_percent"],
            summaries_progress_percent=100.0,
            total_progress_percent=100.0,
            started_at=record["started_at"],
            completed_at=record["completed_at"],
            error=record["error"],
        )

