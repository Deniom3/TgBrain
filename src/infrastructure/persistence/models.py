"""
Infrastructure модели для персистентности.

Модуль предоставляет модели данных для работы с базой данных.
Эти модели используют примитивные типы данных (int, str, bytes)
для совместимости с ORM и SQL запросами.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class TelegramAuthDB:
    """Модель авторизации Telegram (Infrastructure).
    
    Инфраструктурная модель для хранения учетных данных авторизации
    в базе данных. Использует примитивные типы данных для совместимости
    с ORM и SQL запросами.
    
    Атрибуты:
        id: Идентификатор записи (всегда 1 для единственной записи).
        api_id: API ID Telegram (примитивный int).
        api_hash: API Hash Telegram (примитивный str).
        phone_number: Номер телефона (примитивный str).
        session_name: Имя сессии (примитивный str, может быть None).
        session_data: Данные сессии (bytes).
        updated_at: Время последнего обновления.
    
    Примечание:
        Эта модель используется только для взаимодействия с базой данных.
        Для бизнес-логики используйте domain.models.auth.TelegramAuth.
    """

    id: int = 1
    api_id: Optional[int] = None
    api_hash: Optional[str] = None
    phone_number: Optional[str] = None
    session_name: Optional[str] = None
    session_data: Optional[bytes] = None
    updated_at: Optional[datetime] = None
