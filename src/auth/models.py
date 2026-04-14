"""
Модели данных для QR авторизации.

Классы:
- QRAuthSession: Сессия QR авторизации
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class QRAuthSession:
    """Сессия QR авторизации."""
    session_id: str  # Уникальный ID сессии
    session_name: str  # Имя файла сессии
    qr_code_data: str  # Данные QR кода (base64)
    created_at: datetime
    expires_at: datetime
    is_completed: bool = False
    user_id: Optional[int] = None
    user_username: Optional[str] = None
    error: Optional[str] = None
    saved_to_db: bool = False  # Флаг сохранения в БД
    reconnect_attempted: bool = False  # Флаг попытки переподключения
