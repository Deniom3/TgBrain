"""
Telegram Rate Limiter - управление частотой запросов к Telegram API.

Реализует:
- Глобальный троттлинг (20 запросов/минуту для GetHistory)
- Очередь с приоритетами (High, Normal, Low)
- Human-Like поведение (Random Jitter, Batch Delays)
- Автоматическую обработку FloodWaitError
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, TypeVar

from telethon.errors import FloodWaitError

from .algorithms import RateLimitAlgorithms
from .models import (
    RateLimitConfig,
    RateLimitExceeded,
    RequestPriority,
    RequestStatistics,
    SystemStats,
    ThroughputStats,
)
from .repositories import FloodWaitIncidentRepository, RequestStatisticsRepository
from .storage import InMemoryStorage

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class QueuedRequest:
    """Запрос в очереди."""
    priority: RequestPriority
    func: Callable
    args: tuple
    kwargs: dict
    future: asyncio.Future
    created_at: float = field(default_factory=time.time)

    def __lt__(self, other):
        """Сравнение для PriorityQueue (меньше = выше приоритет)."""
        return self.priority < other.priority


class TelegramRateLimiter:
    """
    Rate Limiter для Telegram API.

    Управление частотой запросов с приоритетами и защитой от FloodWait.
    """

    def __init__(
        self,
        config: Optional[RateLimitConfig] = None,
        request_stats_repo: Optional[RequestStatisticsRepository] = None,
        flood_wait_repo: Optional[FloodWaitIncidentRepository] = None,
    ):
        self.config = config or RateLimitConfig()
        self._request_stats_repo = request_stats_repo
        self._flood_wait_repo = flood_wait_repo

        # Инициализация хранилища и алгоритмов
        self.storage = InMemoryStorage()
        self.algorithms = RateLimitAlgorithms(self.config, self.storage)

        # Очередь запросов с приоритетами
        self._queue: asyncio.PriorityQueue[QueuedRequest] = asyncio.PriorityQueue()

        # Semaphore для ограничения параллелизма
        self._semaphore = asyncio.Semaphore(2)

        # Счётчики статистики (для обратной совместимости)
        self._total_requests = 0
        self._success_requests = 0
        self._failed_requests = 0

        # Worker задача
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False

        # Callback для логирования инцидентов в БД
        self._on_flood_wait_callback: Optional[Callable] = None

    async def start(self) -> None:
        """Запуск worker задачи для обработки очереди."""
        if self._running:
            logger.warning("RateLimiter уже запущен")
            return

        logger.info("Запуск RateLimiter worker...")
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        """Остановка worker задачи."""
        if not self._running:
            return

        logger.info("Остановка RateLimiter worker...")
        self._running = False

        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

        # Отменяем все ожидающие запросы в очереди
        while not self._queue.empty():
            try:
                request = self._queue.get_nowait()
                if not request.future.done():
                    request.future.cancel()
            except asyncio.QueueEmpty:
                break

    def set_flood_wait_callback(self, callback: Callable) -> None:
        """Установить callback для логирования FloodWait инцидентов в БД."""
        self._on_flood_wait_callback = callback

    async def execute(
        self,
        priority: RequestPriority,
        func: Callable,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        """
        Выполнить функцию с учётом приоритета и лимитов.

        Args:
            priority: Приоритет запроса
            func: Функция для выполнения
            *args: Аргументы функции
            **kwargs: Ключевые аргументы функции

        Returns:
            Результат выполнения функции
        """
        if not self._running:
            logger.warning("RateLimiter не запущен, выполняю функцию напрямую")
            return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)

        # Создаём Future для результата
        loop = asyncio.get_event_loop()
        future = loop.create_future()

        # Добавляем запрос в очередь
        request = QueuedRequest(
            priority=priority,
            func=func,
            args=args,
            kwargs=kwargs,
            future=future
        )
        await self._queue.put(request)

        # Ждём результат
        return await future

    async def check_rate_limit(self, key: str, priority: RequestPriority) -> None:
        """
        Проверить лимит частоты запросов.

        Не выполняет операцию, только проверяет возможность выполнения.
        Используется для endpoints которые не требуют выполнения через queue.

        Args:
            key: Уникальный ключ для rate limiting (например, chat_id).
            priority: Приоритет запроса.

        Raises:
            RateLimitExceeded: Если лимит превышен. Вызывается при:
                - Системе заблокирована из-за FloodWait
                - Превышен лимит запросов в минуту
        """
        if not self._running:
            logger.warning("RateLimiter не запущен, пропускаю проверку лимита")
            return

        is_blocked, remaining = await self.algorithms.check_block_status()
        if is_blocked:
            retry_after = max(1, int(remaining))
            logger.warning(
                "Rate limit exceeded: система заблокирована на %d сек (key=%s)",
                retry_after, key,
            )
            raise RateLimitExceeded(retry_after_seconds=retry_after, key=key)

        request_count = await self.storage.get_request_count(window_seconds=60.0)
        if request_count >= self.config.rate_limit_per_minute:
            logger.warning(
                "Rate limit exceeded: лимит %d запросов/мин (key=%s, current=%d)",
                self.config.rate_limit_per_minute, key, request_count,
            )
            raise RateLimitExceeded(retry_after_seconds=60, key=key)

        await self.storage.record_request()
        logger.debug(
            "Rate limit check passed: key=%s, priority=%s, request_count=%d",
            key, priority.value, request_count,
        )

    async def _worker_loop(self) -> None:
        """Основной цикл обработки очереди."""
        while self._running:
            try:
                # Проверяем блокировку от FloodWait
                is_blocked, remaining = await self.algorithms.check_block_status()
                if is_blocked:
                    await asyncio.sleep(0.5)
                    continue

                # Получаем запрос из очереди (с таймаутом)
                try:
                    request = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                # Проверяем лимит частоты
                await self.algorithms.wait_for_rate_limit()

                # Применяем Human-Like задержки
                await self.algorithms.apply_human_like_delay()

                # Выполняем запрос
                await self._execute_request(request)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Ошибка в worker loop: %s", e, exc_info=True)
                await asyncio.sleep(1)

    async def _execute_request(self, request: QueuedRequest) -> None:
        """Выполнение запроса с обработкой ошибок."""
        start_time = time.time()

        try:
            # Обновляем скользящее окно
            await self.storage.record_request()

            # Выполняем функцию
            if asyncio.iscoroutinefunction(request.func):
                result = await request.func(*request.args, **request.kwargs)
            else:
                result = request.func(*request.args, **request.kwargs)

            # Успех
            execution_time = (time.time() - start_time) * 1000
            await self.storage.record_execution_time(execution_time)

            # Сохраняем статистику в БД
            stat = RequestStatistics(
                method_name=request.func.__name__,
                chat_id=request.kwargs.get('chat_id'),
                priority=request.priority.value,
                execution_time_ms=int(execution_time),
                is_success=True,
                error_message=None
            )
            if self._request_stats_repo:
                await self._request_stats_repo.save(stat)

            self._success_requests += 1
            self._total_requests += 1

            if not request.future.done():
                request.future.set_result(result)

        except FloodWaitError as e:
            # Обработка FloodWait
            await self.algorithms.handle_flood_wait(
                e,
                request.func.__name__,
                self._on_flood_wait_callback
            )

            # Сохраняем ошибку в БД
            execution_time = (time.time() - start_time) * 1000
            stat = RequestStatistics(
                method_name=request.func.__name__,
                chat_id=request.kwargs.get('chat_id'),
                priority=request.priority.value,
                execution_time_ms=int(execution_time),
                is_success=False,
                error_message="FloodWait: %s seconds" % e.seconds
            )
            if self._request_stats_repo:
                await self._request_stats_repo.save(stat)

            self._failed_requests += 1
            self._total_requests += 1

            if not request.future.done():
                request.future.set_exception(e)

        except Exception as e:
            # Другие ошибки
            execution_time = (time.time() - start_time) * 1000
            await self.storage.record_execution_time(execution_time)

            # Сохраняем ошибку в БД
            stat = RequestStatistics(
                method_name=request.func.__name__,
                chat_id=request.kwargs.get('chat_id'),
                priority=request.priority.value,
                execution_time_ms=int(execution_time),
                is_success=False,
                error_message=str(e)
            )
            if self._request_stats_repo:
                await self._request_stats_repo.save(stat)

            self._failed_requests += 1
            self._total_requests += 1

            if not request.future.done():
                request.future.set_exception(e)

    def get_throughput_stats(self) -> ThroughputStats:
        """Получить статистику пропускной способности."""
        now = time.time()
        minute_ago = now - 60.0
        hour_ago = now - 3600.0

        # Считаем запросы за минуту и час
        requests_per_minute = len([
            t for t in self.storage.state.request_times
            if t >= minute_ago
        ])
        requests_per_hour = len([
            t for t in self.storage.state.request_times
            if t >= hour_ago
        ])

        # Среднее время выполнения
        avg_execution_time = 0.0
        if self.storage.state.execution_times:
            avg_execution_time = sum(self.storage.state.execution_times) / len(self.storage.state.execution_times)

        # Считаем FloodWait инциденты за час (упрощённо)
        flood_wait_count = self._failed_requests  # Приблизительно

        return ThroughputStats(
            requests_per_minute=requests_per_minute,
            requests_per_hour=requests_per_hour,
            success_count=self._success_requests,
            error_count=self._failed_requests,
            avg_execution_time_ms=avg_execution_time,
            flood_wait_count=flood_wait_count,
        )

    def get_system_stats(self) -> SystemStats:
        """Получить общую статистику системы."""
        throttle_remaining = self.algorithms.get_block_remaining()

        return SystemStats(
            total_requests=self._total_requests,
            success_requests=self._success_requests,
            failed_requests=self._failed_requests,
            flood_wait_incidents=self.algorithms.get_flood_wait_count(),
            current_batch_size=self.algorithms.current_batch_size,
            is_throttled=throttle_remaining > 0,
            throttle_remaining_seconds=throttle_remaining,
        )

    @property
    def is_running(self) -> bool:
        """Статус работы worker задачи."""
        return self._running

    @property
    def current_batch_size(self) -> int:
        """Текущий размер пакета (может быть уменьшен после FloodWait)."""
        return self.algorithms.current_batch_size

    # ==========================================================================
    # Свойства для обратной совместимости с тестами
    # ==========================================================================

    @property
    def _is_blocked(self) -> bool:
        """Статус блокировки (для тестов)."""
        return self.algorithms.is_blocked()

    @_is_blocked.setter
    def _is_blocked(self, value: bool) -> None:
        """Установка статуса блокировки (для тестов)."""
        if value:
            self.algorithms._block_until = time.time() + 60
        else:
            self.algorithms.clear_block()

    @property
    def _block_until(self) -> Optional[float]:
        """Время окончания блокировки (для тестов)."""
        return self.algorithms._block_until

    @_block_until.setter
    def _block_until(self, value: Optional[float]) -> None:
        """Установка времени блокировки (для тестов)."""
        self.algorithms._block_until = value

    async def _handle_flood_wait(
        self,
        error: FloodWaitError,
        request: QueuedRequest
    ) -> None:
        """Обработка FloodWait (для тестов)."""
        await self.algorithms.handle_flood_wait(
            error,
            request.func.__name__,
            self._on_flood_wait_callback
        )

    async def _apply_human_like_delay(self) -> None:
        """Применение Human-Like задержек (для тестов)."""
        await self.algorithms.apply_human_like_delay()
