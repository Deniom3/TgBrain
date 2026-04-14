"""
Декораторы для Rate Limiter.

rate_limited — автоматическое применение Rate Limiter
flood_wait_handler — обработка FloodWaitError
"""

import logging
from functools import wraps
from typing import Callable, Optional

from telethon.errors import FloodWaitError

from .limiter import TelegramRateLimiter
from .models import RequestPriority

logger = logging.getLogger(__name__)


def rate_limited(
    limiter: TelegramRateLimiter,
    priority: RequestPriority = RequestPriority.NORMAL
):
    """
    Декоратор для автоматического применения Rate Limiter.

    Usage:
        @rate_limited(limiter, RequestPriority.HIGH)
        async def get_messages(chat_id):
            return await client.get_messages(chat_id)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await limiter.execute(priority, func, *args, **kwargs)
        return wrapper
    return decorator


def flood_wait_handler(
    logger_instance: Optional[logging.Logger] = None,
    log_to_db: Optional[Callable] = None
):
    """
    Декоратор для обработки FloodWaitError.

    Usage:
        @flood_wait_handler(logger)
        async def fetch_data():
            return await client.get_messages(chat_id)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except FloodWaitError as e:
                log_func = logger_instance or logger
                log_func.warning(
                    f"FloodWait в {func.__name__}: {e.seconds} сек. "
                    f"Рекомендуемое время ожидания: {e.seconds} сек"
                )
                if log_to_db:
                    await log_to_db(func.__name__, e.seconds)
                raise
        return wrapper
    return decorator
