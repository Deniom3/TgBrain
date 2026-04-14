"""
Ingestion — модель сообщения.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class IngestionMessage:
    """Модель сообщения Telegram для ingestion."""
    id: int
    chat_id: int
    chat_title: str
    chat_type: str
    sender_id: Optional[int]
    sender_name: Optional[str]
    text: str
    date: datetime
    message_link: Optional[str]
    is_bot: bool = False
    is_action: bool = False
