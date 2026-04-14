"""
Хелперы для расчёта расписаний генерации summary.

Поддержка форматов:
- HH:MM — простое время (например, "09:00", "23:30")
- Простой cron — */N для минут/часов, дни недели (например, "*/30", "0 9 * * 1")
"""

import logging
import re
from datetime import datetime, timedelta, timezone

from .exceptions import CronParseError, InvalidScheduleError

logger = logging.getLogger(__name__)

# Максимум итераций: 366 дней * 24 часа * 60 минут = 525,600
MAX_CRON_ITERATIONS = 366 * 24 * 60
# Timeout для расчёта cron выражения (секунды)
CRON_CALCULATION_TIMEOUT = 5
# Максимальная длина расписания для логирования
MAX_SCHEDULE_LOG_LENGTH = 100


def calculate_next_run(schedule: str) -> datetime:
    """
    Рассчитать следующее время запуска на основе расписания.

    Args:
        schedule: Строка расписания в формате HH:MM или простого cron.

    Returns:
        Следующее время запуска в UTC (timezone-aware).

    Поддерживаемые форматы:
        - "HH:MM" — запуск в указанное время каждый день
        - "*/N" — запуск каждые N минут
        - "H */N" — запуск каждые N часов в минуту H
        - "H H * * D" — cron-подобный формат (минута, час, день, месяц, день недели)
    """
    schedule = schedule.strip()

    if "/" in schedule or schedule.count(" ") >= 1:
        return calculate_simple_cron(schedule)
    else:
        return calculate_simple(schedule)


def sanitize_for_log(schedule: str) -> str:
    """
    Удалить потенциально опасные символы из расписания.

    Включает:
    - ASCII control chars: \n, \r, \t
    - Unicode line separators: U+2028 (LS), U+2029 (PS)

    Args:
        schedule: Исходная строка расписания.

    Returns:
        Очищенная строка длиной не более MAX_SCHEDULE_LOG_LENGTH.
    """
    sanitized = re.sub(r"[\n\r\t\u2028\u2029]", "", schedule)
    if len(sanitized) > MAX_SCHEDULE_LOG_LENGTH:
        return sanitized[:MAX_SCHEDULE_LOG_LENGTH]
    return sanitized



def calculate_simple(schedule: str) -> datetime:
    """
    Рассчитать следующее время запуска для формата HH:MM.

    Args:
        schedule: Строка в формате "HH:MM" (например, "09:00", "23:30").

    Returns:
        Следующее время запуска в UTC.

    Логика:
        - Если указанное время ещё не наступило сегодня → сегодня
        - Если уже прошло → завтра
    """
    now_utc = datetime.now(timezone.utc)

    try:
        parts = schedule.split(":")
        if len(parts) != 2:
            raise InvalidScheduleError(
                f"Некорректный формат времени: {schedule}",
            )

        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except ValueError as exc:
            raise InvalidScheduleError(
                f"Некорректный формат времени: {schedule}",
            ) from exc

        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise InvalidScheduleError(
                f"Некорректное время: {hour}:{minute}",
            )

    except InvalidScheduleError:
        logger.error("Ошибка парсинга расписания %s", sanitize_for_log(schedule))
        raise

    next_run = now_utc.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if next_run <= now_utc:
        next_run += timedelta(days=1)

    logger.debug("Расчёт простого расписания %s: следующее время %s", sanitize_for_log(schedule), next_run)

    return next_run


def calculate_simple_cron(schedule: str) -> datetime:
    """
    Рассчитать следующее время запуска для простого cron-подобного формата.

    Args:
        schedule: Строка в формате:
            - "*/N" — каждые N минут
            - "H */N" — каждые N часов в минуту H
            - "H H * * D" — cron (минута, час, день, месяц, день недели)

    Returns:
        Следующее время запуска в UTC.

    Поддерживаемые форматы:
        1. "*/30" — каждые 30 минут
        2. "0 */2" — каждые 2 часа в 0 минут
        3. "30 9 * * 1" — каждый понедельник в 09:30
        4. "0 9 * * 1-5" — каждый будний день в 09:00
    """
    now_utc = datetime.now(timezone.utc)
    parts = schedule.split()

    if len(parts) == 1 and parts[0].startswith("*/"):
        return _calculate_interval_minutes(parts[0], now_utc)

    if len(parts) == 2 and parts[1].startswith("*/"):
        return _calculate_interval_hours(parts[0], parts[1], now_utc)

    if len(parts) >= 2:
        return _calculate_cron_like(parts, now_utc)

    raise InvalidScheduleError(
        f"Неподдерживаемый формат расписания: {sanitize_for_log(schedule)}",
    )


