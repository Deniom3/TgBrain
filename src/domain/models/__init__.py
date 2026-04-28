"""
Модуль доменных моделей.

Предоставляет domain-модели для использования в бизнес-логике.
"""

from .auth import TelegramAuth
from .chat_filter_config import ChatFilterConfig
from .message import IngestionMessage, MessageId

__all__ = ["TelegramAuth", "ChatFilterConfig", "IngestionMessage", "MessageId"]
