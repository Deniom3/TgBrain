"""
Пакетный импорт сообщений из Telegram Desktop.

Модули:
- models: Value Objects для batch import
- file_service: Сервис для работы с файлами
- task_service: Сервис управления задачами импорта
"""

from src.batch_import.models import BatchImportFileInfo, ImportFileMetadata
from src.batch_import.file_service import BatchImportFileService

__all__ = [
    "BatchImportFileInfo",
    "ImportFileMetadata",
    "BatchImportFileService",
]
