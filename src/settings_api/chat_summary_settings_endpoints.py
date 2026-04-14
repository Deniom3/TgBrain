"""
Summary Settings API endpoints.

Управление настройками генерации summary:
- Включение/отключение генерации
- Период сбора сообщений
- Расписание генерации
- Кастомный промпт
"""

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..api.models import ErrorDetail, ErrorResponse

from ..schedule.exceptions import ScheduleError
from ..schedule.helpers import calculate_next_run as calc_schedule_next_run
from ..schedule.helpers import sanitize_for_log
from ..settings import ChatSettingsRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Settings/Chats/Summary"])


def _convert_hhmm_to_utc(schedule: str, timezone_name: str) -> str:
    """Конвертировать локальное HH:MM в UTC.

    Args:
        schedule: Время в формате HH:MM.
        timezone_name: Название часового пояса.

    Returns:
        Время в формате HH:MM в UTC.

    Raises:
        HTTPException: При невалидном часовом поясе.
    """
    hour, minute = map(int, schedule.split(":"))

    try:
        local_tz = ZoneInfo(timezone_name)
    except (KeyError, ZoneInfoNotFoundError) as exc:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-001", message="Неверно задан timezone приложения")
            ).model_dump(),
        ) from exc

    now_local = datetime.now(local_tz)
    local_dt = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    utc_dt = local_dt.astimezone(timezone.utc)
    return utc_dt.strftime("%H:%M")


class SummaryToggleResponse(BaseModel):
    """Ответ на переключение summary."""

    chat_id: int
    summary_enabled: bool
    message: str


class SummaryPeriodRequest(BaseModel):
    """Запрос на установку периода."""

    minutes: int = Field(..., ge=5, le=10080)


class SummaryPeriodResponse(BaseModel):
    """Ответ с периодом."""

    chat_id: int
    period_minutes: int
    message: str


class SummaryScheduleRequest(BaseModel):
    """Запрос на установку расписания."""

    schedule: str = Field(
        ...,
        max_length=100,
        description="Расписание в формате HH:MM или cron",
    )


class SummaryScheduleResponse(BaseModel):
    """Ответ с расписанием."""

    chat_id: int
    schedule: Optional[str]
    schedule_utc: Optional[str] = None
    timezone: Optional[str] = None
    next_run: Optional[datetime]
    message: str


class SummaryPromptRequest(BaseModel):
    """Запрос на установку кастомного промпта."""

    prompt: str = Field(..., min_length=10, max_length=4000)


class SummaryPromptResponse(BaseModel):
    """Ответ с промптом."""

    chat_id: int
    prompt: Optional[str]
    message: str


async def get_chat_settings_repo(request: Request) -> ChatSettingsRepository:
    """Получить репозиторий настроек чатов из app.state."""
    repo = getattr(request.app.state, "chat_settings_repo", None)
    if repo is not None:
        return repo
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Пул подключений к БД не инициализирован")
            ).model_dump(),
        )
    return ChatSettingsRepository(pool)


@router.post(
    "/chats/{chat_id}/summary/enable",
    response_model=SummaryToggleResponse,
    summary="Включить генерацию summary",
)
async def enable_summary(
    chat_id: int,
    repo: ChatSettingsRepository = Depends(get_chat_settings_repo),
) -> SummaryToggleResponse:
    """Включить генерацию summary для чата."""
    setting = await repo.enable_summary(chat_id)
    if not setting:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-103", message="Chat not found")
            ).model_dump(),
        )

    return SummaryToggleResponse(
        chat_id=chat_id,
        summary_enabled=True,
        message="Генерация summary включена",
    )


@router.post(
    "/chats/{chat_id}/summary/disable",
    response_model=SummaryToggleResponse,
    summary="Отключить генерацию summary",
)
async def disable_summary(
    chat_id: int,
    repo: ChatSettingsRepository = Depends(get_chat_settings_repo),
) -> SummaryToggleResponse:
    """Отключить генерацию summary для чата."""
    setting = await repo.disable_summary(chat_id)
    if not setting:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-103", message="Chat not found")
            ).model_dump(),
        )

    return SummaryToggleResponse(
        chat_id=chat_id,
        summary_enabled=False,
        message="Генерация summary отключена",
    )


