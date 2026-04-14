"""
Модели данных для Rate Limiter.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import Optional


class RateLimitExceeded(Exception):
    """
    Превышение лимита частоты запросов.

    Выбрасывается из check_rate_limit() при обнаружении превышения.
    Перехватывается на уровне API и преобразуется в HTTPException 429.

    Attributes:
        retry_after_seconds: Время ожидания перед повторной попыткой.
        key: Ключ rate limiting, по которому обнаружено превышение.
    """

    def __init__(self, retry_after_seconds: int = 60, key: str = "") -> None:
        self.retry_after_seconds = retry_after_seconds
        self.key = key
        super().__init__(
            f"Rate limit exceeded for key='{key}', retry after {retry_after_seconds}s"
        )


class RequestPriority(IntEnum):
    """Приоритеты запросов к Telegram API."""
    LOW = 3       # Фоновые операции (индексация истории)
    NORMAL = 2    # Обычные операции (новые сообщения)
    HIGH = 1      # Критичные операции (авторизация, ответы пользователю)


@dataclass
class RequestStatistics:
    """Статистика запроса к Telegram API."""
    id: Optional[int] = None
    method_name: str = ""
    chat_id: Optional[int] = None
    priority: int = RequestPriority.NORMAL
    execution_time_ms: Optional[int] = None
    is_success: bool = True
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class FloodWaitIncident:
    """Инцидент FloodWait (ошибка 420)."""
    id: Optional[int] = None
    method_name: str = ""
    chat_id: Optional[int] = None
    error_seconds: int = 0
    actual_wait_seconds: int = 0
    batch_size_before: Optional[int] = None
    batch_size_after: Optional[int] = None
    resolved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


@dataclass
class RateLimitConfig:
    """Конфигурация Rate Limiter."""
    # Лимиты частоты
    rate_limit_per_minute: int = 20
    
    # Human-Like настройки
    jitter_min_seconds: float = 1.5
    jitter_max_seconds: float = 4.5
    batch_size: int = 50
    batch_count_before_break: int = 10
    break_min_seconds: float = 30.0
    break_max_seconds: float = 60.0
    
    # Рабочее окно (опционально)
    active_hours_start: int = 8
    active_hours_end: int = 23
    
    # FloodWait настройки
    flood_sleep_threshold: int = 60
    flood_buffer_seconds: int = 15
    
    # Автоматическое замедление
    auto_slowdown_duration_minutes: int = 30
    auto_slowdown_factor: float = 0.5


@dataclass
class ThroughputStats:
    """Статистика пропускной способности."""
    requests_per_minute: int = 0
    requests_per_hour: int = 0
    success_count: int = 0
    error_count: int = 0
    avg_execution_time_ms: float = 0.0
    flood_wait_count: int = 0


@dataclass
class SystemStats:
    """Общая статистика системы."""
    total_requests: int = 0
    success_requests: int = 0
    failed_requests: int = 0
    flood_wait_incidents: int = 0
    current_batch_size: int = 50
    is_throttled: bool = False
    throttle_remaining_seconds: int = 0
