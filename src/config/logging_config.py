"""
Конфигурация логирования приложения.
"""

from __future__ import annotations

import logging

_QUIET_LOGGERS = ("httpcore", "httpx", "telethon", "asyncpg")


def setup_logging(level: str = "INFO") -> None:
    """
    Настроить базовое логирование приложения.

    Args:
        level: Уровень логирования корневого логгера.
    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    for name in _QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
