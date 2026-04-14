"""
Хранилище состояний для Rate Limiter.

Управление скользящим окном запросов и статистикой.
"""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RateLimitState:
    """Состояние хранилища для Rate Limiter."""
    # Скользящее окно запросов (временные метки)
    request_times: deque[float] = field(default_factory=deque)
    
    # Статистика выполнения (последние 1000 запросов)
    execution_times: deque[float] = field(default_factory=deque)
    
    # Счётчик пакетов для Batch Delays
    batch_counter: int = 0
    
    # Время последнего сброса счётчика пакетов
    last_batch_reset_time: Optional[float] = None
    
    # Lock для потокобезопасности
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    
    # Lock для скользящего окна
    request_times_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    
    # Lock для статистики
    stats_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class InMemoryStorage:
    """
    In-memory хранилище состояний для Rate Limiter.
    
    Хранит скользящее окно запросов и статистику выполнения.
    """
    
    def __init__(self, max_execution_times: int = 1000):
        """
        Инициализация хранилища.
        
        Args:
            max_execution_times: Максимальное количество записей execution_times.
        """
        self.state = RateLimitState()
        self.max_execution_times = max_execution_times
    
    async def record_request(self) -> None:
        """Записать временную метку запроса в скользящее окно."""
        async with self.state.request_times_lock:
            self.state.request_times.append(time.time())
    
    async def clean_old_requests(self, window_seconds: float = 60.0) -> None:
        """
        Очистить старые записи из скользящего окна.
        
        Args:
            window_seconds: Размер окна в секундах.
        """
        async with self.state.request_times_lock:
            cutoff = time.time() - window_seconds
            while self.state.request_times and self.state.request_times[0] < cutoff:
                self.state.request_times.popleft()
    
    async def get_request_count(self, window_seconds: float = 60.0) -> int:
        """
        Получить количество запросов за период.
        
        Args:
            window_seconds: Размер окна в секундах.
            
        Returns:
            Количество запросов в окне.
        """
        async with self.state.request_times_lock:
            cutoff = time.time() - window_seconds
            count = sum(1 for t in self.state.request_times if t >= cutoff)
            return count
    
    async def record_execution_time(self, execution_time_ms: float) -> None:
        """
        Записать время выполнения запроса.
        
        Args:
            execution_time_ms: Время выполнения в миллисекундах.
        """
        async with self.state.stats_lock:
            self.state.execution_times.append(execution_time_ms)
            while len(self.state.execution_times) > self.max_execution_times:
                self.state.execution_times.popleft()
    
    async def get_avg_execution_time(self) -> float:
        """
        Получить среднее время выполнения.
        
        Returns:
            Среднее время в миллисекундах.
        """
        async with self.state.stats_lock:
            if not self.state.execution_times:
                return 0.0
            return sum(self.state.execution_times) / len(self.state.execution_times)
    
    async def increment_batch_counter(
        self,
        reset_threshold_seconds: float = 60.0
    ) -> tuple[int, bool]:
        """
        Увеличить счётчик пакетов.
        
        Args:
            reset_threshold_seconds: Порог сброса счётчика в секундах.
            
        Returns:
            Кортеж (текущий счётчик, был ли сброшен).
        """
        now = time.time()
        reset = False
        
        # Сбрасываем если прошло больше порога без запросов
        if self.state.last_batch_reset_time is not None:
            time_since_reset = now - self.state.last_batch_reset_time
            if time_since_reset > reset_threshold_seconds:
                self.state.batch_counter = 0
                reset = True
        self.state.last_batch_reset_time = now
        
        self.state.batch_counter += 1
        return self.state.batch_counter, reset
    
    async def reset_batch_counter(self) -> None:
        """Сбросить счётчик пакетов."""
        self.state.batch_counter = 0
        self.state.last_batch_reset_time = time.time()
    
    async def get_batch_counter(self) -> int:
        """Получить текущий счётчик пакетов."""
        return self.state.batch_counter
    
    def clear(self) -> None:
        """Очистить всё хранилище."""
        self.state.request_times.clear()
        self.state.execution_times.clear()
        self.state.batch_counter = 0
        self.state.last_batch_reset_time = None
