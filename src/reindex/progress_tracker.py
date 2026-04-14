"""
Progress tracking для переиндексации.

Отслеживание прогресса выполнения задач переиндексации:
- Обновление статистики после каждого batch'а
- Расчёт оставшегося времени
- История прогресса
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.reindex.models import ReindexStats

logger = logging.getLogger(__name__)


class ProgressTracker:
    """
    Трекер прогресса переиндексации.

    Особенности:
    - Обновление статистики в реальном времени
    - Расчёт оставшегося времени (ETA)
    - История изменений прогресса
    - Поддержка нескольких задач
    """

    def __init__(self):
        """Инициализация трекера."""
        self._history: List[Dict[str, Any]] = []
        self._start_time: Optional[datetime] = None
        self._last_update: Optional[datetime] = None

    def start(self, stats: ReindexStats) -> None:
        """
        Начать отслеживание.

        Args:
            stats: Начальная статистика.
        """
        self._start_time = datetime.now()
        self._last_update = self._start_time
        self._history.clear()

        self._record_progress(stats, "started")
        logger.info(
            f"Начало отслеживания прогресса: "
            f"{stats.messages_to_reindex} сообщений, "
            f"{stats.summaries_to_reindex} summary"
        )

    def update(self, stats: ReindexStats) -> None:
        """
        Обновить прогресс.

        Args:
            stats: Текущая статистика.
        """
        self._last_update = datetime.now()
        self._record_progress(stats, "updated")

        # Логирование прогресса каждые 10%
        progress = stats.progress_percent
        if progress % 10 < (stats.reindexed_count / max(stats.messages_to_reindex, 1) * 100):
            logger.info(
                f"Прогресс: {progress:.1f}% "
                f"({stats.reindexed_count}/{stats.messages_to_reindex})"
            )

    def finish(self, stats: ReindexStats, status: str = "completed") -> None:
        """
        Завершить отслеживание.

        Args:
            stats: Финальная статистика.
            status: Статус завершения (completed/error/cancelled).
        """
        self._last_update = datetime.now()
        self._record_progress(stats, status)

        logger.info(
            f"Завершение переиндексации: "
            f"успешно={stats.reindexed_count}, "
            f"ошибок={stats.failed_count}, "
            f"время={stats.elapsed_seconds:.2f}с"
        )

    def _record_progress(self, stats: ReindexStats, event: str) -> None:
        """
        Записать прогресс в историю.

        Args:
            stats: Текущая статистика.
            event: Тип события.
        """
        record = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "reindexed_count": stats.reindexed_count,
            "failed_count": stats.failed_count,
            "progress_percent": stats.progress_percent,
            "is_running": stats.is_running,
        }
        self._history.append(record)

    def get_eta(self, stats: ReindexStats) -> Optional[float]:
        """
        Рассчитать оставшееся время (ETA).

        Args:
            stats: Текущая статистика.

        Returns:
            Оставшееся время в секундах или None.
        """
        if not self._start_time or stats.reindexed_count == 0:
            return None

        elapsed = (datetime.now() - self._start_time).total_seconds()
        rate = stats.reindexed_count / elapsed  # сообщений в секунду

        if rate <= 0:
            return None

        remaining = stats.messages_to_reindex - stats.reindexed_count
        eta = remaining / rate

        return eta

    def get_summary(self, stats: ReindexStats) -> Dict[str, Any]:
        """
        Получить сводку прогресса.

        Args:
            stats: Текущая статистика.

        Returns:
            Словарь с информацией о прогрессе (messages + summary).
        """
        eta = self.get_eta(stats)

        return {
            "progress_percent": round(stats.progress_percent, 2),
            "reindexed_count": stats.reindexed_count,
            "failed_count": stats.failed_count,
            "total_messages": stats.messages_to_reindex,
            "summaries_progress_percent": round(stats.summaries_progress_percent, 2),
            "summaries_reindexed_count": stats.summaries_reindexed_count,
            "summaries_failed_count": stats.summaries_failed_count,
            "summaries_total": stats.summaries_to_reindex,
            "total_progress_percent": round(stats.total_progress_percent, 2),
            "total_completed": stats.reindexed_count + stats.summaries_reindexed_count,
            "total_to_reindex": stats.messages_to_reindex + stats.summaries_to_reindex,
            "elapsed_seconds": round(stats.elapsed_seconds, 2),
            "eta_seconds": round(eta, 2) if eta else None,
            "rate_per_second": round(
                stats.reindexed_count / max(stats.elapsed_seconds, 1), 2
            ),
            "status": "running" if stats.is_running else "idle",
        }

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Получить историю прогресса.

        Args:
            limit: Максимальное количество записей.

        Returns:
            Список записей истории.
        """
        return self._history[-limit:]

    def reset(self) -> None:
        """Сбросить трекер."""
        self._history.clear()
        self._start_time = None
        self._last_update = None
        logger.debug("ProgressTracker сброшен")


class MultiTaskProgressTracker:
    """
    Трекер прогресса для нескольких задач.

    Позволяет отслеживать прогресс нескольких задач переиндексации
    одновременно.
    """

    def __init__(self):
        """Инициализация мульти-трекера."""
        self._trackers: Dict[str, ProgressTracker] = {}

    def get_tracker(self, task_id: str) -> ProgressTracker:
        """
        Получить или создать трекер для задачи.

        Args:
            task_id: ID задачи.

        Returns:
            Трекер прогресса.
        """
        if task_id not in self._trackers:
            self._trackers[task_id] = ProgressTracker()
        return self._trackers[task_id]

    def remove_tracker(self, task_id: str) -> None:
        """
        Удалить трекер задачи.

        Args:
            task_id: ID задачи.
        """
        if task_id in self._trackers:
            del self._trackers[task_id]

    def get_all_summaries(self) -> Dict[str, Dict[str, Any]]:
        """
        Получить сводку по всем задачам.

        Returns:
            Словарь {task_id: summary}.
        """
        return {
            task_id: tracker.get_summary(ReindexStats())
            for task_id, tracker in self._trackers.items()
        }

    def clear(self) -> None:
        """Очистить все трекеры."""
        self._trackers.clear()
