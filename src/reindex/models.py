"""
Модели данных для переиндексации.

Классы:
- ReindexStatus: Статус переиндексации (enum)
- ReindexPriority: Приоритет переиндексации (enum)
- ReindexStats: Статистика переиндексации
- EmbeddingModelStats: Статистика по моделям эмбеддингов
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ReindexStatus(Enum):
    """Статус переиндексации."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    ERROR = "error"


class ReindexPriority(Enum):
    """Приоритет переиндексации."""
    LOW = 1  # Плановая переиндексация
    NORMAL = 2  # Смена модели
    HIGH = 3  # Критичные сообщения без эмбеддинга


@dataclass
class ReindexStats:
    """Статистика переиндексации."""
    total_messages: int = 0
    messages_to_reindex: int = 0
    reindexed_count: int = 0
    failed_count: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    current_model: str = ""
    is_running: bool = False
    errors: List[str] = field(default_factory=list)
    
    # Поля для отслеживания summary
    summaries_to_reindex: int = 0
    summaries_reindexed_count: int = 0
    summaries_failed_count: int = 0

    @property
    def progress_percent(self) -> float:
        """Процент выполнения для messages."""
        if self.messages_to_reindex == 0:
            return 100.0
        return (self.reindexed_count / self.messages_to_reindex) * 100

    @property
    def summaries_progress_percent(self) -> float:
        """Процент выполнения для summary."""
        if self.summaries_to_reindex == 0:
            return 100.0
        return (self.summaries_reindexed_count / self.summaries_to_reindex) * 100

    @property
    def total_progress_percent(self) -> float:
        """Общий процент выполнения (messages + summary)."""
        total = self.messages_to_reindex + self.summaries_to_reindex
        if total == 0:
            return 100.0
        completed = self.reindexed_count + self.summaries_reindexed_count
        return (completed / total) * 100

    @property
    def elapsed_seconds(self) -> float:
        """Прошло времени с начала."""
        if not self.started_at:
            return 0.0
        end = self.completed_at or datetime.now()
        return (end - self.started_at).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь."""
        return {
            "total_messages": self.total_messages,
            "messages_to_reindex": self.messages_to_reindex,
            "reindexed_count": self.reindexed_count,
            "failed_count": self.failed_count,
            "progress_percent": round(self.progress_percent, 2),
            "summaries_to_reindex": self.summaries_to_reindex,
            "summaries_reindexed_count": self.summaries_reindexed_count,
            "summaries_failed_count": self.summaries_failed_count,
            "summaries_progress_percent": round(self.summaries_progress_percent, 2),
            "total_progress_percent": round(self.total_progress_percent, 2),
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "current_model": self.current_model,
            "is_running": self.is_running,
            "has_errors": len(self.errors) > 0,
            "error_count": len(self.errors),
        }


@dataclass
class EmbeddingModelStats:
    """Статистика по моделям эмбеддингов."""
    model_name: str
    message_count: int
    first_message: Optional[datetime]
    last_message: Optional[datetime]

    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь."""
        return {
            "model_name": self.model_name,
            "message_count": self.message_count,
            "first_message": self.first_message.isoformat() if self.first_message else None,
            "last_message": self.last_message.isoformat() if self.last_message else None,
        }
