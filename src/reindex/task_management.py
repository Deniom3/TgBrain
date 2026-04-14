"""
Управление задачами переиндексации.

Функции:
- schedule_reindex: Запланировать переиндексацию
- check_model_changed: Проверка смены модели
- cancel_task: Отмена задачи
"""

import logging
from datetime import datetime
from typing import List, Optional

from src.models.data_models import ReindexSettings, ReindexTask
from src.reindex.models import ReindexPriority, ReindexStatus

logger = logging.getLogger(__name__)


def schedule_reindex(
    task_queue: List[ReindexTask],
    new_task_event,
    embeddings_client,
    settings: ReindexSettings,
    priority: ReindexPriority = ReindexPriority.NORMAL,
    batch_size: Optional[int] = None,
    delay: Optional[float] = None,
    force: bool = False,
) -> str:
    """
    Запланировать переиндексацию.

    Args:
        task_queue: Очередь задач.
        new_task_event: Event для уведомления о новой задаче.
        embeddings_client: Клиент эмбеддингов.
        settings: Настройки.
        priority: Приоритет задачи.
        batch_size: Размер пакета.
        delay: Задержка между пакетами.
        force: Принудительный запуск без проверки Smart Trigger.

    Returns:
        ID задачи.
    """
    if not force and not check_model_changed(embeddings_client, settings):
        logger.info("Smart Trigger: модель не изменилась, переиндексация отменена")
        return ""

    task_id = f"reindex_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    task = ReindexTask(
        id=task_id,
        status=ReindexStatus.SCHEDULED.value,
        priority=priority.value,
        target_model=embeddings_client.get_model_name()
        if embeddings_client
        else "",
        batch_size=batch_size or settings.batch_size,
        delay_between_batches=delay or settings.delay_between_batches,
    )

    task_queue.append(task)
    new_task_event.set()

    logger.info(
        f"Запланирована переиндексация: {task_id} (приоритет: {priority.name})"
    )

    return task_id


def check_model_changed(embeddings_client, settings: Optional[ReindexSettings]) -> bool:
    """
    Проверить, изменилась ли активная модель.

    Smart Trigger: переиндексация нужна только если имя модели изменилось.

    Args:
        embeddings_client: Клиент эмбеддингов.
        settings: Настройки.

    Returns:
        True если модель изменилась.
    """
    if not embeddings_client:
        return False

    current_model = embeddings_client.get_model_name()
    last_model = settings.last_reindex_model if settings else None

    if last_model is None:
        logger.info(
            "Smart Trigger: last_reindex_model не установлена, требуется переиндексация"
        )
        return True

    model_changed = current_model != last_model

    if model_changed:
        logger.info(
            f"Smart Trigger: модель изменилась ({last_model} -> {current_model})"
        )
    else:
        logger.info(
            f"Smart Trigger: модель не изменилась ({current_model})"
        )

    return model_changed


def cancel_task(task: ReindexTask) -> None:
    """
    Отменить задачу.

    Args:
        task: Задача для отмены.
    """
    task.status = ReindexStatus.ERROR.value
    task.error = "Cancelled by user"
    task.completed_at = datetime.now()
    logger.info(f"Задача {task.id} отменена пользователем")


def clear_queue(task_queue: List[ReindexTask]) -> int:
    """
    Очистить очередь задач.

    Args:
        task_queue: Очередь задач.

    Returns:
        Количество очищенных задач.
    """
    count = len(task_queue)
    task_queue.clear()
    logger.info(f"Очищено {count} задач из очереди")
    return count
