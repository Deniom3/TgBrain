"""
HTTP endpoints для пакетного импорта сообщений из Telegram Desktop.

Endpoints:
- POST /api/v1/messages/import — Загрузка файла или JSON
- GET /api/v1/messages/import/{task_id}/progress — Прогресс обработки
- DELETE /api/v1/messages/import/{task_id}/cancel — Отмена обработки
"""

import json
import logging
from datetime import datetime, UTC
from typing import NoReturn, Optional, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from src.api.dependencies.auth import AuthenticatedUser, get_current_user
from src.api.dependencies.rate_limiter import import_rate_limit
from src.api.endpoints.import_helpers import (
    get_import_usecase,
)
from src.api.endpoints.import_models import (
    CancelResponse,
    ImportErrorDetail,
    ImportErrorResponse,
    ImportResponse,
    ProgressResponse,
)
from src.api.error_codes import APP_ERROR_CODES, EXTERNAL_INGEST_ERROR_CODES
from src.api.models import ErrorDetail, ErrorResponse
from src.application.exceptions import (
    AccessDeniedError,
    FileTooLargeError,
    InvalidInputError,
    TaskNotFoundError,
    TooManyMessagesError,
)
from src.application.usecases.import_messages import (
    CancelResult,
    ImportRequest,
    ImportResult,
    ProgressData,
)
from src.application.usecases.result import Failure, Success

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/messages", tags=["Batch Import"])


@router.post(
    "/import",
    response_model=ImportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": ImportErrorResponse, "description": "Ошибка валидации"},
        401: {"model": ImportErrorResponse, "description": "Требуется авторизация"},
        403: {"model": ImportErrorResponse, "description": "Нет доступа к чату"},
        413: {"model": ImportErrorResponse, "description": "Файл слишком большой"},
        415: {"model": ImportErrorResponse, "description": "Неверный тип контента"},
        500: {"model": ImportErrorResponse, "description": "Ошибка сервера"},
    },
    summary="Пакетный импорт сообщений",
    description="Загрузка JSON файла экспорта Telegram Desktop или JSON напрямую + автоматический запуск обработки. Требуется авторизация.",
)
async def import_messages(
    request: Request,
    file: Optional[UploadFile] = File(None),
    chat_id: Optional[int] = Form(None),
    json_data: Optional[str] = Form(None),
    _rate_limit: AuthenticatedUser = Depends(import_rate_limit),
    _current_user: AuthenticatedUser = Depends(get_current_user),
) -> ImportResponse:
    """
    Загрузка файла импорта или JSON напрямую + автоматический запуск обработки.

    Поддерживает два формата:
    1. Multipart/form-data: файл + опциональный chat_id
    2. JSON напрямую: json_data + опциональный chat_id

    Args:
        request: HTTP запрос.
        file: JSON файл экспорта (до 500MB).
        chat_id: Переопределение chat_id (приоритет над файлом).
        json_data: JSON данные напрямую (до 1000 сообщений).

    Returns:
        ImportResponse с task_id и информацией о файле.

    Raises:
        HTTPException: При валидации или ошибках обработки.
    """
    safe_filename = str(file.filename)[:50].replace("\n", "").replace("\r", "") if file and file.filename else "unknown"
    logger.info(
        "Batch import started: file=%s, json_data=%s",
        safe_filename,
        json_data is not None,
    )

    usecase = get_import_usecase(request)

    file_content: bytes | None = None
    parsed_json_data: dict | None = None

    if file is not None:
        if json_data is not None:
            error_code = EXTERNAL_INGEST_ERROR_CODES["EXT-001"]
            raise HTTPException(
                status_code=error_code.http_status,
                detail=ErrorResponse(
                    error=ErrorDetail(code=error_code.code, message=error_code.message)
                ).model_dump(),
            )

        if not file.content_type or file.content_type not in (
            "application/json",
            "multipart/form-data",
        ):
            error_code = EXTERNAL_INGEST_ERROR_CODES["EXT-010"]
            raise HTTPException(
                status_code=error_code.http_status,
                detail=ErrorResponse(
                    error=ErrorDetail(code=error_code.code, message=error_code.message)
                ).model_dump(),
            )

        file_content = await file.read()

    elif json_data is not None:
        try:
            parsed_json_data = json.loads(json_data)
        except json.JSONDecodeError:
            error_code = EXTERNAL_INGEST_ERROR_CODES["EXT-001"]
            raise HTTPException(
                status_code=error_code.http_status,
                detail=ErrorResponse(
                    error=ErrorDetail(code=error_code.code, message=error_code.message)
                ).model_dump(),
            )

    file_id = str(uuid4())

    user_id = getattr(_current_user, "user_id", 0)

    import_request = ImportRequest(
        file_content=file_content,
        json_data=parsed_json_data,
        chat_id_override=chat_id,
        file_id=file_id,
        user_id=user_id,
    )

    result = await usecase.start_import(import_request)

    if isinstance(result, Failure):
        _map_failure_to_http(result.error)

    success_result = cast(Success[ImportResult, Exception], result)
    import_result = success_result.value

    return ImportResponse(
        success=True,
        task_id=import_result.task_id,
        file_id=import_result.file_id,
        file_size=import_result.file_size,
        messages_count=import_result.messages_count,
        estimated_chunks=import_result.estimated_chunks,
        chat_id_from_file=import_result.chat_id_from_file,
        chat_name_from_file=import_result.chat_name_from_file,
        status=import_result.status,
        created_at=datetime.now(UTC),
    )


