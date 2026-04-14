"""
Пакет репозиториев для работы с настройками приложения в БД.

Содержит репозитории для управления:
- Telegram авторизацией (telegram_auth)
- Настройками чатов (chat_settings)
- Summary настройками чатов (chat_summary_settings)
- Результатами суммаризации (chat_summary)
- Настройками очистки summary (summary_cleanup_settings)
- LLM провайдерами (llm_providers)
- Провайдерами эмбеддингов (embedding_providers)
- Общими настройками приложения (app_settings)
- Сервисом шифрования (encryption_settings)
"""

from .chat_settings import ChatSettingsRepository
from .chat_settings_base import ChatSettingsBaseRepository
from .chat_settings_bulk import ChatSettingsBulkRepository
from .chat_summary_settings import ChatSummarySettingsRepository
from .chat_summary.repository import ChatSummaryRepository
from .app_settings import AppSettingsRepository
from .telegram_auth import TelegramAuthRepository
from .llm_providers import LLMProvidersRepository
from .embedding_providers import EmbeddingProvidersRepository
from ..domain.summary_cleanup_settings import SummaryCleanupSettings
from .summary_cleanup_settings import SummaryCleanupSettingsRepository
from .pending_cleanup_repository import PendingCleanupSettingsRepository
from .encryption_settings import (
    EncryptionService,
    EncryptionKeyError,
    EncryptionKeyMismatchError,
    get_encryption_service,
)
from .exceptions import ChatSettingsStorageError

__all__ = [
    "ChatSettingsRepository",
    "ChatSettingsBaseRepository",
    "ChatSettingsBulkRepository",
    "ChatSummarySettingsRepository",
    "ChatSummaryRepository",
    "AppSettingsRepository",
    "TelegramAuthRepository",
    "LLMProvidersRepository",
    "EmbeddingProvidersRepository",
    "SummaryCleanupSettings",
    "SummaryCleanupSettingsRepository",
    "PendingCleanupSettingsRepository",
    "EncryptionService",
    "EncryptionKeyError",
    "EncryptionKeyMismatchError",
    "get_encryption_service",
    "ChatSettingsStorageError",
]
