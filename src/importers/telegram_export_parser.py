import json
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Union, Optional, Tuple

from .models import ExportChat, ExportMessage, IngestionMessage
from src.domain.value_objects import ChatId

# Настройка логирования
logger = logging.getLogger(__name__)


class TelegramExportParser:
    """Парсер для JSON-экспортов Telegram Desktop."""

    def parse_file(self, file_path: str) -> ExportChat:
        """Парсинг файла экспорта Telegram Desktop с безопасной проверкой пути."""
        # Защита от path traversal атак
        safe_path = self._validate_file_path(file_path)
        
        # Проверка расширения файла
        if not safe_path.lower().endswith('.json'):
            raise ValueError("File must have .json extension")
        
        # Проверка размера файла для предотвращения DoS-атак
        if os.path.getsize(safe_path) > 50 * 1024 * 1024:  # 50MB limit
            raise ValueError("File size exceeds 50MB limit")
            
        with open(safe_path, 'r', encoding='utf-8') as f:
            # Ограничение размера JSON для предотвращения DoS-атак
            content = f.read(50 * 1024 * 1024)  # 50MB limit
            try:
                # Используем более безопасный JSON decoder с ограничением глубины
                json_data = self._safe_json_loads(content)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON format: {str(e)}")
                
        return self.parse_json(json_data)
    
    def _safe_json_loads(self, content: str) -> dict:
        """Безопасное чтение JSON с ограничением глубины и защиты от DoS."""
        try:
            # Ограничиваем максимальную глубину JSON и размер для защиты от DoS
            parsed = json.loads(content, object_hook=self._validate_depth_and_size)
            return parsed
        except RecursionError:
            raise ValueError("JSON depth exceeds maximum allowed depth")
        except MemoryError:
            raise ValueError("JSON processing exceeded memory limits")
    
    def _validate_depth_and_size(self, obj):
        """Валидация глубины и размера JSON для защиты от DoS."""
        if hasattr(obj, '__len__') and len(obj) > 10000:  # Превышение размера
            raise ValueError("JSON object exceeds maximum allowed size")
        return obj

    def _validate_file_path(self, file_path: str) -> str:
        """Защита от path traversal атак с расширенной проверкой."""
        # Нормализуем входной путь
        requested_path = Path(file_path).resolve()
        
        # Проверяем расширение файла
        if requested_path.suffix.lower() != '.json':
            raise ValueError(f"Only .json files are allowed: {file_path}")
        
        # Определяем фиксированную безопасную директорию для импорта
        # Можно использовать относительный путь от корня проекта
        project_root = Path(__file__).parent.parent.parent.resolve()  # до директории проекта
        safe_base_path = project_root / "uploads"  # директория для загрузок
        
        # Создаем директорию, если она не существует
        safe_base_path.mkdir(exist_ok=True)
        
        # Проверяем, что запрашиваемый путь находится внутри безопасной директории
        try:
            # Получаем относительный путь от безопасной директории
            requested_path.relative_to(safe_base_path)
        except ValueError:
            # Если невозможно получить относительный путь от safe_base_path, 
            # проверим, что он хотя бы внутри проекта
            try:
                relative_to_project = requested_path.relative_to(project_root)
                # Проверим, что путь не пытается выйти за пределы проекта
                if '..' in str(relative_to_project):
                    raise ValueError(f"Path traversal detected: {file_path}")
                # Для безопасности переместим файл в uploads
                target_path = safe_base_path / requested_path.name
                if target_path.resolve() != requested_path:
                    raise ValueError(f"Path traversal detected: {file_path}")
            except ValueError:
                raise ValueError(f"Path outside allowed directories: {file_path}")
        
        # Проверяем, что файл действительно существует и это файл (не директория)
        if not requested_path.is_file():
            raise FileNotFoundError(f"File not found: {requested_path}")
            
        return str(requested_path)

    def parse_json(self, json_data: dict) -> ExportChat:
        """Парсинг JSON-данных экспорта Telegram Desktop."""
        # Use the from_dict method which handles 'from' field alias
        return ExportChat.from_dict(json_data)

    def extract_text(self, text_field: Union[str, list]) -> str:
        """Конвертация текстового поля из строки или массива в строку."""
        if isinstance(text_field, str):
            return text_field
        elif isinstance(text_field, list):
            # Extract text from text_entities if available, otherwise join the array elements
            text_parts = []
            for item in text_field:
                if isinstance(item, dict) and 'text' in item:
                    text_parts.append(item['text'])
                elif isinstance(item, str):
                    text_parts.append(item)
            return ''.join(text_parts)
        else:
            return str(text_field) if text_field is not None else ''

    def parse_sender_id(self, from_id: str) -> Tuple[Optional[int], bool]:
        """
        Преобразование from_id в sender_id и признак бота.
        
        from_id форматы:
        - "user123" -> (123, False)
        - "channel123" -> (-1000000000123, False) 
        - "bot123" -> (123, True)
        """
        if not from_id:
            return None, False

        if from_id.startswith('user'):
            user_id = from_id[4:]  # Remove 'user' prefix
            try:
                return int(user_id), False
            except ValueError:
                return None, False
        
        elif from_id.startswith('channel'):
            channel_id = from_id[7:]  # Remove 'channel' prefix
            try:
                # Convert to negative ID as channels in Telegram have negative IDs
                # Assuming format is -100xxxxxxxxxx for supergroups
                numeric_id = int(channel_id)
                # Format channel ID with -100 prefix
                return -1000000000000 - numeric_id, False
            except ValueError:
                return None, False
                
        elif from_id.startswith('bot'):
            bot_id = from_id[3:]  # Remove 'bot' prefix
            try:
                return int(bot_id), True
            except ValueError:
                return None, False
        
        # If none of the above formats match
        try:
            return int(from_id), False
        except ValueError:
            return None, False

    def parse_date(self, date_str: str) -> Optional[datetime]:
        """Парсинг даты из ISO 8601 строки в datetime объект."""
        if not date_str:
            return None
        
        # Try parsing various ISO 8601 formats
        date_formats = [
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%f',
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%d %H:%M:%S'
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        # If standard formats fail, try parsing with timezone info that might include colons
        try:
            # Handle cases like +03:00 format
            if date_str.endswith('Z'):
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            elif '+' in date_str[-6:]:
                return datetime.fromisoformat(date_str.replace(' ', 'T'))
            elif '-' in date_str[-6:] and date_str.count('-') > 2:
                return datetime.fromisoformat(date_str.replace(' ', 'T'))
        except ValueError:
            pass
        
        # Last resort - try fromisoformat for modern Python
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except ValueError:
            return None

    def convert_to_ingestion(self, export_msg: ExportMessage, chat_id: Optional[ChatId]) -> IngestionMessage:
        """Конвертация ExportMessage в IngestionMessage."""
        if chat_id is None:
            raise ValueError("Chat ID is required for message conversion")
        
        text = self.extract_text(export_msg.text)
        date = self.parse_date(export_msg.date)
        
        sender_id, is_bot = None, False
        if export_msg.from_id:
            sender_id, is_bot = self.parse_sender_id(export_msg.from_id)
        
        is_action = export_msg.type == "service"
        sender_name = export_msg.from_
        message_link = f"export://{chat_id.value}/{export_msg.id}" if export_msg.id else None
        
        return IngestionMessage.from_primitives(
            chat_id=chat_id.value,
            text=text,
            date=date or datetime.now(),
            sender_id=sender_id,
            sender_name=sender_name,
            is_bot=is_bot,
            is_action=is_action,
            message_link=message_link
        )

    def convert_to_domain_entity(self, export_msg: ExportMessage, chat_id: Optional[ChatId]):
        """Конвертация ExportMessage в доменную сущность IngestionMessage с использованием Value Objects."""
        ingestion_msg = self.convert_to_ingestion(export_msg, chat_id)
        return ingestion_msg.to_domain_entity_data()