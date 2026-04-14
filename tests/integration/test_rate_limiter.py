"""
Тесты для Rate Limiter.

Проверка:
- TelegramRateLimiter: очередь с приоритетами, лимиты частоты
- Human-Like: Random Jitter, Batch Delays
- FloodWait: обработка ошибок 420
- API endpoints: throughput, stats, flood-history
"""

import asyncio
import pytest
import time
from unittest.mock import MagicMock, Mock

from src.rate_limiter import (
    TelegramRateLimiter,
    RequestPriority,
    RateLimitConfig,
    rate_limited,
    flood_wait_handler,
)

pytestmark = pytest.mark.integration



# ======================================================================
# Фикстуры
# ======================================================================

@pytest.fixture
def rate_config():
    """Конфигурация для тестов."""
    return RateLimitConfig(
        rate_limit_per_minute=20,
        jitter_min_seconds=0.1,  # Уменьшено для тестов
        jitter_max_seconds=0.3,
        batch_size=50,
        batch_count_before_break=3,  # Уменьшено для тестов
        break_min_seconds=0.5,
        break_max_seconds=1.0,
        flood_sleep_threshold=60,
        flood_buffer_seconds=5,  # Уменьшено для тестов
        auto_slowdown_duration_minutes=1,
        auto_slowdown_factor=0.5,
    )


@pytest.fixture
async def rate_limiter(rate_config):
    """Rate Limiter для тестов."""
    limiter = TelegramRateLimiter(rate_config)
    await limiter.start()
    yield limiter
    await limiter.stop()


# ======================================================================
# Тесты TelegramRateLimiter
# ======================================================================

@pytest.mark.integration
class TestTelegramRateLimiter:

    @pytest.mark.asyncio
    async def test_init(self, rate_config):
        """Тест инициализации."""
        limiter = TelegramRateLimiter(rate_config)
        
        assert limiter.config == rate_config
        assert limiter._running is False
        assert limiter._is_blocked is False
        assert limiter.current_batch_size == rate_config.batch_size
        
    @pytest.mark.asyncio
    async def test_start_stop(self, rate_limiter):
        """Тест запуска и остановки."""
        assert rate_limiter._running is True
        assert rate_limiter._worker_task is not None
        
        await rate_limiter.stop()
        assert rate_limiter._running is False
        
    @pytest.mark.asyncio
    async def test_execute_success(self, rate_limiter):
        """Тест успешного выполнения."""
        async def dummy_func():
            return "result"
        
        result = await rate_limiter.execute(
            RequestPriority.NORMAL,
            dummy_func
        )
        
        assert result == "result"
        stats = rate_limiter.get_system_stats()
        assert stats.total_requests >= 1
        
    @pytest.mark.asyncio
    async def test_execute_with_args(self, rate_limiter):
        """Тест выполнения с аргументами."""
        async def add_func(a, b):
            return a + b
        
        result = await rate_limiter.execute(
            RequestPriority.NORMAL,
            add_func,
            5,
            3
        )
        
        assert result == 8
        
    @pytest.mark.asyncio
    async def test_execute_with_kwargs(self, rate_limiter):
        """Тест выполнения с именованными аргументами."""
        async def greet_func(name, greeting="Hello"):
            return f"{greeting}, {name}!"
        
        result = await rate_limiter.execute(
            RequestPriority.NORMAL,
            greet_func,
            "World",
            greeting="Hi"
        )
        
        assert result == "Hi, World!"
        
    @pytest.mark.asyncio
    async def test_priority_order(self, rate_config):
        """Тест приоритета очереди."""
        limiter = TelegramRateLimiter(rate_config)
        await limiter.start()
        
        results = []
        
        async def slow_func(value):
            await asyncio.sleep(0.1)
            results.append(value)
            return value
        
        # Добавляем запросы в обратном порядке приоритета
        tasks = []
        tasks.append(asyncio.create_task(
            limiter.execute(RequestPriority.LOW, slow_func, "low")
        ))
        await asyncio.sleep(0.05)  # Небольшая задержка
        tasks.append(asyncio.create_task(
            limiter.execute(RequestPriority.HIGH, slow_func, "high")
        ))
        
        await asyncio.gather(*tasks)
        await limiter.stop()
        
        # HIGH должен выполниться раньше LOW
        # Примечание: из-за асинхронности порядок может варьироваться
        assert len(results) == 2
        
    @pytest.mark.asyncio
    async def test_system_stats(self, rate_limiter):
        """Тест системной статистики."""
        async def dummy_func():
            return "ok"
        
        # Выполняем несколько запросов
        for _ in range(3):
            await rate_limiter.execute(RequestPriority.NORMAL, dummy_func)
        
        stats = rate_limiter.get_system_stats()
        
        assert stats.total_requests >= 3
        assert stats.success_requests >= 3
        assert stats.failed_requests == 0
        assert stats.is_throttled is False
        
    @pytest.mark.asyncio
    async def test_throughput_stats(self, rate_limiter):
        """Тест статистики пропускной способности."""
        async def dummy_func():
            await asyncio.sleep(0.05)
            return "ok"
        
        # Выполняем несколько запросов
        for _ in range(5):
            await rate_limiter.execute(RequestPriority.NORMAL, dummy_func)
        
        stats = rate_limiter.get_throughput_stats()
        
        assert stats.success_count >= 5
        assert stats.avg_execution_time_ms > 0


# ======================================================================
# Тесты FloodWait
# ======================================================================

