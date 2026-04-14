"""
Репозитории для работы с настройками приложения в БД.

Модуль содержит репозитории для управления:
- Telegram авторизацией (telegram_auth)
- Настройками чатов (chat_settings)
- Summary настройками чатов (chat_summary_settings)
- Настройками очистки summary (summary_cleanup_settings)
- Настройками очистки pending (pending_cleanup_settings)
- LLM провайдерами (llm_providers)
- Общими настройками приложения (app_settings)
"""

from .repositories.telegram_auth import TelegramAuthRepository
from .repositories.chat_settings import ChatSettingsRepository
from .repositories.chat_summary_settings import ChatSummarySettingsRepository
from .domain.summary_cleanup_settings import SummaryCleanupSettings
from .repositories.summary_cleanup_settings import SummaryCleanupSettingsRepository
from .domain.pending_cleanup_settings import (
    PendingCleanupSettings,
    PENDING_TTL_MINUTES,
    PENDING_CLEANUP_INTERVAL_MINUTES,
)
from .repositories.pending_cleanup_repository import PendingCleanupSettingsRepository
from .repositories.llm_providers import LLMProvidersRepository
from .repositories.embedding_providers import EmbeddingProvidersRepository
from .repositories.app_settings import AppSettingsRepository
from .repositories.chat_summary.repository import ChatSummaryRepository
from .repositories.chat_settings_base import ChatSettingsBaseRepository
from .repositories.chat_settings_bulk import ChatSettingsBulkRepository
from .repositories.encryption_settings import (
    ENCRYPTION_KEY_KEY,
    EncryptionService,
    EncryptionKeyError,
    EncryptionKeyMismatchError,
    get_encryption_service,
)
from .repositories.exceptions import ChatSettingsStorageError

__all__ = [
    "TelegramAuthRepository",
    "ChatSettingsRepository",
    "ChatSettingsBaseRepository",
    "ChatSettingsBulkRepository",
    "ChatSummarySettingsRepository",
    "ChatSummaryRepository",
    "SummaryCleanupSettings",
    "SummaryCleanupSettingsRepository",
    "PendingCleanupSettings",
    "PendingCleanupSettingsRepository",
    "PENDING_TTL_MINUTES",
    "PENDING_CLEANUP_INTERVAL_MINUTES",
    "LLMProvidersRepository",
    "EmbeddingProvidersRepository",
    "AppSettingsRepository",
    "ENCRYPTION_KEY_KEY",
    "EncryptionService",
    "EncryptionKeyError",
    "EncryptionKeyMismatchError",
    "get_encryption_service",
    "ChatSettingsStorageError",
]
