"""
Модели данных для TgBrain.

Модуль предоставляет модели данных для использования в приложении.
Для бизнес-логики используются domain модели с Value Objects,
для персистентности — infrastructure модели с примитивными типами.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, List, Literal, Optional, TypeAlias, TypedDict, Union

from ..domain.value_objects import (
    MessageText,
    SenderName,
    ChatTitle,
)

# TelegramAuth импортируется из domain для обратной совместимости
# Это позволяет коду использовать from src.models.data_models import TelegramAuth
from ..domain.models.auth import TelegramAuth

__all__ = [
    "SummaryStatus",
    "Chat",
    "Message",
    "PendingMessage",
    "TelegramAuth",  # Обратная совместимость
    "ChatSetting",
    "LLMProvider",
    "EmbeddingProvider",
    "AppSetting",
    "ReindexSettings",
    "ReindexTask",
    "ChatSummary",
    "MessageRecord",
    "SummaryRecord",
    "MergedResult",
    "MessageGroup",
    "MessageText",
    "SenderName",
    "ChatTitle",
    "WebhookConfig",
]


JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]


class WebhookConfig(TypedDict, total=False):
    type: str
    url: str
    method: str
    headers: dict[str, str]
    body_template: dict[str, JsonValue]
    message_thread_id: JsonPrimitive



class SummaryStatus(str, Enum):
    """Статусы задачи генерации summary."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Chat:
    """Модель чата."""
    id: int
    title: str
    type: str
    last_message_id: int = 0
    is_active: bool = True
    updated_at: Optional[datetime] = None


@dataclass
class Message:
    """Модель сообщения."""
    id: int
    chat_id: int
    sender_id: Optional[int]
    sender_name: Optional[str]
    message_text: str
    message_date: datetime
    message_link: Optional[str] = None
    embedding: Optional[list[float]] = None
    embedding_model: Optional[str] = None
    is_processed: bool = False
    created_at: Optional[datetime] = None


@dataclass
class PendingMessage:
    """Модель сообщения, ожидающего обработки."""
    id: int
    message_data: dict[str, Any]
    retry_count: int = 0
    last_error: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class ChatSetting:
    """Модель настройки чата (объединённая с Chat)."""
    id: Optional[int]
    chat_id: int
    title: str
    type: str = "private"
    last_message_id: int = 0
    is_monitored: bool = True
    summary_enabled: bool = True
    summary_period_minutes: int = 1440  # 24 часа по умолчанию
    summary_schedule: Optional[str] = None  # cron или "HH:MM"
    custom_prompt: Optional[str] = None
    webhook_config: Optional[WebhookConfig] = None  # Конфигурация webhook (url, method, headers, body_template)
    webhook_enabled: bool = False
    next_schedule_run: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class LLMProvider:
    """Модель LLM провайдера."""
    id: Optional[int]
    name: str
    is_active: bool = False
    api_key: Optional[str] = None
    base_url: str = ""
    model: str = ""
    is_enabled: bool = True
    priority: int = 0
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class EmbeddingProvider:
    """Модель провайдера эмбеддингов."""
    id: Optional[int]
    name: str
    is_active: bool = False
    api_key: Optional[str] = None
    base_url: str = ""
    model: str = ""
    is_enabled: bool = True
    priority: int = 0
    description: Optional[str] = None
    embedding_dim: int = 768
    max_retries: int = 3
    timeout: int = 30
    normalize: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class AppSetting:
    """Модель общей настройки приложения."""
    id: Optional[int]
    key: str
    value: Optional[str]
    value_type: str = "string"
    description: Optional[str] = None
    is_sensitive: bool = False
    updated_at: Optional[datetime] = None

    def get_typed_value(self) -> Any:
        """
        Получить значение с приведением к типу.

        Returns:
            Значение в правильном типе (int, float, bool, str, None).
        """
        if self.value is None:
            return None

        if self.value_type == "int":
            return int(self.value) if self.value else None
        elif self.value_type == "float":
            return float(self.value) if self.value else None
        elif self.value_type == "bool":
            return self.value.lower() in ("true", "1", "yes") if self.value else False
        elif self.value_type == "json":
            import json
            try:
                return json.loads(self.value) if self.value else None
            except json.JSONDecodeError:
                return self.value
        else:  # string
            return self.value


