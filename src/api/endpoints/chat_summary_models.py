"""
Chat Summary API models — Pydantic модели для запросов и ответов.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ==================== Response Models ====================

class SummaryStatusResponse(BaseModel):
    """
    Универсальный ответ для получения summary/задачи.

    Если status = completed → заполнены result_text, messages_count, etc.
    Если status = pending/processing → заполнены progress_percent
    Если status = failed → заполнен error_message
    """
    id: int
    chat_id: int
    status: str  # pending, processing, completed, failed
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Поля для completed
    result_text: Optional[str] = None
    messages_count: Optional[int] = None
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    generated_by: Optional[str] = None
    metadata: Optional[dict] = None

    # Поля для pending/processing
    progress_percent: float = 0.0

    # Поля для failed
    error_message: Optional[str] = None


class SummaryListItem(BaseModel):
    """Элемент списка summary."""

    id: int
    chat_id: int
    created_at: datetime
    period_start: datetime
    period_end: datetime
    messages_count: int
    generated_by: str
    status: str = "completed"


class SummaryDetail(BaseModel):
    """Детальная информация о summary."""

    id: int
    chat_id: int
    created_at: datetime
    period_start: datetime
    period_end: datetime
    result_text: str
    messages_count: int
    generated_by: str
    metadata: Optional[dict] = None


class SummaryStats(BaseModel):
    """Статистика по summary."""

    chat_id: int
    total_summaries: int
    first_summary: datetime
    last_summary: datetime
    avg_messages: int


# ==================== Request/Response Models ====================

class CleanupRequest(BaseModel):
    """Запрос на очистку старых summary."""

    older_than_days: int = Field(default=30, ge=1, le=365)


class SummaryGenerateRequest(BaseModel):
    """Запрос на генерацию summary для одного чата (асинхронно)."""

    period_minutes: Optional[int] = Field(
        default=None,
        ge=5,
        le=10080,
        description="Период сбора сообщений в минутах (5-10080)"
    )

    period_start: Optional[datetime] = Field(
        default=None,
        description="Начало периода (переопределяет period_minutes)"
    )

    period_end: Optional[datetime] = Field(
        default=None,
        description="Окончание периода (переопределяет period_minutes)"
    )

    custom_prompt: Optional[str] = Field(
        default=None,
        min_length=10,
        max_length=4000,
        description="Кастомный промпт для генерации"
    )

    max_messages: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Максимум сообщений для анализа"
    )

    use_cache: bool = Field(
        default=True,
        description="Использовать кэш при наличии"
    )


class SummaryGenerateTaskResponse(BaseModel):
    """Ответ на создание задачи (один чат)."""
    task_id: Optional[int] = None
    status: str
    from_cache: bool
    message: str
    chat_id: int


class SummaryGenerateAllRequest(BaseModel):
    """Запрос на генерацию summary для всех чатов (асинхронно)."""

    chat_ids: Optional[List[int]] = Field(
        default=None,
        max_length=50,
        description="Список ID чатов (None = все включённые)"
    )

    period_minutes: Optional[int] = Field(
        default=None,
        ge=5,
        le=10080,
        description="Период для всех чатов (переопределяет настройки чата)"
    )

    custom_prompt: Optional[str] = Field(
        default=None,
        min_length=10,
        max_length=4000,
        description="Общий промпт для всех чатов"
    )

    max_messages: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Максимум сообщений на чат"
    )

    use_cache: bool = Field(
        default=True,
        description="Использовать кэш при наличии"
    )


class SummaryTaskItem(BaseModel):
    """Одна задача в массовой генерации."""
    chat_id: int
    task_id: Optional[int] = None
    status: str = "pending"


class SummaryGenerateAllTasksResponse(BaseModel):
    """Ответ на массовое создание задач."""
    tasks: List[SummaryTaskItem]
    total_chats: int
    message: str
    created_at: datetime


__all__ = [
    "SummaryStatusResponse",
    "SummaryListItem",
    "SummaryDetail",
    "SummaryStats",
    "CleanupRequest",
    "SummaryGenerateRequest",
    "SummaryGenerateTaskResponse",
    "SummaryGenerateAllRequest",
    "SummaryTaskItem",
    "SummaryGenerateAllTasksResponse",
]
