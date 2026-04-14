"""
Алгоритмы Rate Limiting для Telegram API.

Реализует:
- Rate Limit контроль (скользящее окно)
- Human-Like задержки (Random Jitter, Batch Delays)
- FloodWait обработка
"""

import asyncio
import logging
import random
import time
from typing import TYPE_CHECKING, Callable, Optional, TypeVar

from telethon.errors import FloodWaitError

from .models import FloodWaitIncident, RateLimitConfig

if TYPE_CHECKING:
    from .storage import InMemoryStorage

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RateLimitAlgorithms:
    """
    Алгоритмы контроля частоты запросов.
    
    Реализует логику rate limiting без привязки к очереди.
    """
    
    def __init__(
        self,
        config: RateLimitConfig,
        storage: 'InMemoryStorage'
    ):
        """
        Инициализация алгоритмов.
        
        Args:
            config: Конфигурация Rate Limiter.
            storage: Хранилище состояний.
        """
        self.config = config
        self.storage = storage
        
        # Флаг блокировки от FloodWait
        self._is_blocked = False
        self._block_until: Optional[float] = None
        self._block_lock = asyncio.Lock()
        
        # Текущий batch_size (может уменьшаться после FloodWait)
        self._current_batch_size = config.batch_size
        self._slowdown_until: Optional[float] = None
        
        # Счётчик FloodWait инцидентов
        self._flood_wait_count = 0
    
    async def wait_for_rate_limit(self) -> None:
        """
        Ожидание соблюдения лимита частоты.
        
        Проверяет скользящее окно и ждёт если лимит превышен.
        """
        async with self.storage.state.request_times_lock:
            now = time.time()
            cutoff = now - 60.0
            
            # Удаляем старые записи
            while self.storage.state.request_times and self.storage.state.request_times[0] < cutoff:
                self.storage.state.request_times.popleft()
            
            # Проверяем лимит
            if len(self.storage.state.request_times) >= self.config.rate_limit_per_minute:
                # Нужно ждать освобождения окна
                oldest = self.storage.state.request_times[0]
                wait_time = oldest + 60.0 - now + 0.1
                if wait_time > 0:
                    logger.debug(f"Rate limit: ожидание {wait_time:.2f} сек")
                    await asyncio.sleep(wait_time)
                    
                    # Рекурсивно проверяем снова
                    await self.wait_for_rate_limit()
                    return
    
    async def apply_human_like_delay(self) -> None:
        """
        Применение Human-Like задержек.
        
        Random Jitter между запросами + Batch Delays после N запросов.
        """
        # Random Jitter между запросами
        jitter = random.uniform(
            self.config.jitter_min_seconds,
            self.config.jitter_max_seconds
        )
        await asyncio.sleep(jitter)
        
        # Batch Delays
        batch_count, was_reset = await self.storage.increment_batch_counter(
            reset_threshold_seconds=60.0
        )
        
        if was_reset:
            logger.info("✅ Batch counter reset after 60s idle")
        
        if batch_count >= self.config.batch_count_before_break:
            await self.storage.reset_batch_counter()
            break_time = random.uniform(
                self.config.break_min_seconds,
                self.config.break_max_seconds
            )
            logger.info(
                f"Batch delay: перерыв на {break_time:.1f} сек "
                f"(after {self.config.batch_count_before_break} requests)"
            )
            await asyncio.sleep(break_time)
    
    async def handle_flood_wait(
        self,
        error: FloodWaitError,
        method_name: str,
        on_flood_wait_callback: Optional[Callable] = None
    ) -> None:
        """
        Обработка ошибки FloodWait.
        
        Args:
            error: Ошибка FloodWaitError.
            method_name: Имя метода который вызвал ошибку.
            on_flood_wait_callback: Callback для логирования в БД.
        """
        error_seconds = error.seconds
        actual_wait = error_seconds + self.config.flood_buffer_seconds
        
        logger.warning(
            f"🚫 FloodWait: {error_seconds} сек. "
            f"Блокировка на {actual_wait} сек (с буфером {self.config.flood_buffer_seconds})"
        )
        
        # Блокируем очередь
        async with self._block_lock:
            self._is_blocked = True
            self._block_until = time.time() + actual_wait
        
        # Уменьшаем batch_size
        old_batch_size = self._current_batch_size
        self._current_batch_size = max(
            10,
            int(self._current_batch_size * self.config.auto_slowdown_factor)
        )
        self._slowdown_until = time.time() + (self.config.auto_slowdown_duration_minutes * 60)
        
        logger.info(
            f"⚠️ Batch size уменьшен: {old_batch_size} → {self._current_batch_size} "
            f"(на {self.config.auto_slowdown_duration_minutes} мин)"
        )
        
        # Записываем инцидент
        incident = FloodWaitIncident(
            method_name=method_name,
            error_seconds=error_seconds,
            actual_wait_seconds=actual_wait,
            batch_size_before=old_batch_size,
            batch_size_after=self._current_batch_size,
        )
        
        # Увеличиваем счётчик инцидентов
        self._flood_wait_count += 1
        
        if on_flood_wait_callback:
            await on_flood_wait_callback(incident)
    
    async def check_block_status(self) -> tuple[bool, int]:
        """
        Проверка статуса блокировки.
        
        Returns:
            Кортеж (заблокирован ли, остаток секунд блокировки).
        """
        async with self._block_lock:
            if self._is_blocked:
                if self._block_until and time.time() < self._block_until:
                    remaining = int(self._block_until - time.time())
                    return True, remaining
                else:
                    # Блокировка истекла
                    self._is_blocked = False
                    self._block_until = None
                    logger.info("✅ Блокировка FloodWait снята")
            return False, 0
    
    def clear_block(self) -> None:
        """Снять блокировку вручную."""
        self._is_blocked = False
        self._block_until = None
    
    @property
    def current_batch_size(self) -> int:
        """
        Текущий размер пакета (может быть уменьшен после FloodWait).
        
        Автоматически восстанавливается после окончания периода замедления.
        """
        if self._slowdown_until and time.time() >= self._slowdown_until:
            if self._current_batch_size != self.config.batch_size:
                logger.info(
                    f"✅ Batch size восстановлен: {self._current_batch_size} → "
                    f"{self.config.batch_size}"
                )
                self._current_batch_size = self.config.batch_size
                self._slowdown_until = None
        return self._current_batch_size
    
    def is_blocked(self) -> bool:
        """Проверить статус блокировки."""
        return self._is_blocked
    
    def get_block_remaining(self) -> int:
        """Получить остаток секунд блокировки."""
        if self._is_blocked and self._block_until:
            return max(0, int(self._block_until - time.time()))
        return 0
    
    def get_flood_wait_count(self) -> int:
        """Получить количество FloodWait инцидентов."""
        return self._flood_wait_count
