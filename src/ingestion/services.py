"""
IngestionServices — координатор сервисов ingestion.

Интеграция всех компонентов для сбора и обработки сообщений.
"""

import logging
from typing import Optional

import asyncpg

from ..config import Settings
from ..embeddings import EmbeddingsClient
from ..rate_limiter import TelegramRateLimiter
from ..settings.repositories.app_settings import AppSettingsRepository
from ..settings.repositories.telegram_auth import TelegramAuthRepository
from .chat_sync_service import ChatSyncService
from .ingester import TelegramIngester
from .pending_cleanup_service import PendingCleanupService
from .saver import MessageSaver
from .session_manager import SessionManager
from .telegram_connection import TelegramConnection

logger = logging.getLogger(__name__)


class IngestionServices:
    """
    Координатор сервисов ingestion.

    Объединяет все компоненты для работы с Telegram:
    - SessionManager — управление сессиями
    - TelegramConnection — подключение к Telegram
    - MessageSaver — сохранение сообщений
    - PendingCleanupService — очистка pending

    Attributes:
        config: Настройки приложения
        embeddings: Клиент эмбеддингов
        rate_limiter: Rate limiter для API запросов
        pool: Пул подключений к БД
    """

    def __init__(
        self,
        config: Settings,
        embeddings: EmbeddingsClient,
        telegram_auth_repo: TelegramAuthRepository,
        app_settings_repo: AppSettingsRepository,
        rate_limiter: Optional[TelegramRateLimiter] = None,
        pool: Optional[asyncpg.Pool] = None
    ):
        self.config = config
        self.embeddings = embeddings
        self.rate_limiter = rate_limiter
        self._pool = pool

        # Инициализация компонентов
        self.session_manager = SessionManager(config, telegram_auth_repo, app_settings_repo)
        self.telegram_connection: Optional[TelegramConnection] = None
        self.pending_cleanup = PendingCleanupService(config)
        self.saver: Optional[MessageSaver] = None

        # TelegramIngester для обратной совместимости
        self.ingester = TelegramIngester(
            config,
            embeddings,
            telegram_auth_repo,
            app_settings_repo,
            rate_limiter,
        )

    async def initialize(self) -> None:
        """
        Инициализировать сервисы.

        Создаёт MessageSaver после получения пула подключений.
        """
        if self._pool is None:
            from ..database import get_pool
            self._pool = await get_pool()

        self.saver = MessageSaver(self.config, self._pool, self.embeddings)
        logger.info("✅ IngestionServices инициализированы")

    async def start_monitoring(self, chat_ids: list[int]) -> None:
        """
        Запустить мониторинг чатов.

        Args:
            chat_ids: Список ID чатов для мониторинга.
        """
        if not self.saver:
            await self.initialize()

        logger.info(f"Запуск мониторинга для {len(chat_ids)} чатов...")

        # Загрузка последних ID сообщений для каждого чата через ingester
        await self.ingester.initialize_monitored_chats(chat_ids)

        logger.info(f"✅ Мониторинг запущен для {len(chat_ids)} чатов")

    async def stop_monitoring(self) -> None:
        """
        Остановить мониторинг чатов.

        Останавливает polling и закрывает подключения.
        """
        logger.info("Остановка мониторинга...")

        if self.ingester:
            await self.ingester.stop()

        if self.pending_cleanup:
            self.pending_cleanup.stop()

        logger.info("✅ Мониторинг остановлен")

    async def get_monitored_chats(self) -> list[int]:
        """
        Получить список monitored чатов.

        Returns:
            Список ID monitored чатов.
        """
        from ..database import get_pool
        from ..settings.repositories.chat_settings import ChatSettingsRepository

        pool = await get_pool()
        repo = ChatSettingsRepository(pool)
        return await repo.get_monitored_chat_ids()

    async def sync_chats(self, client, limit: int = 100, preserve_existing: bool = True) -> dict:
        """
        Синхронизировать чаты с Telegram.

        Args:
            client: Telegram клиент.
            limit: Лимит чатов для синхронизации.
            preserve_existing: Сохранять существующие настройки.

        Returns:
            Статистика синхронизации.
        """
        sync_service = ChatSyncService(self._pool)
        include_private = bool(self.config.tg_chat_enable_list)

        return await sync_service.sync_chats_with_telegram(
            client,
            limit=limit,
            preserve_existing=preserve_existing,
            include_private=include_private
        )

    async def apply_env_settings(self) -> dict:
        """
        Применить настройки из .env.

        Returns:
            Статистика применения настроек.
        """
        sync_service = ChatSyncService(self._pool)
        return await sync_service.apply_env_initialization(
            self.config.tg_chat_enable_list,
            self.config.tg_chat_disable_list
        )

    def get_stats(self) -> dict:
        """
        Получить статистику ingestion.

        Returns:
            Статистика обработки сообщений.
        """
        return self.ingester.get_stats() if self.ingester else {}
