"""
Pydantic модели для External Message Ingestion API.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ExternalMessageStatus(str, Enum):
    """
    Статус обработки внешнего сообщения.

    Attributes:
        PROCESSED: Сообщение успешно обработано и сохранено.
        PENDING: Сообщение отложено (например, ожидает векторизации).
        FILTERED: Сообщение отфильтровано (спам, реклама, боты).
        DUPLICATE: Сообщение является дубликатом.
        UPDATED: Сообщение обновлено (редактирование исходного).
    """

    PROCESSED = "processed"
    PENDING = "pending"
    FILTERED = "filtered"
    DUPLICATE = "duplicate"
    UPDATED = "updated"


class ExternalMessageRequest(BaseModel):
    """Запрос на внешнее сообщение."""

    chat_id: int = Field(
        ...,
        description="ID чата в Telegram",
        examples=[-1001234567890, 123456789],
    )
    text: str = Field(
        ...,
        description="Текст сообщения",
        min_length=1,
        max_length=4096,
        examples=["Это тестовое сообщение"],
    )
    date: str = Field(
        ...,
        description="Дата отправки в формате ISO 8601",
        examples=["2026-03-22T10:30:00Z"],
    )
    sender_id: Optional[int] = Field(
        None,
        description="ID отправителя",
        examples=[123456789],
    )
    sender_name: Optional[str] = Field(
        None,
        description="Имя отправителя",
        examples=["User Name"],
    )
    message_link: Optional[str] = Field(
        None,
        description="Ссылка на сообщение",
        examples=["https://t.me/c/1234567890/123"],
    )
    is_bot: bool = Field(
        False,
        description="Отправлено ботом",
    )
    is_action: bool = Field(
        False,
        description="Системное сообщение",
    )


class ExternalMessageResponse(BaseModel):
    """Ответ API внешнего сообщения."""

    success: bool = Field(..., description="Общий статус выполнения")
    status: ExternalMessageStatus = Field(..., description="Детальный статус")
    message_id: Optional[int] = Field(None, description="ID сообщения")
    chat_id: Optional[int] = Field(None, description="ID чата")
    filtered: bool = Field(False, description="Сообщение отфильтровано")
    pending: bool = Field(False, description="Сообщение в pending")
    duplicate: bool = Field(False, description="Сообщение — дубликат")
    updated: bool = Field(False, description="Сообщение обновлено")
    reason: Optional[str] = Field(None, description="Причина (для filtered/pending)")
    error_code: Optional[str] = Field(None, description="Код ошибки (EXT-xxx)")
