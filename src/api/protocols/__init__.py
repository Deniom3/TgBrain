"""
Protocol-интерфейсы для API слоя.

Используются для type hints вместо конкретных инфраструктурных классов,
чтобы избежать нарушения границ слоёв (Clean Architecture).
"""

from datetime import datetime
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class RateLimiterProtocol(Protocol):
    """
    Protocol для rate limiter.

    Определяет публичный контракт, используемый API dependency функциями.
    Реальная реализация: src.rate_limiter.limiter.TelegramRateLimiter.
    """

    @property
    def is_running(self) -> bool:
        """Статус работы rate limiter."""
        ...

    async def check_rate_limit(self, key: str, priority: Any) -> None:
        """Проверить лимит частоты запросов."""
        ...

    async def start(self) -> None:
        """Запуск rate limiter."""
        ...

    async def stop(self) -> None:
        """Остановка rate limiter."""
        ...


@runtime_checkable
class ChatSettingsRepoProtocol(Protocol):
    """
    Protocol для репозитория настроек чатов.

    Определяет только методы, используемые в API эндпоинтах.
    Реальная реализация: src.settings.chat_settings.ChatSettingsRepository.
    """

    async def get_summary_settings(self, chat_id: int) -> dict[str, Any] | None:
        """Получить настройки summary для чата."""
        ...

    async def get_enabled_summary_chat_ids(self) -> list[int]:
        """Получить ID чатов с включённой генерацией summary."""
        ...


@runtime_checkable
class SummaryRepoProtocol(Protocol):
    """
    Protocol для репозитория summary.

    Определяет методы, используемые в retrieval эндпоинтах.
    Реальная реализация: src.settings.chat_summary.repository.ChatSummaryRepository.
    """

    async def get_summaries_by_chat_with_pool(
        self, chat_id: int, limit: int, offset: int
    ) -> list:
        """Получить summary для чата с пагинацией."""
        ...

    async def get_latest_summary_with_pool(self, chat_id: int):
        """Получить последнее summary для чата."""
        ...

    async def get_summary_task_with_pool(self, summary_id: int):
        """Получить задачу/summary по ID."""
        ...

    async def get_summary_by_id_with_pool(self, summary_id: int):
        """Получить summary по ID."""
        ...

    async def delete_summary_by_id_with_pool(self, summary_id: int) -> bool:
        """Удалить summary по ID."""
        ...

    async def delete_old_summaries_with_pool(
        self, chat_id: int, cutoff: datetime
    ) -> int:
        """Удалить старые summary."""
        ...

    async def get_stats_with_pool(self) -> list:
        """Получить статистику по summary."""
        ...
