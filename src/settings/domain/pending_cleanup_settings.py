"""
Настройки очистки pending сообщений (доменные сущности).

Содержит Value Objects и константы конфигурации,
общие для Telegram + External источников.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Minutes:
    """Value Object для временных интервалов в минутах."""

    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValueError(f"Minutes must be > 0, got {self.value}")

    def __int__(self) -> int:
        return self.value


# Ключи настроек
PENDING_TTL_MINUTES = "pending.ttl_minutes"
PENDING_CLEANUP_INTERVAL_MINUTES = "pending.cleanup_interval_minutes"

# Описания для инициализации настроек (DRY)
PENDING_TTL_DESCRIPTION = "TTL для необработанных сообщений (минуты) — Telegram + External"
PENDING_INTERVAL_DESCRIPTION = "Периодичность очистки pending (минуты)"


@dataclass(frozen=True, slots=True)
class PendingCleanupSettings:
    """Настройки очистки pending сообщений (единые для всех источников)."""

    ttl_minutes: Minutes
    cleanup_interval_minutes: Minutes