@router.get(
    "/import/{task_id}/progress",
    response_model=ProgressResponse,
    responses={
        401: {"model": ImportErrorResponse, "description": "Требуется авторизация"},
        404: {"model": ImportErrorResponse, "description": "Задача не найдена"},
    },
    summary="Прогресс обработки импорта",
    description="Получение прогресса обработки импорта по task_id. Требуется авторизация.",
)
async def get_progress(
    task_id: str,
    request: Request,
    _rate_limit: AuthenticatedUser = Depends(import_rate_limit),
    _current_user: AuthenticatedUser = Depends(get_current_user),
) -> ProgressResponse:
    """
    Получение прогресса обработки импорта.

    Args:
        task_id: UUID задачи обработки.
        request: HTTP запрос.

    Returns:
        ProgressResponse со статистикой обработки.

    Raises:
        HTTPException: Если задача не найдена (EXT-013).
    """
    usecase = get_import_usecase(request)

    result = await usecase.get_progress(task_id)

    if isinstance(result, Failure):
        if isinstance(result.error, TaskNotFoundError):
            error_code = EXTERNAL_INGEST_ERROR_CODES["EXT-013"]
            raise HTTPException(
                status_code=error_code.http_status,
                detail=ErrorResponse(
                    error=ErrorDetail(code=error_code.code, message=error_code.message)
                ).model_dump(),
            )
        ec = APP_ERROR_CODES["APP-101"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )

    success_progress = cast(Success[ProgressData, Exception], result)
    progress = success_progress.value
    return _map_progress_to_response(progress)


@router.delete(
    "/import/{task_id}/cancel",
    response_model=CancelResponse,
    responses={
        401: {"model": ImportErrorResponse, "description": "Требуется авторизация"},
        404: {"model": ImportErrorResponse, "description": "Задача не найдена"},
    },
    summary="Отмена обработки импорта",
    description="Отмена обработки импорта по task_id. Требуется авторизация.",
)
async def cancel_import(
    task_id: str,
    request: Request,
    _rate_limit: AuthenticatedUser = Depends(import_rate_limit),
    _current_user: AuthenticatedUser = Depends(get_current_user),
) -> CancelResponse:
    """
    Отмена обработки импорта.

    Args:
        task_id: UUID задачи обработки.
        request: HTTP запрос.

    Returns:
        CancelResponse с результатом отмены.

    Raises:
        HTTPException: Если задача не найдена (EXT-013).
    """
    usecase = get_import_usecase(request)

    result = await usecase.cancel_import(task_id)

    if isinstance(result, Failure):
        if isinstance(result.error, TaskNotFoundError):
            error_code = EXTERNAL_INGEST_ERROR_CODES["EXT-013"]
            raise HTTPException(
                status_code=error_code.http_status,
                detail=ErrorResponse(
                    error=ErrorDetail(code=error_code.code, message=error_code.message)
                ).model_dump(),
            )
        ec = APP_ERROR_CODES["APP-101"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )

    success_cancel = cast(Success[CancelResult, Exception], result)
    cancel_result = success_cancel.value
    return _map_cancel_to_response(task_id, cancel_result)


def _map_failure_to_http(error: Exception) -> NoReturn:
    """Маппинг ошибок UseCase на HTTP-исключения."""
    if isinstance(error, InvalidInputError):
        error_code = EXTERNAL_INGEST_ERROR_CODES["EXT-001"]
        raise HTTPException(
            status_code=error_code.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=error_code.code, message=error_code.message)
            ).model_dump(),
        )
    if isinstance(error, FileTooLargeError):
        error_code = EXTERNAL_INGEST_ERROR_CODES["EXT-008"]
        raise HTTPException(
            status_code=error_code.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=error_code.code, message=error_code.message)
            ).model_dump(),
        )
    if isinstance(error, TooManyMessagesError):
        error_code = EXTERNAL_INGEST_ERROR_CODES["EXT-015"]
        raise HTTPException(
            status_code=error_code.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=error_code.code, message=error_code.message)
            ).model_dump(),
        )
    if isinstance(error, AccessDeniedError):
        error_code = EXTERNAL_INGEST_ERROR_CODES["EXT-014"]
        raise HTTPException(
            status_code=error_code.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=error_code.code, message=error_code.message)
            ).model_dump(),
        )
    error_code = EXTERNAL_INGEST_ERROR_CODES["EXT-004"]
    raise HTTPException(
        status_code=error_code.http_status,
        detail=ErrorResponse(
            error=ErrorDetail(code=error_code.code, message=error_code.message)
        ).model_dump(),
    )


def _map_progress_to_response(progress: ProgressData) -> ProgressResponse:
    """Маппинг ProgressData на ProgressResponse."""
    total = progress.total_messages or 1
    progress_percent = (progress.processed_messages / total) * 100 if total > 0 else 0

    error_details = []
    if progress.error_message:
        error_details.append(
            ImportErrorDetail(
                message_id=None,
                error_code="EXT-004",
                error_message=progress.error_message,
            )
        )

    return ProgressResponse(
        task_id=progress.task_id,
        status=progress.status,
        total_messages=progress.total_messages,
        processed_count=progress.processed_messages,
        progress_percent=progress_percent,
        processed=progress.processed_messages,
        filtered=progress.filtered,
        duplicates=progress.duplicates,
        pending=progress.pending,
        errors=progress.errors,
        current_chunk=progress.current_chunk,
        total_chunks=progress.total_chunks,
        started_at=progress.started_at.isoformat() if progress.started_at else None,
        estimated_completion=None,
        error_details=error_details,
    )


def _map_cancel_to_response(task_id: str, cancel_result: CancelResult) -> CancelResponse:
    """Маппинг CancelResult на CancelResponse."""
    return CancelResponse(
        success=cancel_result.cancelled,
        task_id=task_id,
        status="cancelled",
        processed_before_cancel=0,
        message="Import cancelled successfully" if cancel_result.cancelled else "Import already completed",
    )
