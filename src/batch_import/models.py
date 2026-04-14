"""
Value Objects и модели данных для пакетного импорта.

Следует стандартам Domain Model:
- Все поля — Value Objects
- Нет raw int/string/bool
- Immutable dataclasses
"""

from dataclasses import dataclass
from typing import Optional

from src.domain.value_objects import ChatId, ChatTitle, ChatType


@dataclass(frozen=True)
class ImportFileMetadata:
    """
    Value Object для метаданных импорт файла.
    
    Attributes:
        file_id: UUID файла в системе
        file_size: Размер файла в байтах (wrapped in Value Object)
        messages_count: Количество сообщений (wrapped in Value Object)
        chat_id: ID чата из файла
        chat_name: Название чата
        chat_type: Тип чата
    """
    
    file_id: str
    file_size: int
    messages_count: int
    chat_id: Optional[ChatId]
    chat_name: Optional[ChatTitle]
    chat_type: Optional[ChatType]
    
    def __post_init__(self) -> None:
        """Валидация после инициализации."""
        if self.file_size < 0:
            raise ValueError("file_size cannot be negative")
        if self.messages_count < 0:
            raise ValueError("messages_count cannot be negative")


@dataclass(frozen=True)
class BatchImportFileInfo:
    """
    Value Object для информации о файле импорта.
    
    Attributes:
        chat_id: ID чата (Value Object)
        chat_name: Название чата (Value Object)
        chat_type: Тип чата (Value Object)
        messages: Список сообщений для импорта
        file_path: Путь к временному файлу
        file_id: UUID файла
    """
    
    chat_id: ChatId
    chat_name: ChatTitle
    chat_type: ChatType
    file_path: str
    file_id: str
    file_size: int
    messages_count: int
    
    def __post_init__(self) -> None:
        """Валидация после инициализации."""
        if self.file_size < 0:
            raise ValueError("file_size cannot be negative")
        if self.messages_count < 0:
            raise ValueError("messages_count cannot be negative")


@dataclass(frozen=True)
class ImportTaskInfo:
    """
    Value Object для информации о задаче импорта.
    
    Attributes:
        task_id: UUID задачи
        file_info: Информация о файле
        status: Статус задачи
        estimated_chunks: Ожидаемое количество чанков
    """
    
    task_id: str
    file_info: BatchImportFileInfo
    status: str
    estimated_chunks: int
