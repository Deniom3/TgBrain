"""
Валидатор JSON для batch import.

Назначение:
- Валидация структуры JSON файла экспорта Telegram
- Проверка required полей
- Проверка типов данных
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


REQUIRED_FIELDS = ["name", "type", "id", "messages"]
VALID_CHAT_TYPES = {"private", "group", "channel", "supergroup", "private_channel", "personal_chat"}


class JsonValidationError(ValueError):
    """Исключение валидации JSON."""

    def __init__(self, message: str, code: str = "JSON-001") -> None:
        self.message = message
        self.code = code
        super().__init__(self.message)


class JsonValidator:
    """Валидатор JSON структуры."""

    @staticmethod
    def validate_structure(json_data: Optional[Dict[str, Any]]) -> None:
        """
        Валидация структуры JSON данных.
        
        Args:
            json_data: JSON данные для проверки.
            
        Raises:
            JsonValidationError: Если структура невалидна.
        """
        if json_data is None:
            return
        
        if not isinstance(json_data, dict):
            raise JsonValidationError(
                "Root must be an object",
                "JSON-001"
            )
        
        for field in REQUIRED_FIELDS:
            if field not in json_data:
                raise JsonValidationError(
                    f"Missing required field: {field}",
                    "JSON-002"
                )
        
        if not isinstance(json_data["messages"], list):
            raise JsonValidationError(
                "messages must be an array",
                "JSON-003"
            )

    @staticmethod
    def validate_chat_type(chat_type: str) -> None:
        """
        Валидация типа чата.
        
        Args:
            chat_type: Тип чата для проверки.
            
        Raises:
            JsonValidationError: Если тип чата невалиден.
        """
        if chat_type not in VALID_CHAT_TYPES:
            raise JsonValidationError(
                f"Invalid chat type: {chat_type}",
                "JSON-004"
            )

    @staticmethod
    def validate_message_count(messages_count: int, max_messages: int) -> None:
        """
        Валидация количества сообщений.
        
        Args:
            messages_count: Количество сообщений.
            max_messages: Максимально допустимое количество.
            
        Raises:
            JsonValidationError: Если сообщений слишком много.
        """
        if messages_count > max_messages:
            raise JsonValidationError(
                f"Too many messages: {messages_count} (max {max_messages})",
                "JSON-005"
            )

    @staticmethod
    def validate_full(json_data: Optional[Dict[str, Any]], max_messages: int) -> None:
        """
        Полная валидация JSON данных.
        
        Args:
            json_data: JSON данные для проверки.
            max_messages: Максимально допустимое количество сообщений.
            
        Raises:
            JsonValidationError: Если данные невалидны.
        """
        JsonValidator.validate_structure(json_data)
        
        if json_data and "type" in json_data:
            JsonValidator.validate_chat_type(json_data["type"])
        
        if json_data and "messages" in json_data:
            JsonValidator.validate_message_count(
                len(json_data["messages"]),
                max_messages
            )