@router.post(
    "/chats/{chat_id}/summary/toggle",
    response_model=SummaryToggleResponse,
    summary="Переключить генерацию summary",
)
async def toggle_summary(
    chat_id: int,
    repo: ChatSettingsRepository = Depends(get_chat_settings_repo),
) -> SummaryToggleResponse:
    """Переключить статус генерации summary."""
    setting = await repo.toggle_summary(chat_id)
    if not setting:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-103", message="Chat not found")
            ).model_dump(),
        )

    return SummaryToggleResponse(
        chat_id=chat_id,
        summary_enabled=setting.summary_enabled,
        message=f"Генерация summary {'включена' if setting.summary_enabled else 'отключена'}",
    )


@router.put(
    "/chats/{chat_id}/summary/period",
    response_model=SummaryPeriodResponse,
    summary="Установить период summary",
)
async def set_summary_period(
    chat_id: int,
    request: SummaryPeriodRequest,
    repo: ChatSettingsRepository = Depends(get_chat_settings_repo),
) -> SummaryPeriodResponse:
    """Установить период сбора сообщений для summary."""
    setting = await repo.set_summary_period(chat_id, request.minutes)
    if not setting:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-103", message="Chat not found")
            ).model_dump(),
        )

    return SummaryPeriodResponse(
        chat_id=chat_id,
        period_minutes=request.minutes,
        message=f"Период summary установлен: {request.minutes} минут",
    )


@router.put(
    "/chats/{chat_id}/summary/schedule",
    response_model=SummaryScheduleResponse,
    summary="Установить расписание summary",
)
async def set_summary_schedule(
    chat_id: int,
    request: SummaryScheduleRequest,
    http_request: Request,
    repo: ChatSettingsRepository = Depends(get_chat_settings_repo),
) -> SummaryScheduleResponse:
    """Установить расписание генерации summary."""
    schedule = request.schedule.strip()

    if not (
        re.match(r"^\d{1,2}:\d{2}$", schedule)
        or re.match(r"^[\d\*\-\,\/\s]+$", schedule)
    ):
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-102", message="Неверный формат расписания. Используйте HH:MM или cron")
            ).model_dump(),
        )

    timezone_name = "Etc/UTC"
    if http_request is not None:
        timezone_name = getattr(http_request.app.state, "timezone", "Etc/UTC")

    schedule_to_store = schedule
    if re.match(r"^\d{1,2}:\d{2}$", schedule):
        schedule_to_store = _convert_hhmm_to_utc(schedule, timezone_name)

    try:
        calc_schedule_next_run(schedule_to_store)
    except ScheduleError as e:
        logger.warning(
            "Нераспознанное расписание для чата %s: %s (код: %s)",
            chat_id,
            e.message,
            e.code,
        )
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-102", message="Невалидное расписание")
            ).model_dump(),
        ) from e

    setting = await repo.set_summary_schedule(chat_id, schedule_to_store)
    if not setting:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-103", message="Chat not found")
            ).model_dump(),
        )

    next_run = calc_schedule_next_run(schedule_to_store)
    await repo.update_next_schedule_run(chat_id, next_run)

    logger.info(
        "Установлено расписание summary для чата %s: %s, next_run=%s",
        chat_id,
        sanitize_for_log(schedule_to_store),
        next_run,
    )

    return SummaryScheduleResponse(
        chat_id=chat_id,
        schedule=schedule_to_store,
        next_run=next_run,
        message=f"Расписание summary установлено: {schedule}",
    )


@router.get(
    "/chats/{chat_id}/summary/schedule",
    response_model=SummaryScheduleResponse,
    summary="Получить расписание summary",
)
async def get_summary_schedule(
    chat_id: int,
    http_request: Request,
    repo: ChatSettingsRepository = Depends(get_chat_settings_repo),
) -> SummaryScheduleResponse:
    """Получить расписание генерации summary."""
    settings = await repo.get_summary_settings(chat_id)
    if not settings:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-103", message="Chat not found")
            ).model_dump(),
        )

    schedule_utc = settings.get("summary_schedule")
    next_run_raw = settings.get("next_schedule_run")
    next_run = None

    if isinstance(next_run_raw, datetime):
        if next_run_raw.tzinfo is None:
            next_run = next_run_raw.replace(tzinfo=timezone.utc)
        else:
            next_run = next_run_raw

    timezone_name = getattr(http_request.app.state, "timezone", "Etc/UTC") or "Etc/UTC"

    local_schedule = schedule_utc
    if schedule_utc:
        try:
            local_tz = ZoneInfo(timezone_name)
            hour, minute = map(int, schedule_utc.split(":"))
            utc_dt = datetime.now(timezone.utc).replace(hour=hour, minute=minute, second=0, microsecond=0)
            local_dt = utc_dt.astimezone(local_tz)
            local_schedule = local_dt.strftime("%H:%M")
        except (KeyError, ZoneInfoNotFoundError, ValueError) as exc:
            logger.warning(
                "Ошибка конвертации расписания в локальный часовой пояс %s: %s",
                timezone_name,
                exc,
            )
            local_schedule = schedule_utc

    return SummaryScheduleResponse(
        chat_id=chat_id,
        schedule=local_schedule,
        schedule_utc=schedule_utc,
        timezone=timezone_name,
        next_run=next_run,
        message=f"Расписание summary: {schedule_utc or 'не установлено'}",
    )


