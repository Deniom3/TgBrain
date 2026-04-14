"""
Модуль переиндексации сообщений при смене модели эмбеддингов.

Компоненты:
- models: Модели данных (ReindexStats, ReindexStatus, ReindexPriority)
- sql_queries: SQL запросы
- repository: Репозитории для работы с БД
- batch_processor: Пакетная обработка сообщений
- progress_tracker: Отслеживание прогресса
- task_executor: Исполнитель задач
- task_management: Управление задачами
- direct_reindex: Прямая переиндексация
- service: ReindexService (управление сервисом)

Пример использования:
    from src.reindex import ReindexService, ReindexPriority

    service = ReindexService(embeddings_client)
    await service.start_background_service()
    service.schedule_reindex(priority=ReindexPriority.NORMAL)
    status = service.get_status()
    await service.stop_background_service()
"""

from src.reindex.batch_processor import BatchProcessor
from src.reindex.direct_reindex import reindex_all
from src.reindex.models import (
    EmbeddingModelStats,
    ReindexPriority,
    ReindexStats,
    ReindexStatus,
)
from src.reindex.progress_tracker import ProgressTracker
from src.reindex.repository import ReindexSettingsRepository, ReindexTaskRepository
from src.reindex.service import ReindexService
from src.reindex.task_executor import TaskExecutor
from src.reindex.task_management import (
    cancel_task,
    check_model_changed,
    clear_queue,
    schedule_reindex,
)

__all__ = [
    "ReindexService",
    "ReindexStats",
    "EmbeddingModelStats",
    "ReindexStatus",
    "ReindexPriority",
    "BatchProcessor",
    "ProgressTracker",
    "TaskExecutor",
    "ReindexSettingsRepository",
    "ReindexTaskRepository",
    "reindex_all",
    "schedule_reindex",
    "check_model_changed",
    "cancel_task",
    "clear_queue",
]
