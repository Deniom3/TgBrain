"""
Настройки автоматической очистки summary задач (доменная модель).

Все временные интервалы хранятся в минутах.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class SummaryCleanupSettings:
    """
    Настройки очистки summary задач.

    Все временные интервалы хранятся в минутах:
    - pending_timeout_minutes: 60 (1 час)
    - processing_timeout_minutes: 5
    - failed_retention_minutes: 120 (2 часа)
    - completed_retention_minutes: None (бессрочно)
    """

    pending_timeout_minutes: int = 60
    processing_timeout_minutes: int = 5
    failed_retention_minutes: int = 120
    completed_retention_minutes: Optional[int] = None
    auto_cleanup_enabled: bool = True
