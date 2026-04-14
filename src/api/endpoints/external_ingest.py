"""
REST endpoint для приёма внешних сообщений.

POST /api/v1/messages/ingest
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from starlette.requests import Request

from src.api.endpoints.external_ingest_models import (
    ExternalMessageRequest,
    ExternalMessageResponse,
    ExternalMessageStatus,
)
from src.api.error_codes import APP_ERROR_CODES, EXTERNAL_INGEST_ERROR_CODES
from src.api.models import ErrorDetail, ErrorResponse
from src.domain.exceptions import ValidationError
from src.rate_limiter import RequestPriority, TelegramRateLimiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["External Ingestion"])


async def get_rate_limiter(request: Request) -> TelegramRateLimiter:
    """Получение RateLimiter из app.state."""
    limiter = request.app.state.rate_limiter
    if limiter is None:
        ec = APP_ERROR_CODES["APP-106"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )
    return limiter


def _validate_request(request: ExternalMessageRequest) -> None:
    """
    Централизованная валидация запроса.

    Args:
        request: Запрос на внешнее сообщение.

    Raises:
        HTTPException: При невалидных данных (EXT-001).
        ValidationError: При ошибке валидации даты.
    """
    # Валидация даты (ISO 8601)
    try:
        datetime.fromisoformat(request.date.replace('Z', '+00:00'))
    except ValueError as e:
        raise ValidationError(
            f"Invalid date format: {e}",
            field="date"
        ) from e

    # Валидация: текст не должен быть пустым после trim
    if not request.text.strip():
        raise ValidationError("Text cannot be empty", field="text")


@router.post(
    "/messages/ingest",
    response_model=ExternalMessageResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Ошибка валидации"},
        401: {"model": ErrorResponse, "description": "Требуется авторизация"},
        500: {"model": ErrorResponse, "description": "Ошибка сервера"},
    },
    summary="Приём внешнего сообщения",
    description="POST endpoint для приёма сообщений от внешних источников (боты, вебхуки). Требуется авторизация.",
)
async def ingest_external_message(
    request: ExternalMessageRequest,
    http_request: Request,
    limiter: TelegramRateLimiter = Depends(get_rate_limiter),
) -> ExternalMessageResponse:
    """
    Приём сообщения от внешнего источника.

    Обрабатывает сообщение через стандартный pipeline:
    1. Валидация данных
    2. Проверка мониторинга чата (EXT-002 = 400 если не мониторится)
    3. Проверка дубликатов (перед векторизацией)
    4. Векторизация (если не дубликат)
    5. Сохранение в БД

    Args:
        request: Данные сообщения от внешнего источника.
        http_request: HTTP запрос для доступа к app.state.
        limiter: Rate limiter для контроля нагрузки.

    Returns:
        Response со статусом обработки.

    Raises:
        HTTPException: При валидации или если чат не мониторится.
    """
    logger.info(
        "External message ingestion: chat_id=%d, text_length=%d",
        request.chat_id, len(request.text)
    )

    # Централизованная валидация
    _validate_request(request)

    # Проверка rate limit
    await limiter.check_rate_limit(
        key=f"external_ingest:{request.chat_id}",
        priority=RequestPriority.LOW,
    )

    # Получение компонентов из app.state
    pool = http_request.app.state.db_pool
    embeddings = http_request.app.state.embeddings
    saver = http_request.app.state.message_saver

    if pool is None:
        ec = APP_ERROR_CODES["APP-106"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )

    if embeddings is None:
        ec = APP_ERROR_CODES["APP-106"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )

    if saver is None:
        ec = APP_ERROR_CODES["APP-106"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )

    # Создание ExternalMessageSaver
    from src.ingestion.external_saver import ExternalMessageSaver
    external_saver = ExternalMessageSaver(pool, saver)

    # Парсинг даты
    date = datetime.fromisoformat(request.date.replace('Z', '+00:00'))

    # Сохранение внешнего сообщения
    result = await external_saver.save_external_message(
        chat_id=request.chat_id,
        text=request.text,
        date=date,
        sender_id=request.sender_id,
        sender_name=request.sender_name,
        message_link=request.message_link,
        is_bot=request.is_bot,
        is_action=request.is_action,
    )

    # Обработка результата
    if result.status.status == "error":
        error_code = EXTERNAL_INGEST_ERROR_CODES["EXT-002"]
        raise HTTPException(
            status_code=error_code.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=error_code.code, message=error_code.message)
            ).model_dump(),
        )

    # Маппинг результата в response
    status_map = {
        "processed": ExternalMessageStatus.PROCESSED,
        "pending": ExternalMessageStatus.PENDING,
        "filtered": ExternalMessageStatus.FILTERED,
        "duplicate": ExternalMessageStatus.DUPLICATE,
        "updated": ExternalMessageStatus.UPDATED,
    }

    # Определение error_code для response
    resp_error_code: str | None = None
    if result.status.status == "filtered":
        resp_error_code = "EXT-005"
    elif result.status.status == "duplicate":
        resp_error_code = "EXT-006"
    elif result.status.status == "pending":
        if result.reason:
            if result.reason == "Embedding unavailable":
                resp_error_code = "EXT-007"
            elif result.reason == "Embedding error":
                resp_error_code = "EXT-003"
            elif result.reason == "Database error":
                resp_error_code = "EXT-004"

    return ExternalMessageResponse(
        success=result.success,
        status=status_map.get(result.status.status, ExternalMessageStatus.PENDING),
        message_id=result.message_id,
        chat_id=result.chat_id,
        filtered=result.status.filtered,
        pending=result.status.pending,
        duplicate=result.status.duplicate,
        updated=result.status.updated,
        reason=result.reason,
        error_code=resp_error_code,
    )
