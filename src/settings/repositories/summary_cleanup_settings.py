"""
Репозиторий для управления настройками очистки summary задач.

Использует существующую таблицу app_settings (key-value хранение).
Все временные настройки хранятся в минутах.
"""

import logging
from typing import Optional

from ..domain.summary_cleanup_settings import SummaryCleanupSettings
from .app_settings import AppSettingsRepository

logger = logging.getLogger(__name__)

# Ключи настроек (все в минутах)
CLEANUP_PENDING_TIMEOUT_MINUTES = "summary.cleanup.pending_timeout_minutes"
CLEANUP_PROCESSING_TIMEOUT_MINUTES = "summary.cleanup.processing_timeout_minutes"
CLEANUP_FAILED_RETENTION_MINUTES = "summary.cleanup.failed_retention_minutes"
CLEANUP_COMPLETED_RETENTION_MINUTES = "summary.cleanup.completed_retention_minutes"
CLEANUP_AUTO_ENABLED = "summary.cleanup.auto_enabled"


class SummaryCleanupSettingsRepository:
    """Репозиторий для управления настройками очистки."""

    def __init__(self, app_settings_repo: AppSettingsRepository) -> None:
        """
        Инициализировать репозиторий.

        Args:
            app_settings_repo: Репозиторий для работы с app_settings.
        """
        self._app_settings_repo = app_settings_repo

    async def get(self) -> SummaryCleanupSettings:
        """
        Получить текущие настройки.

        Если ключа нет или значение = 0/пустое — считаем отключенным (0).
        """
        pending_mins = await self._app_settings_repo.get_value(
            CLEANUP_PENDING_TIMEOUT_MINUTES, None
        )
        processing_mins = await self._app_settings_repo.get_value(
            CLEANUP_PROCESSING_TIMEOUT_MINUTES, None
        )
        failed_mins = await self._app_settings_repo.get_value(
            CLEANUP_FAILED_RETENTION_MINUTES, None
        )
        completed_mins = await self._app_settings_repo.get_value(
            CLEANUP_COMPLETED_RETENTION_MINUTES, None
        )
        auto_enabled = await self._app_settings_repo.get_value(
            CLEANUP_AUTO_ENABLED, "true"
        )

        return SummaryCleanupSettings(
            pending_timeout_minutes=int(pending_mins) if pending_mins and str(pending_mins).strip() else 0,
            processing_timeout_minutes=int(processing_mins) if processing_mins and str(processing_mins).strip() else 0,
            failed_retention_minutes=int(failed_mins) if failed_mins and str(failed_mins).strip() else 0,
            completed_retention_minutes=int(completed_mins) if completed_mins and str(completed_mins).strip() else None,
            auto_cleanup_enabled=str(auto_enabled).lower() == "true",
        )

    async def update(
        self,
        pending_timeout_minutes: Optional[int] = None,
        processing_timeout_minutes: Optional[int] = None,
        failed_retention_minutes: Optional[int] = None,
        completed_retention_minutes: Optional[int] = None,
        auto_cleanup_enabled: Optional[bool] = None,
    ) -> SummaryCleanupSettings:
        """Обновить настройки. Все значения в минутах."""
        if pending_timeout_minutes is not None:
            await self._app_settings_repo.upsert(
                CLEANUP_PENDING_TIMEOUT_MINUTES,
                str(pending_timeout_minutes),
                value_type="integer",
                description="Через сколько минут удалять застрявшие pending задачи",
            )

        if processing_timeout_minutes is not None:
            await self._app_settings_repo.upsert(
                CLEANUP_PROCESSING_TIMEOUT_MINUTES,
                str(processing_timeout_minutes),
                value_type="integer",
                description="Через сколько минут переводить processing в failed",
            )

        if failed_retention_minutes is not None:
            await self._app_settings_repo.upsert(
                CLEANUP_FAILED_RETENTION_MINUTES,
                str(failed_retention_minutes),
                value_type="integer",
                description="Через сколько минут удалять failed задачи",
            )

        if completed_retention_minutes is not None:
            await self._app_settings_repo.upsert(
                CLEANUP_COMPLETED_RETENTION_MINUTES,
                str(completed_retention_minutes) if completed_retention_minutes else None,
                value_type="integer",
                description="Через сколько минут удалять completed (None = не удалять)",
            )

        if auto_cleanup_enabled is not None:
            await self._app_settings_repo.upsert(
                CLEANUP_AUTO_ENABLED,
                str(auto_cleanup_enabled),
                value_type="boolean",
                description="Включить/отключить автоматическую очистку",
            )

        return await self.get()

    async def reset(self) -> SummaryCleanupSettings:
        """Сбросить настройки к значениям по умолчанию (в минутах)."""
        await self._app_settings_repo.upsert(
            CLEANUP_PENDING_TIMEOUT_MINUTES, "60", "integer",
        )
        await self._app_settings_repo.upsert(
            CLEANUP_PROCESSING_TIMEOUT_MINUTES, "5", "integer",
        )
        await self._app_settings_repo.upsert(
            CLEANUP_FAILED_RETENTION_MINUTES, "120", "integer",
        )
        await self._app_settings_repo.upsert(
            CLEANUP_COMPLETED_RETENTION_MINUTES, None, "integer",
        )
        await self._app_settings_repo.upsert(
            CLEANUP_AUTO_ENABLED, "true", "boolean",
        )

        return await self.get()
