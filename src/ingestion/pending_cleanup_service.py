"""
Сервис очистки pending сообщений.

Периодическая очистка старых pending сообщений из БД.
"""

import asyncio
import logging
from typing import Optional

import asyncpg

from ..config import Settings
from ..database import get_pool
from ..settings.repositories.pending_cleanup_repository import PendingCleanupSettingsRepository
from ..settings.repositories.app_settings import AppSettingsRepository

logger = logging.getLogger(__name__)


class PendingCleanupService:
    """
    Сервис очистки pending сообщений.
    
    Использует настройки из app_settings:
    - pending.ttl_minutes (по умолчанию 240 минут = 4 часа)
    - pending.cleanup_interval_minutes (по умолчанию 60 минут = 1 час)
    
    Удаляет записи из pending_messages где:
    - created_at < NOW() - ($1 || ' minutes')::INTERVAL
    - retry_count >= 3
    
    Attributes:
        config: Настройки приложения
        stop_event: Событие для остановки сервиса
    """
    
    def __init__(
        self,
        config: Settings,
        pool: Optional[asyncpg.Pool] = None,
    ) -> None:
        """
        Инициализировать сервис очистки.
        
        Args:
            config: Настройки приложения.
            pool: Пул подключений к БД.
        """
        self.config = config
        self.stop_event = asyncio.Event()
        self._pool = pool
        self._pending_cleanup_repo: Optional[PendingCleanupSettingsRepository] = None
    
    async def _get_pool(self) -> asyncpg.Pool:
        """Получить пул подключений к БД."""
        if self._pool is None:
            self._pool = await get_pool()
        return self._pool

    async def _get_settings_repo(self) -> PendingCleanupSettingsRepository:
        """Получить репозиторий настроек."""
        if self._pending_cleanup_repo is None:
            pool = await self._get_pool()
            app_settings_repo = AppSettingsRepository(pool)
            self._pending_cleanup_repo = PendingCleanupSettingsRepository(app_settings_repo)
        return self._pending_cleanup_repo
    
    async def cleanup_old_pending_messages(self) -> int:
        """
        Очистка старых pending сообщений.
        
        Returns:
            Количество удалённых записей.
        """
        settings_repo = await self._get_settings_repo()
        settings = await settings_repo.get()
        ttl_minutes = settings.ttl_minutes.value

        pool = await self._get_pool()
        ttl_str = str(ttl_minutes)
        
        async with pool.acquire() as conn:
            async with conn.transaction():
                count_result = await conn.fetchrow("""
                    SELECT COUNT(*) as cnt
                    FROM pending_messages
                    WHERE created_at < NOW() - ($1 || ' minutes')::INTERVAL
                      AND retry_count >= 3
                """, ttl_str)
                
                deleted_count = count_result["cnt"] if count_result else 0
                
                await conn.execute("""
                    DELETE FROM pending_messages
                    WHERE created_at < NOW() - ($1 || ' minutes')::INTERVAL
                      AND retry_count >= 3
                """, ttl_str)
        
        logger.info(
            "Очищено %d pending сообщений (старше %d минут, retry_count >= 3)",
            int(deleted_count),
            ttl_minutes,
        )
        
        return int(deleted_count)
    
    async def start_cleanup_task(self) -> None:
        """
        Периодическая очистка pending сообщений.
        
        Запускает очистку каждые cleanup_interval_minutes.
        При ошибке делает паузу 60 секунд.
        Проверяет флаг остановки self.stop_event.
        """
        logger.info("Запуск фоновой задачи очистки pending сообщений...")
        
        try:
            while not self.stop_event.is_set():
                try:
                    settings_repo = await self._get_settings_repo()
                    settings = await settings_repo.get()
                    interval_minutes = settings.cleanup_interval_minutes.value

                    if interval_minutes > 0:
                        await self.cleanup_old_pending_messages()

                        logger.debug(
                            "Следующая очистка через %d минут", interval_minutes
                        )
                        await asyncio.sleep(interval_minutes * 60)
                        
                        if self.stop_event.is_set():
                            logger.info("Задача очистки pending остановлена (stop event set)")
                            break
                    else:
                        await asyncio.sleep(60)
                        
                        if self.stop_event.is_set():
                            logger.info("Задача очистки pending остановлена (stop event set)")
                            break
                    
                except asyncio.CancelledError:
                    logger.info("Задача очистки pending отменена, завершение текущей операции...")
                    raise
                except Exception as e:
                    logger.error(f"Ошибка cleanup задачи: {e}", exc_info=True)
                    await asyncio.sleep(60)
        finally:
            logger.info("Задача очистки pending завершена")
    
    def stop(self) -> None:
        """
        Остановить сервис очистки.
        
        Устанавливает stop_event для завершения цикла.
        """
        logger.info("Остановка сервиса очистки pending...")
        self.stop_event.set()
    
    def is_running(self) -> bool:
        """
        Проверить, запущен ли сервис.
        
        Returns:
            True если сервис работает (stop_event не установлен).
        """
        return not self.stop_event.is_set()
