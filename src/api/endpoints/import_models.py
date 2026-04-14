"""
Pydantic модели для API request/response batch import.

Модели данных для endpoints импорта сообщений из Telegram Desktop.
"""

from datetime import datetime, UTC
from typing import Optional, List

from pydantic import BaseModel, Field


class ImportErrorDetail(BaseModel):
    """Детали ошибки импорта."""

    message_id: Optional[int] = Field(
        default=None,
        description="ID сообщения где произошла ошибка",
    )
    error_code: str = Field(
        ...,
        description="Код ошибки (EXT-xxx)",
    )
    error_message: str = Field(
        ...,
        description="Описание ошибки",
    )


class ImportErrorResponse(BaseModel):
    """Ответ с ошибкой импорта."""

    error: str = Field(
        ...,
        description="Тип ошибки",
    )
    error_code: Optional[str] = Field(
        default=None,
        description="Код ошибки (EXT-xxx)",
    )
    error_details: Optional[List[ImportErrorDetail]] = Field(
        default=None,
        description="Детали ошибок",
    )


class ImportResponse(BaseModel):
    """Ответ на успешный импорт."""

    success: bool = Field(
        default=True,
        description="Флаг успеха",
    )
    task_id: str = Field(
        ...,
        description="UUID задачи обработки",
    )
    file_id: str = Field(
        ...,
        description="UUID загруженного файла",
    )
    file_size: Optional[int] = Field(
        default=None,
        description="Размер файла в байтах",
    )
    messages_count: int = Field(
        ...,
        description="Количество сообщений",
    )
    estimated_chunks: int = Field(
        ...,
        description="Ожидаемое количество чанков",
    )
    chat_id_from_file: Optional[int] = Field(
        default=None,
        description="Chat ID из JSON файла",
    )
    chat_name_from_file: Optional[str] = Field(
        default=None,
        description="Название чата из JSON",
    )
    status: str = Field(
        default="processing",
        description="Статус задачи",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Время загрузки и запуска",
    )


class ImportFileRequest(BaseModel):
    """Запрос на импорт файла."""

    chat_id: Optional[int] = Field(
        default=None,
        description="Переопределение chat_id (приоритет над файлом)",
    )


class ImportJsonRequest(BaseModel):
    """Запрос на импорт JSON данных."""

    json_data: dict = Field(
        ...,
        description="JSON данные экспорта",
    )
    chat_id: Optional[int] = Field(
        default=None,
        description="Переопределение chat_id",
    )


class ProgressResponse(BaseModel):
    """Прогресс обработки импорта."""

    task_id: str = Field(
        ...,
        description="UUID задачи",
    )
    status: str = Field(
        ...,
        description="Статус обработки",
        examples=["processing", "completed", "failed", "cancelled"],
    )
    total_messages: int = Field(
        ...,
        description="Общее количество сообщений",
    )
    processed_count: int = Field(
        ...,
        description="Обработано сообщений",
    )
    progress_percent: float = Field(
        ...,
        description="Процент выполнения",
    )
    processed: int = Field(
        ...,
        description="Успешно обработано",
    )
    filtered: int = Field(
        ...,
        description="Отфильтровано",
    )
    duplicates: int = Field(
        ...,
        description="Дубликатов",
    )
    pending: int = Field(
        ...,
        description="Ожидает обработки",
    )
    errors: int = Field(
        ...,
        description="Ошибок",
    )
    current_chunk: int = Field(
        ...,
        description="Текущий чанк",
    )
    total_chunks: int = Field(
        ...,
        description="Всего чанков",
    )
    started_at: Optional[str] = Field(
        default=None,
        description="Время начала обработки",
    )
    estimated_completion: Optional[str] = Field(
        default=None,
        description="Ожидаемое время завершения",
    )
    error_details: List[ImportErrorDetail] = Field(
        default_factory=list,
        description="Детали ошибок",
    )


class CancelResponse(BaseModel):
    """Ответ на отмену импорта."""

    success: bool = Field(
        ...,
        description="Флаг успеха отмены",
    )
    task_id: str = Field(
        ...,
        description="UUID задачи",
    )
    status: str = Field(
        default="cancelled",
        description="Статус задачи",
    )
    processed_before_cancel: int = Field(
        default=0,
        description="Обработано до отмены",
    )
    message: str = Field(
        default="Import cancelled successfully",
        description="Сообщение о результате",
    )
