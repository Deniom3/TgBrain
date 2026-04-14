"""
Модуль доменных объектов.

Предоставляет Value Objects для использования в моделях данных.
"""

from .value_objects import (
    ApiId,
    ApiHash,
    PhoneNumber,
    SessionName,
    SessionData,
    MessageText,
    SenderName,
    ChatTitle,
)

__all__ = [
    "ApiId",
    "ApiHash",
    "PhoneNumber",
    "SessionName",
    "SessionData",
    "MessageText",
    "SenderName",
    "ChatTitle",
]
