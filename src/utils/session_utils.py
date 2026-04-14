"""
Utility функции для работы с сессиями.

Предоставляет вспомогательные функции для конвертации и обработки
Value Objects сессии.
"""

from typing import Optional

from ..domain.value_objects import SessionName


def session_name_to_str(session_name: Optional[SessionName]) -> Optional[str]:
    """
    Конвертировать SessionName VO в строку.

    Args:
        session_name: SessionName VO или None

    Returns:
        Строковое представление или None
    """
    if session_name is None:
        return None

    if isinstance(session_name, SessionName):
        return session_name.value

    # Fallback для legacy кода
    if hasattr(session_name, 'value'):
        return str(session_name.value)

    return str(session_name)


__all__ = [
    "session_name_to_str",
]
