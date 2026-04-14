"""
Сервис для работы с файлами импорта.

Инкапсулирует бизнес-логику:
- Сохранение файлов во временное хранилище
- Извлечение информации о чате из файла
- Валидация содержимого файла
"""

import json
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from src.batch_import.json_validator import JsonValidator
from src.batch_import.models import BatchImportFileInfo
from src.domain.value_objects import ChatId, ChatTitle, ChatType
from src.importers.telegram_export_parser import TelegramExportParser

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024  # 500MB
MAX_FILE_MESSAGES = 200000  # Лимит сообщений для файлов


class BatchImportFileService:
    """Сервис для управления файлами импорта."""
    
    def __init__(self) -> None:
        """Инициализация сервиса."""
        pass
    
    async def save_file_to_temp(
        self,
        file_content: bytes,
        file_id: str,
        file_size: int,
    ) -> str:
        """
        Сохранение файла во временное хранилище.
        
        Args:
            file_content: Содержимое файла.
            file_id: UUID файла.
            file_size: Размер файла в байтах.
            
        Returns:
            Путь к сохранённому файлу.
            
        Raises:
            ValueError: Если файл слишком большой.
        """
        if file_size > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"File too large: {file_size} bytes (max {MAX_FILE_SIZE_BYTES})")
        
        temp_dir = Path(tempfile.gettempdir()) / "batch_imports"
        temp_dir.mkdir(mode=0o700, exist_ok=True)
        
        file_path = temp_dir / f"{file_id}.json"
        file_path.write_bytes(file_content)
        
        logger.info("File saved: file_id=%s, path=%s, size=%d", file_id, str(file_path), file_size)
        return str(file_path)
    
    def extract_chat_info_from_file(
        self,
        file_path: str,
    ) -> Tuple[Optional[int], Optional[str], Optional[str]]:
        """
        Извлечение chat_id, name, type из JSON файла.
        
        Args:
            file_path: Путь к JSON файлу.
            
        Returns:
            Кортеж (chat_id, chat_name, chat_type) или (None, None, None) при ошибке.
        """
        try:
            parser = TelegramExportParser()
            export_chat = parser.parse_file(file_path)
            return export_chat.id, export_chat.name, export_chat.type
        except Exception as e:
            logger.warning("Failed to extract chat info from file: %s", e)
            return None, None, None
    
    def validate_file_content(self, file_path: str) -> bool:
        """
        Валидация содержимого файла (magic bytes / JSON structure).
        
        Args:
            file_path: Путь к файлу.
            
        Returns:
            True если файл валиден.
            
        Raises:
            ValueError: Если файл невалиден.
        """
        try:
            content = Path(file_path).read_bytes()
            
            if not content.strip():
                raise ValueError("Empty file")
            
            try:
                data = json.loads(content.decode('utf-8'))
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON: {e}")
            
            JsonValidator.validate_structure(data)
            JsonValidator.validate_message_count(len(data.get("messages", [])), MAX_FILE_MESSAGES)
            
            return True
            
        except Exception as e:
            logger.error("File validation failed: %s", type(e).__name__)
            raise
    
    def count_messages_in_file(self, file_path: str) -> int:
        """
        Подсчёт количества сообщений в файле.

        Args:
            file_path: Путь к файлу.

        Returns:
            Количество сообщений.
        """
        try:
            content = Path(file_path).read_text(encoding='utf-8')
            data = json.loads(content)
            return len(data.get("messages", []))
        except Exception as e:
            logger.warning("Could not count messages: %s", e)
            return 0

    def validate_file_content_full(self, file_path: str) -> Dict[str, Any]:
        """
        Полная валидация файла: проверка содержимого, подсчёт сообщений, извлечение метаданных чата.

        Args:
            file_path: Путь к файлу.

        Returns:
            Dict с keys: messages_count, chat_info.

        Raises:
            ValueError: Если файл невалиден.
        """
        self.validate_file_content(file_path)
        messages_count = self.count_messages_in_file(file_path)
        chat_id, chat_name, chat_type = self.extract_chat_info_from_file(file_path)

        chat_info: Optional[Dict[str, Any]] = None
        if chat_id is not None:
            chat_info = {
                "chat_id": chat_id,
                "chat_name": chat_name,
                "chat_type": chat_type,
            }

        return {
            "messages_count": messages_count,
            "chat_info": chat_info,
        }

    def validate_json_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Полная валидация JSON-данных импорта.
        
        Args:
            data: JSON-данные для валидации.
            
        Returns:
            Dict с keys: messages_count, chat_info.
            
        Raises:
            JsonValidationError: Если данные невалидны.
        """
        JsonValidator.validate_structure(data)
        messages_count = len(data.get("messages", []))
        JsonValidator.validate_message_count(messages_count, MAX_FILE_MESSAGES)
        
        chat_info: Optional[Dict[str, Any]] = None
        if "chat" in data:
            chat_data = data["chat"]
            chat_info = {
                "chat_id": chat_data.get("id"),
                "chat_name": chat_data.get("name"),
                "chat_type": chat_data.get("type"),
            }
        
        return {
            "messages_count": messages_count,
            "chat_info": chat_info,
        }
    
    def create_file_info(
        self,
        file_path: str,
        file_id: str,
        chat_id_override: Optional[int] = None,
    ) -> BatchImportFileInfo:
        """
        Создание BatchImportFileInfo из файла.
        
        Args:
            file_path: Путь к файлу.
            file_id: UUID файла.
            chat_id_override: Переопределение chat_id.
            
        Returns:
            BatchImportFileInfo с информацией о файле.
        """
        chat_id_from_file, chat_name_from_file, chat_type_from_file = self.extract_chat_info_from_file(file_path)
        
        final_chat_id = chat_id_override if chat_id_override is not None else chat_id_from_file
        if final_chat_id is None:
            raise ValueError("chat_id is required (from upload or override)")
        
        chat_name = chat_name_from_file or f"Imported Chat {final_chat_id}"
        chat_type_value = chat_type_from_file if chat_type_from_file else "private"
        
        chat_id = ChatId(final_chat_id)
        chat_title = ChatTitle(chat_name)
        chat_type = ChatType(chat_type_value)
        
        file_size = Path(file_path).stat().st_size
        messages_count = self.count_messages_in_file(file_path)
        
        return BatchImportFileInfo(
            chat_id=chat_id,
            chat_name=chat_title,
            chat_type=chat_type,
            file_path=file_path,
            file_id=file_id,
            file_size=file_size,
            messages_count=messages_count,
        )
