"""
Хелперы для кэширования summary.

Вынесено из SummaryTaskService для уменьшения размера файла.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional


def calculate_cache_ttl(
    period_start: datetime,
    period_end: datetime,
) -> Optional[int]:
    """
    Рассчитать TTL для кэширования summary в зависимости от возраста периода.

    ✨ Задача 26: Плавающий TTL.

    Args:
        period_start: Начало периода запроса.
        period_end: Окончание периода запроса.

    Returns:
        TTL в минутах или None (без ограничений).

    Правила:
        - < 24 часов с конца периода → 120 минут (2 часа)
        - < 72 часов с конца периода → 1440 минут (24 часа)
        - >= 72 часов → без ограничений (данные стабильны)
    """
    now = datetime.now(timezone.utc)
    age_hours = (now - period_end).total_seconds() / 3600

    if age_hours < 24:
        return 120  # 2 часа для "сегодня"
    elif age_hours < 72:
        return 1440  # 24 часа для "вчера" и "позавчера"
    else:
        return None  # Без ограничений для "архив"


def generate_params_hash(
    chat_id: int,
    period_start: datetime,
    period_end: datetime,
    prompt_version: str = "v1",
    model_name: Optional[str] = None,
) -> str:
    """
    Сгенерировать хеш параметров для кэширования.

    ✨ Задача 26: Округление до 6 часов для period > 3 часов.
    
    Args:
        chat_id: ID чата.
        period_start: Начало периода.
        period_end: Окончание периода.
        prompt_version: Версия промпта.
        model_name: Название модели.

    Returns:
        Хеш параметров (32 символа).

    Правила округления:
        - period_hours <= 3 → округление до 1 часа
        - period_hours > 3 → округление до 6 часов
    """
    period_hours = (period_end - period_start).total_seconds() / 3600
    round_hours = 6 if period_hours > 3 else 1

    period_start_rounded = period_start.replace(minute=0, second=0, microsecond=0)
    hour = (period_start_rounded.hour // round_hours) * round_hours
    period_start_rounded = period_start_rounded.replace(hour=hour)

    period_end_rounded = period_end.replace(minute=0, second=0, microsecond=0)
    hour = (period_end_rounded.hour // round_hours) * round_hours
    period_end_rounded = period_end_rounded.replace(hour=hour)

    params = {
        "chat_id": chat_id,
        "period_start": period_start_rounded.isoformat(),
        "period_end": period_end_rounded.isoformat(),
        "prompt_version": prompt_version,
        "model_name": model_name or "default",
    }

    params_json = json.dumps(params, sort_keys=True)
    return hashlib.sha256(params_json.encode()).hexdigest()[:32]
