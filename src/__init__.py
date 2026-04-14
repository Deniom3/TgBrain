"""
TgBrain — основной пакет приложения.
"""

from .config import settings, get_settings, Settings, SettingsWithProviders
from .database import get_db, init_db, close_pool
from .embeddings import EmbeddingsClient, EmbeddingsError
from .ingestion import TelegramIngester
from .rag import RAGService

__all__ = [
    "settings",
    "get_settings",
    "Settings",
    "SettingsWithProviders",
    "get_db",
    "init_db",
    "close_pool",
    "EmbeddingsClient",
    "EmbeddingsError",
    "TelegramIngester",
    "RAGService",
]