@router.delete(
    "/chats/{chat_id}/summary/schedule",
    response_model=SummaryScheduleResponse,
    summary="Отключить расписание summary",
)
async def clear_summary_schedule(
    chat_id: int,
    repo: ChatSettingsRepository = Depends(get_chat_settings_repo),
) -> SummaryScheduleResponse:
    """Отключить расписание генерации summary."""
    setting = await repo.clear_summary_schedule(chat_id)
    if not setting:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-103", message="Chat not found")
            ).model_dump(),
        )

    logger.info("Расписание summary для чата %s отключено", chat_id)

    return SummaryScheduleResponse(
        chat_id=chat_id,
        schedule=None,
        next_run=None,
        message="Расписание summary отключено",
    )


@router.put(
    "/chats/{chat_id}/summary/prompt",
    response_model=SummaryPromptResponse,
    summary="Установить кастомный промпт",
)
async def set_custom_prompt(
    chat_id: int,
    request: SummaryPromptRequest,
    repo: ChatSettingsRepository = Depends(get_chat_settings_repo),
) -> SummaryPromptResponse:
    """Установить кастомный промпт для генерации summary."""
    setting = await repo.set_custom_prompt(chat_id, request.prompt)
    if not setting:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-103", message="Chat not found")
            ).model_dump(),
        )

    return SummaryPromptResponse(
        chat_id=chat_id,
        prompt=request.prompt,
        message="Кастомный промпт установлен",
    )


@router.get(
    "/chats/{chat_id}/summary/prompt",
    response_model=SummaryPromptResponse,
    summary="Получить кастомный промпт",
)
async def get_custom_prompt(
    chat_id: int,
    repo: ChatSettingsRepository = Depends(get_chat_settings_repo),
) -> SummaryPromptResponse:
    """Получить кастомный промпт для чата."""
    prompt = await repo.get_custom_prompt(chat_id)

    return SummaryPromptResponse(
        chat_id=chat_id,
        prompt=prompt,
        message="Кастомный промпт получен" if prompt else "Используется промпт по умолчанию",
    )


@router.delete(
    "/chats/{chat_id}/summary/prompt",
    response_model=SummaryPromptResponse,
    summary="Сбросить кастомный промпт",
)
async def clear_custom_prompt(
    chat_id: int,
    repo: ChatSettingsRepository = Depends(get_chat_settings_repo),
) -> SummaryPromptResponse:
    """Сбросить кастомный промпт на дефолтный."""
    setting = await repo.clear_custom_prompt(chat_id)
    if not setting:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-103", message="Chat not found")
            ).model_dump(),
        )

    return SummaryPromptResponse(
        chat_id=chat_id,
        prompt=None,
        message="Кастомный промпт сброшен",
    )


class SummaryCleanupResponse(BaseModel):
    """Ответ на запуск очистки summary."""
    message: str
    deleted_count: int


@router.post(
    "/chats/{chat_id}/summary/cleanup",
    response_model=SummaryCleanupResponse,
    summary="Запустить очистку summary задач чата",
)
async def cleanup_chat_summary(
    chat_id: int,
    request: Request,
    repo: ChatSettingsRepository = Depends(get_chat_settings_repo),
) -> SummaryCleanupResponse:
    """
    Запустить очистку summary задач для указанного чата.

    Удаляет старые pending, failed и completed summary задачи.
    """
    chat_settings = await repo.get(chat_id)
    if not chat_settings:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-103", message="Chat not found")
            ).model_dump(),
        )

    pool = request.app.state.db_pool

    async with pool.acquire() as conn:
        result = await conn.execute("""
            DELETE FROM chat_summaries
            WHERE chat_id = $1
              AND status IN ('pending', 'failed', 'completed')
        """, chat_id)

    deleted_count = int(result.split()[1]) if "DELETE" in result else 0

    logger.info("Очистка summary для чата %s: удалено %d задач", chat_id, deleted_count)

    return SummaryCleanupResponse(
        message=f"Очищено {deleted_count} summary задач для чата {chat_id}",
        deleted_count=deleted_count,
    )
