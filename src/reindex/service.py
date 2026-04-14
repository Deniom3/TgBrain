"""
ReindexService — управление фоновым сервисом переиндексации.

Только управление:
- Запуск/остановка фонового сервиса
- Управление очередью задач
- Делегирование выполнения задачи

Пример использования:
    from src.reindex import ReindexService

    service = ReindexService(embeddings_client)
    await service.start_background_service()
    service.schedule_reindex(priority=ReindexPriority.NORMAL)
    await service.stop_background_service()
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import asyncpg

from src.embeddings import EmbeddingsClient
from src.models.data_models import ReindexSettings, ReindexTask
from src.reindex.models import EmbeddingModelStats, ReindexPriority, ReindexStats, ReindexStatus
from src.reindex.progress_tracker import ProgressTracker
from src.reindex.repository import ReindexSettingsRepository, ReindexTaskRepository
from src.reindex.task_executor import TaskExecutor
from src.reindex.task_management import (
    cancel_task,
    clear_queue,
    schedule_reindex,
)

if TYPE_CHECKING:
    from src.config import Settings

logger = logging.getLogger(__name__)


class ReindexService:
    """
    Сервис управления переиндексацией.

    Особенности:
    - Фоновая обработка без блокировки API
    - Очередь задач с приоритетами
    - Приостановка/возобновление
    - Progress tracking
    """

    def __init__(
        self,
        embeddings_client: Optional[EmbeddingsClient] = None,
        settings: Optional[ReindexSettings] = None,
        reindex_settings_repo: ReindexSettingsRepository = None,  # type: ignore[assignment]
        reindex_task_repo: ReindexTaskRepository = None,  # type: ignore[assignment]
        db_pool: asyncpg.Pool = None,
    ):
        """
        Инициализировать сервис.

        Args:
            embeddings_client: Клиент эмбеддингов.
            settings: Настройки переиндексации.
            reindex_settings_repo: Репозиторий настроек переиндексации.
            reindex_task_repo: Репозиторий задач переиндексации.
            db_pool: Пул подключений к БД.
        """
        self._embeddings_client = embeddings_client
        self._settings = settings
        self._reindex_settings_repo = reindex_settings_repo
        self._reindex_task_repo = reindex_task_repo
        self._db_pool = db_pool
        self._stats = ReindexStats()
        self._lock = asyncio.Lock()
        self._cancelled = False
        self._paused = False

        self._running = False
        self._background_task: Optional[asyncio.Task] = None
        self._task_queue: List[ReindexTask] = []
        self._current_task: Optional[ReindexTask] = None
        self._new_task_event = asyncio.Event()
        self._progress_tracker = ProgressTracker()

        logger.info("ReindexService инициализирован")

    @property
    def stats(self) -> ReindexStats:
        return self._stats

    @property
    def is_running(self) -> bool:
        return self._stats.is_running

    @property
    def is_background_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def current_task(self) -> Optional[ReindexTask]:
        return self._current_task

    @property
    def settings(self) -> ReindexSettings:
        return self._settings or ReindexSettings()

    def set_embeddings_client(self, client: EmbeddingsClient) -> None:
        self._embeddings_client = client

    def refresh_config(self, new_settings: "Settings") -> None:
        """Обновить ссылку на Settings после reload.

        ReindexService хранит собственные настройки (ReindexSettings),
        но метод добавлен для единообразия с другими сервисами.

        Args:
            new_settings: Новый экземпляр Settings.
        """
        logger.debug("ReindexService обновлён")

    async def load_settings(self) -> ReindexSettings:
        self._settings = await self._reindex_settings_repo.get() or ReindexSettings()
        logger.info(f"Настройки загружены: batch_size={self._settings.batch_size}")
        return self._settings

    async def save_settings(self, settings: ReindexSettings) -> ReindexSettings:
        self._settings = await self._reindex_settings_repo.upsert(settings)
        logger.info("Настройки сохранены")
        return self._settings

    async def start_background_service(self) -> None:
        """Запустить фоновый сервис."""
        if self._running:
            logger.warning("Фоновый сервис уже запущен")
            return

        await self.load_settings()
        self._running = True
        self._paused = False
        self._background_task = asyncio.create_task(self._background_loop())
        logger.info("Фоновый сервис запущен")

    async def stop_background_service(self) -> None:
        """Остановить фоновый сервис."""
        self._running = False
        self._new_task_event.set()

        if self._background_task:
            try:
                self._background_task.cancel()
                await self._background_task
            except asyncio.CancelledError:
                pass

        if self._current_task:
            await self._cancel_task()

        logger.info("Фоновый сервис остановлен")

    async def _background_loop(self) -> None:
        """Фоновый цикл обработки задач."""
        while self._running:
            try:
                if not self._task_queue:
                    try:
                        await asyncio.wait_for(
                            self._new_task_event.wait(), timeout=5.0
                        )
                        self._new_task_event.clear()
                    except asyncio.TimeoutError:
                        continue

                if self._paused:
                    await asyncio.sleep(1)
                    continue

                async with self._lock:
                    if not self._task_queue:
                        continue

                    self._task_queue.sort(key=lambda t: t.priority, reverse=True)
                    self._current_task = self._task_queue.pop(0)

                if self._current_task:
                    await self._execute_task(self._current_task)
                    await self._reindex_task_repo.save(self._current_task)
                    self._current_task = None

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в фоновом цикле: {e}", exc_info=True)
                await asyncio.sleep(5)

    def schedule_reindex(
        self,
        priority: ReindexPriority = ReindexPriority.NORMAL,
        batch_size: Optional[int] = None,
        delay: Optional[float] = None,
        force: bool = False,
    ) -> str:
        """Запланировать переиндексацию."""
        if not self._settings:
            raise RuntimeError("Настройки переиндексации не инициализированы")
        return schedule_reindex(
            self._task_queue,
            self._new_task_event,
            self._embeddings_client,
            self._settings,
            priority,
            batch_size,
            delay,
            force,
        )

    async def pause(self) -> None:
        """Приостановить переиндексацию."""
        self._paused = True
        logger.info("Переиндексация приостановлена")

    async def resume(self) -> None:
        """Возобновить переиндексацию."""
        self._paused = False
        self._new_task_event.set()
        logger.info("Переиндексация возобновлена")

    async def cancel_current_task(self) -> bool:
        """Отменить текущую задачу."""
        if self._current_task:
            await self._cancel_task()
            return True
        return False

    async def _cancel_task(self) -> None:
        """Отмена задачи."""
        if self._current_task:
            cancel_task(self._current_task)

    def clear_queue(self) -> int:
        """Очистить очередь задач."""
        return clear_queue(self._task_queue)

    async def _execute_task(self, task: ReindexTask) -> None:
        """Выполнить задачу (делегирование TaskExecutor)."""
        if not self._embeddings_client:
            task.status = ReindexStatus.ERROR.value
            task.error = "Embeddings client not initialized"
            task.completed_at = task.completed_at or task.started_at
            return

        if not self._settings:
            raise RuntimeError("Настройки переиндексации не инициализированы")

        executor = TaskExecutor(
            self._embeddings_client,
            self._settings,
            self._stats,
            self._progress_tracker,
            self._reindex_task_repo,
            self._reindex_settings_repo,
            self._db_pool,
        )

        await executor.execute_task(
            task,
            running=self._running,
            paused=self._paused,
            cancelled=self._cancelled,
        )

    async def check_reindex_needed(
        self, target_model: str
    ) -> Tuple[bool, int]:
        """Проверить необходимость переиндексации."""
        record = await self._db_pool.fetchrow(
            "SELECT COUNT(*) as count FROM messages WHERE embedding IS NULL OR embedding_model != $1::TEXT",
            target_model,
        )
        count = record["count"] if record else 0

        logger.info(
            f"Проверка переиндексации: модель={target_model}, сообщений={count}"
        )
        return count > 0, count

    def check_and_schedule_reindex(self) -> bool:
        """Проверить и запланировать переиндексацию."""
        if not self.settings.auto_reindex_on_model_change:
            return False

        if not self._embeddings_client:
            return False

        current_model = self._embeddings_client.get_model_name()
        import asyncio
        loop = asyncio.get_event_loop()
        needs_reindex, count = loop.run_until_complete(
            self._check_reindex_needed(current_model)
        )

        if needs_reindex and count > 0:
            logger.info(f"Смена модели. Запланирована переиндексация {count} сообщений")
            self.schedule_reindex(priority=ReindexPriority.NORMAL)
            return True

        return False

    async def _check_reindex_needed(
        self, target_model: str
    ) -> Tuple[bool, int]:
        """Проверить необходимость (async версия)."""
        record = await self._db_pool.fetchrow(
            "SELECT COUNT(*) as count FROM messages WHERE embedding IS NULL OR embedding_model != $1::TEXT",
            target_model,
        )
        count = record["count"] if record else 0
        return count > 0, count

    async def get_embedding_model_stats(self) -> List[EmbeddingModelStats]:
        """Получить статистику по моделям."""
        records = await self._db_pool.fetch(
            """
            SELECT embedding_model, COUNT(*) as message_count,
                   MIN(message_date) as first_message, MAX(message_date) as last_message
            FROM messages WHERE embedding IS NOT NULL
            GROUP BY embedding_model ORDER BY message_count DESC
            """
        )

        return [
            EmbeddingModelStats(
                model_name=r["embedding_model"],
                message_count=r["message_count"],
                first_message=r["first_message"],
                last_message=r["last_message"],
            )
            for r in records
        ]

    async def get_embedding_model_stats_dict(self) -> Dict[str, Dict[str, Any]]:
        """Получить статистику в виде словаря."""
        stats = await self.get_embedding_model_stats()
        return {
            s.model_name: {
                "message_count": s.message_count,
                "first_message": s.first_message.isoformat() if s.first_message else None,
                "last_message": s.last_message.isoformat() if s.last_message else None,
            }
            for s in stats
        }

    def get_status(self) -> Dict[str, Any]:
        """Получить статус сервиса."""
        return {
            "running": self._running,
            "paused": self._paused,
            "is_running": self._stats.is_running,
            "current_task": self._current_task.to_dict() if self._current_task else None,
            "queued_tasks": len(self._task_queue),
            "stats": self._stats.to_dict(),
        }

    def get_progress(self) -> Dict[str, Any]:
        """Получить прогресс."""
        return self._progress_tracker.get_summary(self._stats)

    async def get_task_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Получить историю задач."""
        tasks = await self._reindex_task_repo.get_history(limit)
        return [t.to_dict() for t in tasks]

    async def reindex_all(
        self,
        batch_size: int = 100,
        delay_between_batches: float = 0.5,
        progress_callback=None,
    ) -> ReindexStats:
        """Прямая переиндексация (без очереди)."""
        from src.reindex.direct_reindex import reindex_all as reindex_func

        if not self._embeddings_client:
            raise ValueError("Не установлен embeddings_client")
        return await reindex_func(
            self._embeddings_client,
            self._stats,
            batch_size,
            delay_between_batches,
            progress_callback,
        )

    def cancel(self) -> None:
        """Отменить переиндексацию."""
        self._cancelled = True
        logger.info("Переиндексация отменена")


__all__ = ["ReindexService"]
