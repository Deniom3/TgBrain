"""
Time abstraction для доменной области.

Предоставляет централизованное управление временем для тестирования
и обеспечения консистентности временных меток.
"""

from datetime import datetime, timezone


def now() -> datetime:
    """Получить текущее время в UTC."""
    return datetime.now(timezone.utc)


def now_utc() -> datetime:
    """Получить текущее время в UTC (alias для now())."""
    return now()


def from_iso(iso_string: str) -> datetime:
    """Создать datetime из ISO 8601 строки."""
    return datetime.fromisoformat(iso_string.replace('Z', '+00:00'))


def to_iso(dt: datetime) -> str:
    """Конвертировать datetime в ISO 8601 строку."""
    return dt.isoformat()
