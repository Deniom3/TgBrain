"""
Stubs для asyncpg.

Назначение:
- Устранение type checker ошибок import-untyped
- Предоставление минимальных типов для основных классов asyncpg
"""

from typing import Any


class PostgresError(Exception):
    """Базовое исключение PostgreSQL."""

    pass


class InterfaceError(PostgresError):
    """Ошибка интерфейса базы данных."""

    pass


class Pool:
    """Пул соединений asyncpg."""

    async def acquire(self) -> Any:
        """Получить соединение из пула."""
        ...

    async def close(self) -> None:
        """Закрыть пул."""
        ...


class Connection:
    """Соединение с базой данных."""

    pass
