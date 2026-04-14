"""
Rate Limiter - управление частотой запросов к Telegram API.

Компоненты:
- TelegramRateLimiter: Ядро системы с очередью приоритетов
- RateLimitAlgorithms: Алгоритмы rate limiting и Human-Like задержек
- InMemoryStorage: Хранилище состояний (скользящее окно, статистика)
- FloodWait защита: Автоматическая обработка ошибок 420
- Статистика: Мониторинг нагрузки и инцидентов
"""

from .algorithms import RateLimitAlgorithms
from .decorators import rate_limited, flood_wait_handler
from .limiter import (
    TelegramRateLimiter,
)
from .models import (
    RequestPriority,
    RequestStatistics,
    FloodWaitIncident,
    RateLimitConfig,
    ThroughputStats,
    SystemStats,
)
from .storage import InMemoryStorage

__all__ = [
    # Core classes
    "TelegramRateLimiter",
    "RateLimitAlgorithms",
    "InMemoryStorage",
    # Models
    "RequestPriority",
    "RequestStatistics",
    "FloodWaitIncident",
    "RateLimitConfig",
    "ThroughputStats",
    "SystemStats",
    # Decorators
    "rate_limited",
    "flood_wait_handler",
]
