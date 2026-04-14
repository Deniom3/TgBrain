"""
TelegramIngester — координатор сбора сообщений из Telegram.

SECURITY: Все session_data шифруются перед записью.
Временные файлы создаются с правами 600 и очищаются при crash.
"""

import asyncio
import logging
from asyncio import Task
from typing import Callable, Optional

import asyncpg

from ..config import Settings
from ..database import get_pool
from ..embeddings import EmbeddingsClient
from ..rate_limiter import TelegramRateLimiter
from ..settings.repositories.app_settings import AppSettingsRepository
from ..settings.repositories import ChatSettingsRepository
from ..settings.repositories.encryption_settings import EncryptionKeyMismatchError
from ..settings.repositories.telegram_auth import TelegramAuthRepository
from .chat_sync_service import ChatSyncService
from .message_processing import MessageProcessor
from .pending_cleanup_service import PendingCleanupService
from .saver import MessageSaver
from .session_lifecycle import SessionLifecycleManager
from .session_manager import SessionManager
from .telegram_connection import TelegramConnection

logger = logging.getLogger(__name__)


# Константы для polling и ожидания
PENDING_CLEANUP_INIT_TIMEOUT_SECONDS = 5.0
PENDING_CLEANUP_POLL_INTERVAL_SECONDS = 0.1