@dataclass
class ReindexSettings:
    """Модель настроек переиндексации."""
    id: int = 1
    batch_size: int = 50
    delay_between_batches: float = 1.0
    auto_reindex_on_model_change: bool = True
    auto_reindex_new_messages: bool = True
    reindex_new_messages_delay: int = 60
    max_concurrent_tasks: int = 1
    max_retries: int = 3
    low_priority_delay: float = 2.0
    normal_priority_delay: float = 1.0
    high_priority_delay: float = 0.5
    last_reindex_model: Optional[str] = None
    speed_mode: str = "medium"  # low, medium, aggressive
    current_batch_size: int = 50  # Может уменьшаться после FloodWait
    updated_at: Optional[datetime] = None


@dataclass
class ReindexTask:
    """Модель задачи переиндексации."""
    id: str
    status: str = "idle"  # idle, running, paused, scheduled, completed, error
    priority: int = 2  # 1=LOW, 2=NORMAL, 3=HIGH
    target_model: str = ""
    total_messages: int = 0
    total_summaries: int = 0
    processed_count: int = 0
    summaries_processed_count: int = 0
    failed_count: int = 0
    summaries_failed_count: int = 0
    batch_size: int = 50
    delay_between_batches: float = 1.0
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    progress_percent: float = 0.0
    summaries_progress_percent: float = 100.0
    total_progress_percent: float = 100.0

    def to_dict(self) -> dict[str, Any]:
        """
        Преобразовать модель задачи переиндексации в словарь.

        Returns:
            dict[str, Any]: Словарь с полями задачи, включая
                прогресс в процентах и временные метки в ISO формате.
        """
        return {
            "id": self.id,
            "status": self.status,
            "priority": self.priority,
            "target_model": self.target_model,
            "total_messages": self.total_messages,
            "total_summaries": self.total_summaries,
            "processed_count": self.processed_count,
            "summaries_processed_count": self.summaries_processed_count,
            "failed_count": self.failed_count,
            "summaries_failed_count": self.summaries_failed_count,
            "batch_size": self.batch_size,
            "delay_between_batches": self.delay_between_batches,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "progress_percent": round(self.progress_percent, 2),
            "summaries_progress_percent": round(self.summaries_progress_percent, 2),
            "total_progress_percent": round(self.total_progress_percent, 2),
        }


@dataclass
class ChatSummary:
    """Модель результата суммаризации (единая для задачи и summary)."""
    id: Optional[int]
    chat_id: int
    created_at: Optional[datetime]
    period_start: datetime
    period_end: datetime
    result_text: str  # ✨ ОСНОВНОЕ ПОЛЕ: результат или ошибка
    messages_count: int = 0
    embedding: Optional[list[float]] = None
    embedding_model: Optional[str] = None
    generated_by: str = "llm"
    metadata: Optional[dict[str, Any]] = None

    # ✨ НОВЫЕ: Поля жизненного цикла задачи
    status: SummaryStatus = SummaryStatus.PENDING
    params_hash: Optional[str] = None
    updated_at: Optional[datetime] = None


# =============================================================================
# ✨ RAG Search Models — Модели для расширенного RAG поиска
# =============================================================================


