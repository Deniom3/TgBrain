"""
Repository fixtures для тестирования TgBrain.

Содержит фикстуры для создания репозиториев:
- TelegramAuthRepository
- AppSettingsRepository
- LLMProvidersRepository
- EmbeddingProvidersRepository
- SummaryCleanupSettingsRepository
- PendingCleanupSettingsRepository
- RequestStatisticsRepository
- FloodWaitIncidentRepository
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from src.rate_limiter.repositories import FloodWaitIncidentRepository, RequestStatisticsRepository
    from src.settings.repositories.app_settings import AppSettingsRepository
    from src.settings.repositories.embedding_providers import EmbeddingProvidersRepository
    from src.settings.repositories.llm_providers import LLMProvidersRepository
    from src.settings.repositories.pending_cleanup_repository import PendingCleanupSettingsRepository
    from src.settings.repositories.summary_cleanup_settings import SummaryCleanupSettingsRepository
    from src.settings.repositories.telegram_auth import TelegramAuthRepository

__all__ = [
    "telegram_auth_repo",
    "app_settings_repo",
    "llm_providers_repo",
    "embedding_providers_repo",
    "summary_cleanup_repo",
    "pending_cleanup_repo",
    "request_stats_repo",
    "flood_wait_repo",
]


@pytest.fixture
def telegram_auth_repo(db_pool: MagicMock) -> "TelegramAuthRepository":
    """Фикстура TelegramAuthRepository для тестов."""
    from src.settings.repositories.telegram_auth import TelegramAuthRepository

    return TelegramAuthRepository(db_pool)


@pytest.fixture
def app_settings_repo(db_pool: MagicMock) -> "AppSettingsRepository":
    """Фикстура AppSettingsRepository для тестов."""
    from src.settings.repositories.app_settings import AppSettingsRepository

    return AppSettingsRepository(db_pool)


@pytest.fixture
def llm_providers_repo(db_pool: MagicMock) -> "LLMProvidersRepository":
    """Фикстура LLMProvidersRepository для тестов."""
    from src.settings.repositories.llm_providers import LLMProvidersRepository

    return LLMProvidersRepository(db_pool)


@pytest.fixture
def embedding_providers_repo(db_pool: MagicMock) -> "EmbeddingProvidersRepository":
    """Фикстура EmbeddingProvidersRepository для тестов."""
    from src.settings.repositories.embedding_providers import EmbeddingProvidersRepository

    return EmbeddingProvidersRepository(db_pool)


@pytest.fixture
def summary_cleanup_repo(
    app_settings_repo: "AppSettingsRepository",
) -> "SummaryCleanupSettingsRepository":
    """Фикстура SummaryCleanupSettingsRepository для тестов."""
    from src.settings.repositories.summary_cleanup_settings import SummaryCleanupSettingsRepository

    return SummaryCleanupSettingsRepository(app_settings_repo)


@pytest.fixture
def pending_cleanup_repo(
    app_settings_repo: "AppSettingsRepository",
) -> "PendingCleanupSettingsRepository":
    """Фикстура PendingCleanupSettingsRepository для тестов."""
    from src.settings.repositories.pending_cleanup_repository import PendingCleanupSettingsRepository

    return PendingCleanupSettingsRepository(app_settings_repo)


@pytest.fixture
def request_stats_repo(db_pool: MagicMock) -> "RequestStatisticsRepository":
    """Фикстура RequestStatisticsRepository для тестов."""
    from src.rate_limiter.repositories import RequestStatisticsRepository

    return RequestStatisticsRepository(db_pool)


@pytest.fixture
def flood_wait_repo(db_pool: MagicMock) -> "FloodWaitIncidentRepository":
    """Фикстура FloodWaitIncidentRepository для тестов."""
    from src.rate_limiter.repositories import FloodWaitIncidentRepository

    return FloodWaitIncidentRepository(db_pool)
