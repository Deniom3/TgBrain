"""
Chat Summary API endpoints — генерация summary (async).

Endpoints:
- POST /api/v1/chats/{chat_id}/summary/generate — генерация для одного чата
- POST /api/v1/chats/summary/generate — генерация для всех чатов
"""

import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.dependencies.rate_limiter import AuthenticatedUser, summary_rate_limit
from src.api.dependencies.services import get_summary_usecase
from src.api.endpoints.chat_summary_models import (
    SummaryGenerateAllRequest,
    SummaryGenerateAllTasksResponse,
    SummaryGenerateRequest,
    SummaryGenerateTaskResponse,
    SummaryTaskItem,
)
from src.api.models import ErrorDetail, ErrorResponse
from src.application.usecases.generate_summary import (
    BULK_TASK_DELAY_SECONDS,
    GenerateSummaryUseCase,
    SummaryRequest,
)
from src.application.usecases.result import Failure, Success

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat Summary/Generate"])


# ==================== Async Summary Generation Endpoints ====================


@router.post(
    "/api/v1/chats/{chat_id}/summary/generate",
    response_model=SummaryGenerateTaskResponse,
    summary="Генерация summary для одного чата (асинхронно)",
)
async def generate_chat_summary_async(
    chat_id: int,
    request: SummaryGenerateRequest,
    _rate_limit: AuthenticatedUser = Depends(summary_rate_limit),
    usecase: GenerateSummaryUseCase = Depends(get_summary_usecase),
) -> SummaryGenerateTaskResponse:
    """
    Асинхронная генерация summary для конкретного чата.

    - Создаёт задачу в БД со статусом 'pending'
    - Запускает фоновую обработку через BackgroundTasks
    - Возвращает ID задачи для последующего опроса статуса
    - Проверяет кэш (если use_cache=True)
    """
    try:
        summary_request = SummaryRequest(
            chat_id=chat_id,
            period_start=request.period_start,
            period_end=request.period_end,
            period_minutes=request.period_minutes,
            custom_prompt=request.custom_prompt,
            max_messages=request.max_messages,
        )

        result = await usecase.get_or_create_task(summary_request)

        if isinstance(result, Failure):
            logger.error(
                "Ошибка создания задачи summary для чата %d: %s",
                chat_id,
                result.error,
            )
            raise HTTPException(
                status_code=500,
                detail=ErrorResponse(
                    error=ErrorDetail(code="APP-101", message="Internal server error")
                ).model_dump(),
            )

        task_result = result.unwrap("GenerateSummaryUseCase")

        if task_result.from_cache:
            return SummaryGenerateTaskResponse(
                task_id=task_result.task_id,
                status=task_result.status,
                from_cache=True,
                message="Summary получено из кэша",
                chat_id=chat_id,
            )
        elif not task_result.is_new:
            return SummaryGenerateTaskResponse(
                task_id=task_result.task_id,
                status=task_result.status,
                from_cache=False,
                message="Задача уже выполняется",
                chat_id=chat_id,
            )
        else:
            return SummaryGenerateTaskResponse(
                task_id=task_result.task_id,
                status=task_result.status,
                from_cache=False,
                message="Задача создана и обрабатывается в фоне",
                chat_id=chat_id,
            )

    except HTTPException:
        raise
    except Exception as e:
        # Граница API слоя: перехватываем все непредвиденные исключения,
        # логируем с полным стеком и возвращаем клиенту 500.
        # Конкретные бизнес-исключения должны быть обработаны выше.
        logger.error(
            "Ошибка создания задачи summary для чата %d: %s",
            chat_id,
            type(e).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Internal server error")
            ).model_dump(),
        )


@router.post(
    "/api/v1/chats/summary/generate",
    response_model=SummaryGenerateAllTasksResponse,
    summary="Генерация summary для всех чатов (асинхронно)",
)
async def generate_all_summaries_async(
    request: Request,
    body: SummaryGenerateAllRequest,
    _rate_limit: AuthenticatedUser = Depends(summary_rate_limit),
    usecase: GenerateSummaryUseCase = Depends(get_summary_usecase),
) -> SummaryGenerateAllTasksResponse:
    """
    Асинхронная генерация summary для всех или указанных чатов.

    - Если chat_ids не указан — генерирует для всех включённых чатов
    - period_minutes переопределяет настройки каждого чата
    - Создаёт отдельные задачи для каждого чата
    - Возвращает список ID задач для опроса статуса
    """
    client_ip = request.client.host if request.client else "unknown"
    user_agent = re.sub(r'[\r\n\x00-\x1f]', '', request.headers.get("user-agent", "unknown"))
    logger.info("Массовая генерация summary: IP=%s, UA=%s", client_ip, user_agent)

    try:
        chat_ids: list[int]
        if body.chat_ids:
            chat_ids = body.chat_ids
        else:
            chat_ids = await _get_enabled_chat_ids(usecase)

        if not chat_ids:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error=ErrorDetail(code="APP-102", message="Нет чатов для генерации summary")
                ).model_dump(),
            )

        logger.info("Массовая генерация summary для %d чатов", len(chat_ids))

        tasks: list[SummaryTaskItem] = []
        for chat_id in chat_ids:
            try:
                summary_request = SummaryRequest(
                    chat_id=chat_id,
                    period_start=None,
                    period_end=None,
                    period_minutes=body.period_minutes,
                    custom_prompt=body.custom_prompt,
                    max_messages=body.max_messages,
                )

                result = await usecase.get_or_create_task(
                    summary_request,
                    creation_delay_seconds=BULK_TASK_DELAY_SECONDS,
                )

                if isinstance(result, Success):
                    task_result = result.value
                    tasks.append(SummaryTaskItem(
                        chat_id=chat_id,
                        task_id=task_result.task_id,
                        status=task_result.status,
                    ))
                    if task_result.is_new:
                        logger.info("Создана задача для чата %d, ID: %d", chat_id, task_result.task_id)
                    else:
                        logger.info("Найдена существующая задача для чата %d, ID: %d", chat_id, task_result.task_id)
                else:
                    logger.error("Ошибка создания задачи для чата %d", chat_id)
                    tasks.append(SummaryTaskItem(
                        chat_id=chat_id,
                        task_id=None,
                        status="error",
                    ))

            except Exception:
                # Boundary: API layer catch-all for individual chat processing
                logger.error(
                    "Ошибка создания задачи для чата %d",
                    chat_id,
                )
                tasks.append(SummaryTaskItem(
                    chat_id=chat_id,
                    task_id=None,
                    status="error",
                ))

        created_count = len([t for t in tasks if t.status == "pending"])

        return SummaryGenerateAllTasksResponse(
            tasks=tasks,
            total_chats=len(chat_ids),
            message=f"Создано {created_count} задач",
            created_at=datetime.now(timezone.utc),
        )

    except HTTPException:
        raise
    except Exception as e:
        # Граница API слоя: перехватываем все непредвиденные исключения,
        # логируем с полным стеком и возвращаем клиенту 500.
        # Конкретные бизнес-исключения должны быть обработаны выше.
        logger.error(
            "Ошибка массовой генерации summary: %s",
            type(e).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Internal server error")
            ).model_dump(),
        )


async def _get_enabled_chat_ids(usecase: GenerateSummaryUseCase) -> list[int]:
    """Получить ID чатов с включённой генерацией summary."""
    return await usecase.get_enabled_chat_ids()


__all__ = ["router"]
