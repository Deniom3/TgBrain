"""
Chat Summary API endpoints — получение данных (retrieval).

Endpoints:
- GET /api/v1/chats/{chat_id}/summary — список summary
- GET /api/v1/chats/{chat_id}/summary/latest — последнее summary
- GET /api/v1/chats/{chat_id}/summary/{summary_id} — статус задачи/summary
- DELETE /api/v1/chats/{chat_id}/summary/{summary_id} — удалить summary
- POST /api/v1/chats/{chat_id}/summary/cleanup — очистка старых
- GET /api/v1/chats/summary/stats — статистика
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies.services import get_summary_repo
from src.api.endpoints.chat_summary_models import (
    CleanupRequest,
    SummaryDetail,
    SummaryListItem,
    SummaryStats,
    SummaryStatusResponse,
)
from src.api.models import ErrorDetail, ErrorResponse
from src.api.protocols import SummaryRepoProtocol
from src.models.data_models import SummaryStatus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat Summary"])


# ==================== Summary Retrieval Endpoints ====================

@router.get(
    "/api/v1/chats/{chat_id}/summary",
    response_model=List[SummaryListItem],
    summary="Получить список summary для чата",
)
async def get_chat_summaries(
    chat_id: int,
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    summary_repo: SummaryRepoProtocol = Depends(get_summary_repo),
):
    """Получить список summary для чата с пагинацией."""
    try:
        summaries = await summary_repo.get_summaries_by_chat_with_pool(
            chat_id, limit, offset
        )
        return [
            SummaryListItem(
                id=s.id, chat_id=s.chat_id, created_at=s.created_at,
                period_start=s.period_start, period_end=s.period_end,
                messages_count=s.messages_count, generated_by=s.generated_by,
                status=s.status.value,
            )
            for s in summaries if s.id is not None and s.created_at is not None
        ]
    except HTTPException:
        raise
    except Exception:
        logger.error("Ошибка получения summary для чата %d", chat_id)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Internal server error")
            ).model_dump(),
        )


@router.get(
    "/api/v1/chats/{chat_id}/summary/latest",
    response_model=SummaryDetail,
    summary="Получить последнее summary для чата",
)
async def get_latest_summary(
    chat_id: int,
    summary_repo: SummaryRepoProtocol = Depends(get_summary_repo),
):
    """Получить последнее сгенерированное summary для чата."""
    try:
        summary = await summary_repo.get_latest_summary_with_pool(chat_id)
        if not summary or summary.id is None or summary.created_at is None:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error=ErrorDetail(code="APP-103", message="Summary not found")
                ).model_dump(),
            )
        return SummaryDetail(
            id=summary.id, chat_id=summary.chat_id, created_at=summary.created_at,
            period_start=summary.period_start, period_end=summary.period_end,
            result_text=summary.result_text, messages_count=summary.messages_count,
            generated_by=summary.generated_by, metadata=summary.metadata,
        )
    except HTTPException:
        raise
    except Exception:
        logger.error("Ошибка получения последнего summary для чата %d", chat_id)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Internal server error")
            ).model_dump(),
        )


@router.get(
    "/api/v1/chats/{chat_id}/summary/{summary_id}",
    response_model=SummaryStatusResponse,
    summary="Получить статус задачи/summary",
)
async def get_summary_or_task_status(
    chat_id: int,
    summary_id: int,
    summary_repo: SummaryRepoProtocol = Depends(get_summary_repo),
):
    """
    Получить статус задачи или готовое summary по ID.

    - Если status = completed → возвращает готовое summary
    - Если status = pending/processing → возвращает статус выполнения
    - Если status = failed → возвращает ошибку
    """
    try:
        task = await summary_repo.get_summary_task_with_pool(summary_id)

        if not task:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error=ErrorDetail(code="APP-103", message="Task not found")
                ).model_dump(),
            )

        if task.chat_id != chat_id:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error=ErrorDetail(code="APP-102", message="Task does not belong to specified chat")
                ).model_dump(),
            )

        if task.id is None or task.created_at is None:
            raise HTTPException(
                status_code=500,
                detail=ErrorResponse(
                    error=ErrorDetail(code="APP-101", message="Некорректные данные задачи")
                ).model_dump(),
            )

        response = SummaryStatusResponse(
            id=task.id,
            chat_id=task.chat_id,
            status=task.status.value,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

        if task.status == SummaryStatus.COMPLETED:
            response.result_text = task.result_text
            response.messages_count = task.messages_count
            response.period_start = task.period_start
            response.period_end = task.period_end
            response.generated_by = task.generated_by
            response.metadata = task.metadata
        elif task.status == SummaryStatus.FAILED:
            response.error_message = task.result_text
        elif task.status in [SummaryStatus.PENDING, SummaryStatus.PROCESSING]:
            response.progress_percent = 0.0 if task.status == SummaryStatus.PENDING else 50.0

        return response

    except HTTPException:
        raise
    except Exception:
        logger.error("Ошибка получения задачи %d", summary_id)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Internal server error")
            ).model_dump(),
        )


@router.delete(
    "/api/v1/chats/{chat_id}/summary/{summary_id}",
    summary="Удалить summary",
)
async def delete_summary(
    chat_id: int,
    summary_id: int,
    summary_repo: SummaryRepoProtocol = Depends(get_summary_repo),
):
    """Удалить summary по ID."""
    try:
        summary = await summary_repo.get_summary_by_id_with_pool(summary_id)
        if not summary:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error=ErrorDetail(code="APP-103", message="Summary not found")
                ).model_dump(),
            )
        if summary.chat_id != chat_id:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error=ErrorDetail(code="APP-102", message="Summary does not belong to specified chat")
                ).model_dump(),
            )
        success = await summary_repo.delete_summary_by_id_with_pool(summary_id)
        if not success:
            raise HTTPException(
                status_code=500,
                detail=ErrorResponse(
                    error=ErrorDetail(code="APP-101", message="Failed to delete summary")
                ).model_dump(),
            )
        return {"message": "Summary deleted successfully"}
    except HTTPException:
        raise
    except Exception:
        logger.error("Ошибка удаления summary %d", summary_id)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Internal server error")
            ).model_dump(),
        )


@router.post(
    "/api/v1/chats/{chat_id}/summary/cleanup",
    summary="Очистить старые summary",
)
async def cleanup_summaries(
    chat_id: int,
    request: CleanupRequest,
    summary_repo: SummaryRepoProtocol = Depends(get_summary_repo),
):
    """Очистить старые summary для чата."""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=request.older_than_days)
        deleted_count = await summary_repo.delete_old_summaries_with_pool(
            chat_id, cutoff
        )
        return {
            "message": f"Удалено {deleted_count} summary старше {request.older_than_days} дн.",
            "deleted_count": deleted_count,
        }
    except HTTPException:
        raise
    except Exception:
        logger.error("Ошибка очистки summary для чата %d", chat_id)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Internal server error")
            ).model_dump(),
        )


@router.get(
    "/api/v1/chats/summary/stats",
    response_model=List[SummaryStats],
    summary="Получить статистику по summary",
)
async def get_summaries_stats(
    summary_repo: SummaryRepoProtocol = Depends(get_summary_repo),
):
    """Получить статистику по всем чатам."""
    try:
        stats = await summary_repo.get_stats_with_pool()
        return [
            SummaryStats(
                chat_id=s["chat_id"], total_summaries=s["total_summaries"],
                first_summary=s["first_summary"], last_summary=s["last_summary"],
                avg_messages=s["avg_messages"],
            )
            for s in stats
        ]
    except HTTPException:
        raise
    except Exception:
        logger.error("Ошибка получения статистики summary")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Internal server error")
            ).model_dump(),
        )


__all__ = ["router"]