class TelegramIngester:
    """Координатор сбора сообщений из Telegram."""

    def __init__(
        self,
        config: Settings,
        embeddings_client: EmbeddingsClient,
        telegram_auth_repo: TelegramAuthRepository,
        app_settings_repo: AppSettingsRepository,
        rate_limiter: Optional[TelegramRateLimiter] = None,
    ):
        self.config = config
        self.embeddings = embeddings_client
        self.rate_limiter = rate_limiter
        self._telegram_auth_repo = telegram_auth_repo
        self._app_settings_repo = app_settings_repo
        self._pool: Optional[asyncpg.Pool] = None
        self._running = False
        self._session_manager: Optional[SessionManager] = None
        self._telegram_connection: Optional[TelegramConnection] = None
        self._session_lifecycle: Optional[SessionLifecycleManager] = None
        self._saver: Optional[MessageSaver] = None
        self._pending_cleanup: Optional[PendingCleanupService] = None
        self._message_processor: Optional[MessageProcessor] = None
        self._polling_task: Optional[Task[None]] = None
        self._cleanup_task: Optional[Task[None]] = None
        self._message_handler: Optional[Callable[..., None]] = None
        self._stop_event = asyncio.Event()

    def refresh_config(self, new_settings: Settings) -> None:
        """Обновить ссылку на Settings после reload.

        Args:
            new_settings: Новый экземпляр Settings.
        """
        self.config = new_settings
        logger.debug("TelegramIngester обновлён")

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await get_pool()
        return self._pool

    async def start(self) -> None:
        """Запуск Telegram клиента и начало мониторинга."""
        if self._running:
            logger.warning("Ingester уже запущен")
            return

        logger.info("Запуск Telegram Ingester...")
        try:
            self._session_manager = SessionManager(self.config, self._telegram_auth_repo, self._app_settings_repo)
            session_data = await self._session_manager.load_session_data()
            if not session_data:
                logger.error("session_data не найдена в БД")
                return

            try:
                decrypted_data = await self._session_manager.decrypt_session_data(
                    session_data
                )
            except EncryptionKeyMismatchError:
                logger.error(
                    "❌ Не удалось расшифровать session_data: ключ шифрования не совпадает. "
                    "Это происходит когда: "
                    "1) Ключ в БД изменился (пересоздали БД или изменили ENCRYPTION_KEY), "
                    "2) Данные повреждены. "
                    "Решение: выполните повторную авторизацию через QR-код."
                )
                logger.info(
                    "Для повторной авторизации: "
                    "1) Откройте веб-интерфейс, "
                    "2) Перейдите в раздел 'QR Auth', "
                    "3) Отсканируйте новый QR-код в Telegram."
                )
                return
            
            temp_file_path = (
                await self._session_manager.create_temp_session_file(decrypted_data)
            )

            self._telegram_connection = TelegramConnection(self.config, temp_file_path)
            self._session_lifecycle = SessionLifecycleManager(
                self.config, self._session_manager, self._telegram_connection
            )
            self._session_lifecycle.set_temp_session_file(temp_file_path)

            if not await self._session_lifecycle.connect():
                logger.error("Не удалось подключиться к Telegram")
                return

            self._saver = MessageSaver(
                self.config, await self._get_pool(), self.embeddings
            )

            await self._sync_chats()
            await self._apply_env_settings()

            chat_settings_repo = ChatSettingsRepository(await self._get_pool())
            monitored_chats = await chat_settings_repo.get_monitored_chat_ids()
            logger.info("Monitored чаты из БД: %s чатов", len(monitored_chats))

            self._pending_cleanup = PendingCleanupService(self.config)
            self._message_processor = MessageProcessor(
                self.config, self._saver, self._pending_cleanup
            )

            await self._message_processor.initialize_monitored_chats(monitored_chats)
            self._running = True
            logger.info("Мониторинг запущен для %s чатов", len(monitored_chats))

            self._register_event_handler()
            self._polling_task = asyncio.create_task(self._polling_loop())
            
            # Запуск фоновой задачи очистки pending сообщений
            self._cleanup_task = asyncio.create_task(self.start_cleanup_task())
            logger.info("Задача очистки pending запущена")

        except Exception as exc:
            logger.error("Ошибка при запуске Ingester: %s", exc, exc_info=True)
            raise

    async def _sync_chats(self) -> None:
        sync_service = ChatSyncService(await self._get_pool())
        logger.info("Синхронизация чатов с Telegram...")
        sync_stats = await sync_service.sync_chats_with_telegram(
            self._session_lifecycle.get_client(),  # type: ignore
            limit=100,
            preserve_existing=True,
            include_private=bool(self.config.tg_chat_enable_list),
        )
        logger.info("Синхронизация завершена: %s", sync_stats)

    async def _apply_env_settings(self) -> None:
        enable_list = self.config.tg_chat_enable_list
        disable_list = self.config.tg_chat_disable_list
        if enable_list or disable_list:
            logger.info("Применение настроек из .env...")
            sync_service = ChatSyncService(await self._get_pool())
            env_stats = await sync_service.apply_env_initialization(
                enable_list, disable_list
            )
            logger.info("Настройки применены: %s", env_stats)

    def _register_event_handler(self) -> None:
        if not self._session_lifecycle:
            return
        client = self._session_lifecycle.get_client()
        if client:
            from telethon.tl.types import Message
            from telethon import events

            # Удаляем старый обработчик перед регистрацией нового (защита от дублирования)
            if self._message_handler:
                client.remove_event_handler(self._message_handler)
                logger.debug("Старый обработчик сообщений удалён")

            # Регистрируем обработчик только на сообщения
            @client.on(events.NewMessage)
            async def message_handler(event):
                if hasattr(event, 'message') and isinstance(event.message, Message):
                    await self._message_processor.handle_new_message(event)  # type: ignore

            self._message_handler = message_handler
            logger.info("Обработчик событий зарегистрирован")

    async def _polling_loop(self) -> None:
        while self._running:
            try:
                if self._session_lifecycle:
                    client = self._session_lifecycle.get_client()
                    if client and self._message_processor:
                        await self._message_processor.poll_messages(
                            client, self.rate_limiter
                        )
            except Exception as e:
                logger.error("Ошибка в polling: %s", e)
            await asyncio.sleep(5)

    async def stop(self) -> None:
        if not self._running:
            return

        logger.info("Остановка Telegram Ingester...")
        self._running = False

        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except (asyncio.CancelledError, Exception) as e:
                if not isinstance(e, asyncio.CancelledError):
                    logger.error("Ошибка при отмене polling: %s", e)
            self._polling_task = None

        # Остановка задачи очистки pending
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except (asyncio.CancelledError, Exception) as e:
                if not isinstance(e, asyncio.CancelledError):
                    logger.error("Ошибка при отмене cleanup: %s", e)
            self._cleanup_task = None

        if self._session_lifecycle:
            await self._session_lifecycle.disconnect()
            await self._session_lifecycle.cleanup()

        stats = self._message_processor.get_stats() if self._message_processor else {}
        logger.info(
            "Ingester остановлен. Обработано: %s, отфильтровано: %s, ошибок: %s",
            stats.get('processed', 0),
            stats.get('filtered', 0),
            stats.get('errors', 0),
        )

    def is_connected(self) -> bool:
        return bool(self._session_lifecycle and self._session_lifecycle.is_connected())

    def is_running(self) -> bool:
        """
        Проверить, запущен ли Ingester.

        Returns:
            True если Ingester запущен и работает.
        """
        return self._running

    async def stop_cleanup_task(self) -> None:
        """
        Остановить задачу очистки pending сообщений.

        Публичный метод для безопасной остановки cleanup task
        без нарушения инкапсуляции приватных полей.
        """
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except (asyncio.CancelledError, Exception) as e:
                if not isinstance(e, asyncio.CancelledError):
                    logger.error("Ошибка при отмене cleanup: %s", e)
            self._cleanup_task = None
            logger.info("Задача очистки pending остановлена")

    def get_ingestion_task(self) -> Optional[Task[None]]:
        """
        Вернуть polling task для сохранения в state.

        Returns:
            Polling task или None если не инициализирован.
        """
        return self._polling_task

    async def reload_session(self) -> bool:
        logger.info("🔄 Мягкая перезагрузка сессии Telegram...")
        try:
            self._running = False
            if self._polling_task:
                self._polling_task.cancel()
                try:
                    await self._polling_task
                except (asyncio.CancelledError, Exception) as e:
                    if not isinstance(e, asyncio.CancelledError):
                        logger.error("Ошибка при отмене polling: %s", e)
                self._polling_task = None

            await asyncio.sleep(0.5)
            if not self._session_lifecycle:
                logger.error("SessionLifecycleManager не инициализирован")
                return False

            if not await self._session_lifecycle.reload_session():
                return False

            self._saver = MessageSaver(
                self.config, await self._get_pool(), self.embeddings
            )
            logger.info("✅ MessageSaver инициализирован")

            if self._message_processor:
                self._message_processor.saver = self._saver

            chat_settings_repo = ChatSettingsRepository(await self._get_pool())
            monitored_chats = await chat_settings_repo.get_monitored_chat_ids()
            if self._message_processor:
                await self._message_processor.initialize_monitored_chats(monitored_chats)

            self._register_event_handler()
            self._running = True
            self._polling_task = asyncio.create_task(self._polling_loop())
            logger.info("✅ Сессия успешно обновлена")
            return True

        except Exception as e:
            logger.error("Ошибка перезагрузки сессии: %s", e, exc_info=True)
            return False

    async def reload_monitored_chats(self) -> None:
        if self._message_processor:
            await self._message_processor.reload_monitored_chats()

    def get_stats(self) -> dict[str, object]:
        if self._message_processor:
            return self._message_processor.get_stats()
        return {"processed": 0, "filtered": 0, "errors": 0, "running": self._running}

    async def initialize_monitored_chats(self, chat_ids: list[int]) -> None:
        if self._message_processor:
            await self._message_processor.initialize_monitored_chats(chat_ids)

    async def start_cleanup_task(self) -> None:
        """
        Запустить фоновую задачу очистки pending сообщений.

        Делегирует задачу PendingCleanupService.
        """
        if self._pending_cleanup is not None:
            await self._pending_cleanup.start_cleanup_task()
        else:
            logger.warning("PendingCleanupService не инициализирован")

    async def cleanup_old_pending_messages(self) -> int:
        """
        Очистить старые pending сообщения.

        Returns:
            Количество удалённых записей.
        """
        if self._pending_cleanup is None:
            logger.warning("PendingCleanupService не инициализирован")
            return 0

        try:
            return await self._pending_cleanup.cleanup_old_pending_messages()
        except Exception as e:
            logger.error("Ошибка при очистке pending: %s", e, exc_info=True)
            return 0
