"""
Domain модель авторизации Telegram.

Модуль предоставляет доменную модель для авторизации в Telegram
с использованием Value Objects для обеспечения целостности данных.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..exceptions import ValidationError
from ..value_objects import ApiId, ApiHash, PhoneNumber, SessionName


@dataclass
class TelegramAuth:
    """Модель авторизации Telegram (Domain).

    Доменная модель для хранения учетных данных авторизации
    в Telegram. Использует Value Objects для всех полей
    для обеспечения валидации и целостности данных.

    Атрибуты:
        id: Идентификатор записи (всегда 1 для единственной записи).
        api_id: API ID Telegram (Value Object).
        api_hash: API Hash Telegram (Value Object).
        phone_number: Номер телефона (Value Object).
        session_name: Имя сессии (Value Object).
        updated_at: Время последнего обновления.

    Примечание:
        Модель намеренно НЕ содержит поле session_data.
        Данные сессии (bytes) хранятся только в infrastructure слое
        (TelegramAuthDB) и передаются отдельно через мапперы.
        Это соответствует принципу Clean Architecture - domain слой
        не должен зависеть от деталей реализации персистентности.

    Примеры использования:
        >>> auth = TelegramAuth(
        ...     id=1,
        ...     api_id=ApiId(12345678),
        ...     api_hash=ApiHash("abcdef1234567890abcdef1234567890"),
        ...     phone_number=PhoneNumber("+79991234567"),
        ...     session_name=SessionName("qr_auth_session"),
        ... )
        >>> auth.api_id.value
        12345678
    """

    id: int = 1
    api_id: Optional[ApiId] = None
    api_hash: Optional[ApiHash] = None
    phone_number: Optional[PhoneNumber] = None
    session_name: Optional[SessionName] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Валидация бизнес-правил после инициализации.
        
        Raises:
            ValidationError: Если api_id <= 0 или api_hash не 32 символа.
        """
        if self.api_id is not None and self.api_id.value <= 0:
            raise ValidationError("api_id должен быть положительным числом", field="api_id")
        if self.api_hash is not None and len(self.api_hash.value) != 32:
            raise ValidationError("api_hash должен быть 32 символа", field="api_hash")

    def is_fully_configured(self) -> bool:
        """Проверить, что все необходимые поля заполнены.
        
        Returns:
            True если api_id и api_hash заполнены.
        """
        return self.api_id is not None and self.api_hash is not None

    def has_session(self) -> bool:
        """Проверить наличие сессии.
        
        Returns:
            True если session_name заполнено.
        """
        return self.session_name is not None