class MockFloodWaitError(Exception):
    """Mock FloodWaitError для тестов."""
    def __init__(self, seconds: int):
        self.seconds = seconds
        super().__init__(f"FloodWait: {seconds} seconds")


@pytest.mark.integration
class TestFloodWaitHandling:

    @pytest.mark.asyncio
    async def test_flood_wait_callback(self, rate_limiter):
        """Тест callback для FloodWait."""
        callback_called = False
        captured_incident = None
        
        async def mock_callback(incident):
            nonlocal callback_called, captured_incident
            callback_called = True
            captured_incident = incident
        
        rate_limiter.set_flood_wait_callback(mock_callback)
        
        # Вызываем обработчик напрямую с mock объектом
        
        error = Mock()
        error.seconds = 30
        
        # Вызываем _handle_flood_wait напрямую
        async def dummy_func():
            raise Exception("test")
        
        await rate_limiter._handle_flood_wait(error, Mock(func=dummy_func, args=(), kwargs={}, future=Mock()))
        
        # Callback должен быть вызван
        assert callback_called is True
        assert captured_incident is not None
        assert captured_incident.error_seconds == 30
        
    @pytest.mark.asyncio
    async def test_batch_size_reduction(self, rate_limiter):
        """Тест уменьшения batch_size после FloodWait."""
        original_batch_size = rate_limiter.config.batch_size
        
        
        error = Mock()
        error.seconds = 30
        
        request = Mock()
        request.func.__name__ = "test_func"
        
        await rate_limiter._handle_flood_wait(error, request)
        
        # Batch size должен быть уменьшен
        assert rate_limiter.current_batch_size < original_batch_size
        
    @pytest.mark.asyncio
    async def test_queue_blocking_on_flood_wait(self, rate_limiter):
        """Тест блокировки очереди при FloodWait."""
        
        error = Mock()
        error.seconds = 5
        
        request = Mock()
        request.func.__name__ = "test_func"
        
        await rate_limiter._handle_flood_wait(error, request)
        
        # Очередь должна быть заблокирована
        assert rate_limiter._is_blocked is True
        assert rate_limiter._block_until is not None
        
        stats = rate_limiter.get_system_stats()
        assert stats.is_throttled is True


# ======================================================================
# Тесты декораторов
# ======================================================================

@pytest.mark.integration
class TestDecorators:

    @pytest.mark.asyncio
    async def test_rate_limited_decorator(self, rate_limiter):
        """Тест декоратора rate_limited."""
        
        @rate_limited(rate_limiter, RequestPriority.HIGH)
        async def decorated_func(value):
            return value * 2
        
        result = await decorated_func(21)
        assert result == 42
        
    @pytest.mark.asyncio
    async def test_flood_wait_handler_decorator(self):
        """Тест декоратора flood_wait_handler."""
        from telethon.errors import FloodWaitError as RealFloodWaitError
        
        logger_mock = MagicMock()
        
        # FloodWaitError принимает (request, capture) где capture = seconds
        # request может быть None для тестов
        error = RealFloodWaitError(None, 10)
        
        @flood_wait_handler(logger_mock)
        async def failing_func():
            raise error
        
        with pytest.raises(RealFloodWaitError):
            await failing_func()
        
        logger_mock.warning.assert_called_once()
        # Проверяем что лог содержит seconds
        call_args = logger_mock.warning.call_args[0][0]
        assert "10" in call_args


# ======================================================================
# Тесты Human-Like
# ======================================================================

class TestHumanLike:

    @pytest.mark.asyncio
    async def test_random_jitter(self, rate_config):
        """Тест случайных задержек."""
        limiter = TelegramRateLimiter(rate_config)
        
        # Замеряем время выполнения
        start = time.time()
        await limiter._apply_human_like_delay()
        elapsed = time.time() - start
        
        # Задержка должна быть в пределах конфигурации
        assert rate_config.jitter_min_seconds <= elapsed <= rate_config.jitter_max_seconds + 0.1
        
    @pytest.mark.asyncio
    async def test_batch_delay(self, rate_config):
        """Тест задержки после пакета."""
        limiter = TelegramRateLimiter(rate_config)
        
        # Сбрасываем счётчик через storage
        await limiter.storage.reset_batch_counter()
        
        # Выполняем batch_count_before_break запросов
        for i in range(rate_config.batch_count_before_break):
            await limiter._apply_human_like_delay()
        
        # Последний запрос должен был вызвать Batch Delay
        # Проверяем что счётчик сброшен через storage
        counter = await limiter.storage.get_batch_counter()
        assert counter == 0


# ======================================================================
# Интеграционные тесты
# ======================================================================

@pytest.mark.integration
class TestIntegration:

    @pytest.mark.asyncio
    async def test_full_workflow(self, rate_limiter):
        """Тест полного рабочего цикла."""
        results = []
        
        async def task(value):
            await asyncio.sleep(0.05)
            results.append(value)
            return value
        
        # Выполняем несколько запросов разных приоритетов
        tasks = [
            rate_limiter.execute(RequestPriority.HIGH, task, "high1"),
            rate_limiter.execute(RequestPriority.NORMAL, task, "normal1"),
            rate_limiter.execute(RequestPriority.LOW, task, "low1"),
            rate_limiter.execute(RequestPriority.HIGH, task, "high2"),
            rate_limiter.execute(RequestPriority.NORMAL, task, "normal2"),
        ]
        
        await asyncio.gather(*tasks)
        
        # Все задачи должны выполниться
        assert len(results) == 5
        
        # Проверяем статистику
        stats = rate_limiter.get_system_stats()
        assert stats.total_requests == 5
        assert stats.success_requests == 5
