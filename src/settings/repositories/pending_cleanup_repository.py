"""
Репозиторий для управления настройками очистки pending.

Использует существующую таблицу app_settings (key-value хранение).
Все временные настройки хранятся в минутах.
"""

import logging
from typing import Any, Optional

from ..domain.pending_cleanup_settings import (
    Minutes,
    PendingCleanupSettings,
    PENDING_TTL_MINUTES,
    PENDING_CLEANUP_INTERVAL_MINUTES,
    PENDING_TTL_DESCRIPTION,
    PENDING_INTERVAL_DESCRIPTION,
)
from .app_settings import AppSettingsRepository

logger = logging.getLogger(__name__)

_DEFAULT_TTL = 240
_DEFAULT_INTERVAL = 60


class PendingCleanupSettingsRepository:
    """Репозиторий для управления настройками очистки pending."""

    def __init__(self, app_settings_repo: AppSettingsRepository) -> None:
        self._app_settings_repo = app_settings_repo

    def _parse_minutes_value(self, raw_value: Any, default: int, key_name: str) -> int:
        """Парсинг и валидация значения минут из БД."""
        if raw_value is None or str(raw_value).strip() == "":
            logger.debug("%s missing, using default %d", key_name, default)
            return default
        if str(raw_value).strip() == "0":
            logger.warning("%s=0, using default %d", key_name, default)
            return default
        try:
            val = int(raw_value)
            if val <= 0:
                logger.warning("%s has negative value, using default %d", key_name, default)
                return default
            return val
        except (ValueError, TypeError):
            logger.warning("%s has invalid value, using default %d", key_name, default)
            return default

    async def get(self) -> PendingCleanupSettings:
        """Получить текущие настройки."""
        ttl_mins = await self._app_settings_repo.get_value(PENDING_TTL_MINUTES, None)
        interval_mins = await self._app_settings_repo.get_value(
            PENDING_CLEANUP_INTERVAL_MINUTES, None
        )

        ttl_val = self._parse_minutes_value(ttl_mins, _DEFAULT_TTL, "pending.ttl_minutes")
        interval_val = self._parse_minutes_value(
            interval_mins, _DEFAULT_INTERVAL, "pending.cleanup_interval_minutes"
        )

        return PendingCleanupSettings(
            ttl_minutes=Minutes(ttl_val),
            cleanup_interval_minutes=Minutes(interval_val),
        )

    async def update(
        self,
        ttl_minutes: Optional[int] = None,
        cleanup_interval_minutes: Optional[int] = None,
    ) -> PendingCleanupSettings:
        """Обновить настройки."""
        if ttl_minutes is not None:
            ttl_minutes = self._validate_int_positive(
                ttl_minutes, _DEFAULT_TTL, "ttl_minutes"
            )
            await self._app_settings_repo.upsert(
                PENDING_TTL_MINUTES,
                str(ttl_minutes),
                value_type="integer",
                description=PENDING_TTL_DESCRIPTION,
            )

        if cleanup_interval_minutes is not None:
            cleanup_interval_minutes = self._validate_int_positive(
                cleanup_interval_minutes, _DEFAULT_INTERVAL, "cleanup_interval_minutes"
            )
            await self._app_settings_repo.upsert(
                PENDING_CLEANUP_INTERVAL_MINUTES,
                str(cleanup_interval_minutes),
                value_type="integer",
                description=PENDING_INTERVAL_DESCRIPTION,
            )

        return await self.get()

    def _validate_int_positive(self, value: int, default: int, key_name: str) -> int:
        """Валидация положительного целого значения."""
        if not isinstance(value, int) or isinstance(value, bool):
            logger.warning("Invalid type for %s, using default %d", key_name, default)
            return default
        if value <= 0:
            logger.warning("Invalid %s=%d, using default %d", key_name, value, default)
            return default
        return value

    async def reset(self) -> PendingCleanupSettings:
        """Сбросить настройки к значениям по умолчанию."""
        await self._app_settings_repo.upsert(
            PENDING_TTL_MINUTES, "240", "integer",
            description=PENDING_TTL_DESCRIPTION,
        )
        await self._app_settings_repo.upsert(
            PENDING_CLEANUP_INTERVAL_MINUTES, "60", "integer",
            description=PENDING_INTERVAL_DESCRIPTION,
        )

        return await self.get()
