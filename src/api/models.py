"""
Pydantic модели для API запросов и ответов.

Модели:
- AskRequest/AskResponse: RAG поиск
- HealthResponse: Проверка здоровья
"""

from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class SearchSource(str, Enum):
    """Источник поиска для RAG."""

    MESSAGES = "messages"
    SUMMARIES = "summaries"
    BOTH = "both"


class AskRequest(BaseModel):
    """Запрос к /api/v1/ask endpoint."""

    question: str = Field(
        ...,
        description="Вопрос пользователя",
        min_length=1,
        max_length=1000,
        examples=["Как настроить авторизацию через QR код?"],
    )
    chat_id: Optional[int] = Field(
        None,
        description="ID чата для фильтрации результатов",
        examples=[-1001234567890],
    )
    search_in: SearchSource = Field(
        SearchSource.MESSAGES,
        description="Источник поиска: messages, summaries, или both",
    )
    expand_context: bool = Field(
        True,
        description="Автоматически расширять контекст для коротких сообщений",
    )
    top_k: int = Field(
        5,
        description="Количество результатов",
        ge=1,
        le=20,
    )
    context_window: int = Field(
        2,
        description="Количество соседних сообщений для расширения",
        ge=0,
        le=5,
    )


class AskSource(BaseModel):
    """Источник в ответе RAG-поиска."""

    id: int = Field(..., description="ID сообщения или summary")
    type: Literal["message", "summary"] = Field(..., description="Тип источника")
    text: str = Field(..., description="Текст сообщения или summary")
    date: str = Field(..., description="Дата в формате ISO 8601")
    chat_title: str = Field(..., description="Название чата")
    link: Optional[str] = Field(None, description="Ссылка на сообщение")
    similarity_score: float = Field(
        ..., description="Оценка схожести (0.0-1.0)", ge=0.0, le=1.0
    )
    is_expanded: bool = Field(..., description="Контекст расширен соседями")
    grouped_count: int = Field(..., description="Количество сообщений в группе")


class ResponseMetadata(BaseModel):
    """Метаданные ответа RAG-поиска."""

    search_source: SearchSource = Field(..., description="Источник поиска")
    total_found: int = Field(..., description="Общее количество результатов")
    context_expanded: bool = Field(..., description="Контекст был расширен")


class AskResponse(BaseModel):
    """Ответ /api/v1/ask endpoint."""

    answer: str = Field(..., description="Сгенерированный ответ LLM")
    sources: List[AskSource] = Field(..., description="Список источников")
    query: str = Field(..., description="Исходный вопрос пользователя")
    metadata: ResponseMetadata = Field(..., description="Метаданные поиска")


class HealthComponent(BaseModel):
    """Статус компонента в /health."""

    status: str
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Ответ /health endpoint."""

    status: str
    components: dict
    timestamp: str


class ErrorDetail(BaseModel):
    """Детали ошибки."""

    code: str = Field(..., description="Код ошибки")
    message: str = Field(..., description="Описание ошибки")


class ErrorResponse(BaseModel):
    """Формат ответа при ошибке."""

    error: ErrorDetail
    field: Optional[str] = None
    rule_code: Optional[str] = None
    retry_after_seconds: Optional[int] = None


__all__ = [
    "AskRequest",
    "AskResponse",
    "AskSource",
    "ResponseMetadata",
    "HealthResponse",
    "HealthComponent",
    "SearchSource",
    "ErrorDetail",
    "ErrorResponse",
]
