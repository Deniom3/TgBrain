"""
Доменный слой настроек.

Содержит Value Objects, доменные модели и константы конфигурации.
"""

from .pending_cleanup_settings import (
    Minutes,
    PendingCleanupSettings,
    PENDING_TTL_MINUTES,
    PENDING_CLEANUP_INTERVAL_MINUTES,
    PENDING_TTL_DESCRIPTION,
    PENDING_INTERVAL_DESCRIPTION,
)
from .summary_cleanup_settings import SummaryCleanupSettings

__all__ = [
    "Minutes",
    "PendingCleanupSettings",
    "SummaryCleanupSettings",
    "PENDING_TTL_MINUTES",
    "PENDING_CLEANUP_INTERVAL_MINUTES",
    "PENDING_TTL_DESCRIPTION",
    "PENDING_INTERVAL_DESCRIPTION",
]