def _calculate_interval_minutes(interval_str: str, now: datetime) -> datetime:
    """
    Рассчитать следующее время для интервала в минутах (*/N).

    Args:
        interval_str: Строка вида "*/30".
        now: Текущее время в UTC.

    Returns:
        Следующее время запуска.
    """
    try:
        interval = int(interval_str[2:])
        if interval <= 0 or interval > 60:
            raise InvalidScheduleError(
                f"Интервал должен быть 1-60 минут: {interval_str}",
            )
    except ValueError as exc:
        logger.error("Ошибка парсинга интервала %s", sanitize_for_log(interval_str))
        raise InvalidScheduleError(
            f"Некорректный интервал: {interval_str}",
        ) from exc
    except InvalidScheduleError:
        logger.error("Ошибка парсинга интервала %s", sanitize_for_log(interval_str))
        raise

    current_minute = now.minute
    next_minute = ((current_minute // interval) + 1) * interval

    if next_minute >= 60:
        next_run = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    else:
        next_run = now.replace(minute=next_minute, second=0, microsecond=0)

    logger.debug("Расчёт интервала минут %s: следующее время %s", sanitize_for_log(interval_str), next_run)

    return next_run


def _calculate_interval_hours(
    minute_str: str, hour_str: str, now: datetime
) -> datetime:
    """
    Рассчитать следующее время для интервала в часах (H */N).

    Args:
        minute_str: Минута запуска (0-59).
        hour_str: Строка вида "*/2" для интервала часов.
        now: Текущее время в UTC.

    Returns:
        Следующее время запуска.
    """
    try:
        minute = int(minute_str)
        if not (0 <= minute <= 59):
            raise InvalidScheduleError(
                f"Минута должна быть 0-59: {minute_str}",
            )

        interval = int(hour_str[2:])
        if interval <= 0 or interval > 24:
            raise InvalidScheduleError(
                f"Интервал должен быть 1-24 часа: {hour_str}",
            )

    except ValueError as exc:
        logger.error(
            "Ошибка парсинга интервала часов %s",
            sanitize_for_log(f"{minute_str} {hour_str}"),
        )
        raise InvalidScheduleError(
            f"Некорректный интервал часов: {minute_str} {hour_str}",
        ) from exc
    except InvalidScheduleError:
        logger.error(
            "Ошибка парсинга интервала часов %s",
            sanitize_for_log(f"{minute_str} {hour_str}"),
        )
        raise

    current_hour = now.hour
    next_hour = ((current_hour // interval) + 1) * interval

    if next_hour >= 24:
        next_run = (
            now.replace(hour=0, minute=minute, second=0, microsecond=0)
            + timedelta(days=1)
        )
    else:
        next_run = now.replace(hour=next_hour, minute=minute, second=0, microsecond=0)

    if next_run <= now:
        next_run += timedelta(hours=interval)

    logger.debug(
        "Расчёт интервала часов %s %s: следующее время %s",
        sanitize_for_log(minute_str),
        sanitize_for_log(hour_str),
        next_run,
    )

    return next_run


def _calculate_cron_like(parts: list[str], now: datetime) -> datetime:
    """
    Рассчитать следующее время для cron-подобного формата.

    Args:
        parts: Части cron выражения [минута, час, день, месяц, день_недели].
        now: Текущее время в UTC.

    Returns:
        Следующее время запуска.

    Формат:
        - minute: 0-59 или */N
        - hour: 0-23 или */N
        - day: 1-31 или *
        - month: 1-12 или *
        - day_of_week: 0-6 (0=воскресенье) или 1-7 (1=понедельник), диапазон 1-5
    """
    minute_str = parts[0]
    hour_str = parts[1]
    day_str = parts[2] if len(parts) > 2 else "*"
    month_str = parts[3] if len(parts) > 3 else "*"
    dow_str = parts[4] if len(parts) > 4 else "*"

    minute = _parse_cron_field(minute_str, 0, 59)
    hour = _parse_cron_field(hour_str, 0, 23)
    day = _parse_cron_field(day_str, 1, 31) if day_str != "*" else None
    month = _parse_cron_field(month_str, 1, 12) if month_str != "*" else None
    dow = _parse_cron_field(dow_str, 0, 6) if dow_str != "*" else None

    next_run = now.replace(second=0, microsecond=0) + timedelta(minutes=1)

    start_time = datetime.now(timezone.utc)

    for _ in range(MAX_CRON_ITERATIONS):
        if (datetime.now(timezone.utc) - start_time).total_seconds() > CRON_CALCULATION_TIMEOUT:
            raise CronParseError(
                "Cron calculation timeout",
                cron_expression=" ".join(parts),
            )

        if month is not None and next_run.month not in month:
            next_run = _advance_month(next_run, month)
            continue

        if day is not None and next_run.day not in day:
            next_run = _advance_day(next_run)
            continue

        if dow is not None:
            dow_normalized = (next_run.weekday() + 1) % 7
            if dow_normalized not in dow:
                next_run = _advance_day(next_run)
                continue

        if next_run.hour not in hour:
            next_run = _advance_hour(next_run, hour)
            continue

        if next_run.minute not in minute:
            next_run = _advance_minute(next_run, minute)
            continue

        logger.debug("Расчёт cron %s: следующее время %s", sanitize_for_log(str(parts)), next_run)

        return next_run

    raise CronParseError(
        f"Не удалось рассчитать следующее время для расписания {sanitize_for_log(str(parts))}",
        cron_expression=sanitize_for_log(" ".join(parts)),
    )


def _parse_cron_field(field: str, min_val: int, max_val: int) -> list[int]:
    """
    Распарсить поле cron выражения.

    Args:
        field: Поле cron (например, "*/15", "1-5", "1,3,5").
        min_val: Минимальное значение.
        max_val: Максимальное значение.

    Returns:
        Список допустимых значений.
    """
    if field == "*":
        return list(range(min_val, max_val + 1))

    if field.startswith("*/"):
        try:
            step = int(field[2:])
            if step <= 0:
                raise InvalidScheduleError(
                    f"Шаг должен быть положительным: {field}",
                )
            return list(range(min_val, max_val + 1, step))
        except ValueError as exc:
            logger.error("Ошибка парсинга шага %s", sanitize_for_log(field))
            raise InvalidScheduleError(
                f"Некорректный шаг: {field}",
            ) from exc
        except InvalidScheduleError:
            logger.error("Ошибка парсинга шага %s", sanitize_for_log(field))
            raise

    values: set[int] = set()

    for part in field.split(","):
        if "-" in part:
            try:
                start, end = part.split("-")
                start_int = int(start)
                end_int = int(end)
                if start_int > end_int:
                    raise InvalidScheduleError(
                        f"Некорректный диапазон: {part}",
                    )
                values.update(range(start_int, end_int + 1))
            except ValueError as exc:
                logger.error("Ошибка парсинга диапазона %s", sanitize_for_log(part))
                raise InvalidScheduleError(
                    f"Ошибка парсинга диапазона {part}",
                ) from exc
            except InvalidScheduleError:
                logger.error("Ошибка парсинга диапазона %s", sanitize_for_log(part))
                raise
        else:
            try:
                values.add(int(part))
            except ValueError as exc:
                raise InvalidScheduleError(
                    f"Ошибка парсинга значения {part}",
                ) from exc

    result = sorted(v for v in values if min_val <= v <= max_val)

    if not result:
        raise InvalidScheduleError(
            f"Нет допустимых значений в диапазоне {min_val}-{max_val}: {sanitize_for_log(field)}",
        )

    return result


def _advance_month(dt: datetime, valid_months: list[int]) -> datetime:
    """Перейти к первому дню следующего допустимого месяца."""
    current_month = dt.month

    for month in sorted(valid_months):
        if month > current_month:
            return dt.replace(month=month, day=1, hour=0, minute=0)

    return dt.replace(
        year=dt.year + 1, month=min(valid_months), day=1, hour=0, minute=0
    )


def _advance_day(dt: datetime) -> datetime:
    """Перейти к следующему дню."""
    return dt.replace(hour=0, minute=0) + timedelta(days=1)


def _advance_hour(dt: datetime, valid_hours: list[int]) -> datetime:
    """Перейти к следующему допустимому часу."""
    current_hour = dt.hour

    for hour in sorted(valid_hours):
        if hour > current_hour:
            return dt.replace(hour=hour, minute=0)

    return dt.replace(hour=0, minute=0) + timedelta(days=1)


def _advance_minute(dt: datetime, valid_minutes: list[int]) -> datetime:
    """Перейти к следующей допустимой минуте."""
    current_minute = dt.minute

    for minute in sorted(valid_minutes):
        if minute > current_minute:
            return dt.replace(minute=minute, second=0, microsecond=0)

    next_minute = min(valid_minutes)
    return dt.replace(minute=next_minute, second=0, microsecond=0) + timedelta(hours=1)
