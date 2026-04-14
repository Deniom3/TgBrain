"""
Модуль доменных моделей.

Предоставляет domain-модели для использования в бизнес-логике.
"""

from .auth import TelegramAuth
from .message import IngestionMessage, MessageId

__all__ = ["TelegramAuth", "IngestionMessage", "MessageId"]
