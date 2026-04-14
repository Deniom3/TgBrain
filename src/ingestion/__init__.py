"""
Ingestion — сбор и обработка сообщений из Telegram.

SECURITY: Все session_data шифруются перед записью.
Временные файлы создаются с правами 600 и очищаются при crash.
"""

from .chat_sync_service import ChatSyncService
from .external_saver import ExternalMessageSaver, SaveResult, SaveStatus
from .filters import should_process_message
from .ingester import TelegramIngester
from .message_processing import MessageProcessor
from .models import IngestionMessage
from .pending_cleanup_service import PendingCleanupService
from .polling import PollingService
from .saver import IMessageSaver, MessageSaver
from .session_lifecycle import SessionLifecycleManager
from .session_manager import SessionManager
from .services import IngestionServices
from .telegram_connection import TelegramConnection

__all__ = [
    "TelegramIngester",
    "MessageProcessor",
    "SessionLifecycleManager",
    "IngestionMessage",
    "MessageSaver",
    "IMessageSaver",
    "ExternalMessageSaver",
    "SaveResult",
    "SaveStatus",
    "PollingService",
    "should_process_message",
    "ChatSyncService",
    "SessionManager",
    "PendingCleanupService",
    "TelegramConnection",
    "IngestionServices",
]