@dataclass
class MessageRecord:
    """
    Расширенная модель сообщения для RAG поиска.

    Используется для представления сообщения в результатах поиска
    с поддержкой расширения контекста и группировки.
    """
    id: int
    text: MessageText
    date: datetime
    chat_title: ChatTitle
    link: Optional[str]
    sender_name: SenderName
    similarity_score: float = 0.0

    # ✨ Расширенный контекст
    sender_id: int = 0
    is_expanded: bool = False
    grouped_messages: List[MessageRecord] = field(default_factory=list)
    expanded_context: List[MessageRecord] = field(default_factory=list)

    def __post_init__(self):
        """Валидация после инициализации."""
        if not (0.0 <= self.similarity_score <= 1.0):
            raise ValueError(
                f"similarity_score должен быть в диапазоне 0.0-1.0, "
                f"получено {self.similarity_score}"
            )

    def expand_with(self, neighbors: List[MessageRecord]) -> None:
        """
        Расширить сообщение соседними сообщениями.

        Args:
            neighbors: Список соседних сообщений для добавления в контекст.
        """
        self.is_expanded = True
        self.expanded_context = neighbors

    def format_source(self, index: int) -> str:
        """
        Форматировать сообщение как источник для RAG ответа.

        Args:
            index: Порядковый номер источника в списке.

        Returns:
            Форматированная строка с информацией об источнике.
        """
        source_type = "Расширенный контекст" if self.is_expanded else "Сообщение"
        return (
            f"[{index}] {source_type} от {str(self.sender_name)} "
            f"в {str(self.chat_title)} ({self.date.strftime('%Y-%m-%d %H:%M')})"
        )


@dataclass
class SummaryRecord:
    """
    Модель summary для RAG поиска.

    Представляет результат суммаризации как единый блок контекста
    в поисковых результатах.
    """
    id: int
    chat_id: int
    chat_title: ChatTitle
    result_text: str
    period_start: datetime
    period_end: datetime
    messages_count: int
    similarity_score: float = 0.0
    created_at: Optional[datetime] = None

    def __post_init__(self):
        """Валидация после инициализации."""
        if not (0.0 <= self.similarity_score <= 1.0):
            raise ValueError(
                f"similarity_score должен быть в диапазоне 0.0-1.0, "
                f"получено {self.similarity_score}"
            )

    def format_source(self, index: int) -> str:
        """
        Форматировать summary как источник для RAG ответа.

        Args:
            index: Порядковый номер источника в списке.

        Returns:
            Форматированная строка с информацией об источнике.
        """
        return (
            f"[{index}] Summary за период {self.period_start.strftime('%Y-%m-%d')} - "
            f"{self.period_end.strftime('%Y-%m-%d')} ({self.messages_count} сообщений)"
        )


@dataclass
class MergedResult:
    """
    Объединённый результат поиска (сообщения + summary).
    
    Используется для ранжирования и взвешивания результатов
    из разных источников (сообщения и summary).
    """
    message: Union[MessageRecord, SummaryRecord]
    source_type: Literal['message', 'summary']
    similarity_score: float
    weight: float = 1.0

    def __post_init__(self):
        """Валидация после инициализации."""
        if not (0.0 <= self.similarity_score <= 1.0):
            raise ValueError(
                f"similarity_score должен быть в диапазоне 0.0-1.0, "
                f"получено {self.similarity_score}"
            )

    @property
    def weighted_score(self) -> float:
        """
        Вычислить взвешенную оценку сходства.
        
        Returns:
            Произведение similarity_score на weight.
        """
        return self.similarity_score * self.weight


@dataclass
class MessageGroup:
    """
    Группа сообщений от одного отправителя.
    
    Используется для агрегации последовательных сообщений
    от одного пользователя в единый блок контекста.
    """
    sender_id: int
    sender_name: str
    chat_id: int
    chat_title: str
    messages: List[MessageRecord]
    start_date: datetime
    end_date: datetime
    merged_text: str
    similarity_score: float = 0.0

    def __post_init__(self):
        """Валидация после инициализации."""
        if not (0.0 <= self.similarity_score <= 1.0):
            raise ValueError(
                f"similarity_score должен быть в диапазоне 0.0-1.0, "
                f"получено {self.similarity_score}"
            )

    @property
    def grouped_count(self) -> int:
        """
        Получить количество сообщений в группе.
        
        Returns:
            Длина списка messages.
        """
        return len(self.messages)
