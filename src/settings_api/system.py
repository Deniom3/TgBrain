"""
System API endpoints — Мониторинг нагрузки и статистика.

Endpoints:
- GET /api/v1/system/throughput — текущая нагрузка (запросы за минуту/час)
- GET /api/v1/system/stats — общая статистика системы
- GET /api/v1/system/flood-history — история инцидентов FloodWait
- GET /api/v1/system/request-history — история запросов
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.api.models import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/system", tags=["System"])


# ======================================================================
# Response модели
# ======================================================================

class ThroughputResponse(BaseModel):
    """Ответ со статистикой пропускной способности."""
    requests_per_minute: int = Field(..., description="Запросов за последнюю минуту")
    requests_per_hour: int = Field(..., description="Запросов за последний час")
    success_count: int = Field(..., description="Успешных запросов")
    error_count: int = Field(..., description="Ошибочных запросов")
    avg_execution_time_ms: float = Field(..., description="Среднее время выполнения (мс)")
    flood_wait_count: int = Field(..., description="Инцидентов FloodWait за час")


class SystemStatsResponse(BaseModel):
    """Ответ с общей статистикой системы."""
    total_requests: int = Field(..., description="Всего запросов")
    success_requests: int = Field(..., description="Успешных запросов")
    failed_requests: int = Field(..., description="Неудачных запросов")
    flood_wait_incidents: int = Field(..., description="Всего инцидентов FloodWait")
    current_batch_size: int = Field(..., description="Текущий размер пакета")
    is_throttled: bool = Field(..., description="Заблокирован ли из-за FloodWait")
    throttle_remaining_seconds: int = Field(..., description="Осталось секунд блокировки")


class FloodWaitIncidentItem(BaseModel):
    """Элемент истории инцидентов FloodWait."""
    id: int
    method_name: str
    chat_id: Optional[int]
    error_seconds: int
    actual_wait_seconds: int
    batch_size_before: Optional[int]
    batch_size_after: Optional[int]
    created_at: Optional[str]
    resolved_at: Optional[str]


class FloodWaitHistoryResponse(BaseModel):
    """История инцидентов FloodWait."""
    incidents: List[FloodWaitIncidentItem]
    total: int
    stats: dict


class RequestHistoryItem(BaseModel):
    """Элемент истории запросов."""
    id: int
    method_name: str
    chat_id: Optional[int]
    priority: int
    execution_time_ms: Optional[int]
    is_success: bool
    error_message: Optional[str]
    created_at: Optional[str]


class RequestHistoryResponse(BaseModel):
    """История запросов."""
    requests: List[RequestHistoryItem]
    total: int


# ======================================================================
# Endpoints
# ======================================================================

@router.get("/throughput", response_model=ThroughputResponse)
async def get_system_throughput(request: Request):
    """
    Получить текущую нагрузку системы.

    Возвращает статистику запросов к Telegram API за последнюю минуту и час.
    """
    try:
        # Получаем репозиторий из app.state
        request_stats_repo = request.app.state.request_stats_repo
        stats = await request_stats_repo.get_throughput(minutes=60)
        
        return ThroughputResponse(
            requests_per_minute=stats.requests_per_minute,
            requests_per_hour=stats.requests_per_hour,
            success_count=stats.success_count,
            error_count=stats.error_count,
            avg_execution_time_ms=stats.avg_execution_time_ms,
            flood_wait_count=stats.flood_wait_count,
        )
    except Exception:
        logger.exception("Ошибка получения статистики throughput")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Internal server error")
            ).model_dump(),
        )


@router.get("/stats", response_model=SystemStatsResponse)
async def get_system_stats(request: Request):
    """
    Получить общую статистику системы.

    Возвращает полную статистику работы Rate Limiter.
    """
    try:
        limiter = request.app.state.rate_limiter
        if limiter is None:
            raise HTTPException(
                status_code=503,
                detail=ErrorResponse(
                    error=ErrorDetail(code="APP-106", message="Rate limiter not initialized")
                ).model_dump(),
            )
        stats = limiter.get_system_stats()

        return SystemStatsResponse(
            total_requests=stats.total_requests,
            success_requests=stats.success_requests,
            failed_requests=stats.failed_requests,
            flood_wait_incidents=stats.flood_wait_incidents,
            current_batch_size=stats.current_batch_size,
            is_throttled=stats.is_throttled,
            throttle_remaining_seconds=stats.throttle_remaining_seconds,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Ошибка получения системной статистики")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Internal server error")
            ).model_dump(),
        )


@router.get("/flood-history", response_model=FloodWaitHistoryResponse)
async def get_flood_wait_history(
    request: Request,
    limit: int = 50,
    include_stats: bool = True
):
    """
    Получить историю инцидентов FloodWait.

    Возвращает последние инциденты ошибки 420.
    """
    try:
        # Получаем репозиторий из app.state
        flood_wait_repo = request.app.state.flood_wait_repo
        incidents = await flood_wait_repo.get_recent(limit=limit)
        
        stats = {}
        if include_stats:
            stats = await flood_wait_repo.get_stats(hours=24)
        
        return FloodWaitHistoryResponse(
            incidents=[
                FloodWaitIncidentItem(
                    id=incident.id or 0,
                    method_name=incident.method_name,
                    chat_id=incident.chat_id,
                    error_seconds=incident.error_seconds,
                    actual_wait_seconds=incident.actual_wait_seconds,
                    batch_size_before=incident.batch_size_before,
                    batch_size_after=incident.batch_size_after,
                    created_at=incident.created_at.isoformat() if incident.created_at else None,
                    resolved_at=incident.resolved_at.isoformat() if incident.resolved_at else None,
                )
                for incident in incidents if incident.id is not None
            ],
            total=len(incidents),
            stats=stats,
        )
    except Exception:
        logger.exception("Ошибка получения истории FloodWait")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Internal server error")
            ).model_dump(),
        )


@router.get("/request-history", response_model=RequestHistoryResponse)
async def get_request_history(request: Request, limit: int = 100):
    """
    Получить историю запросов к Telegram API.

    Возвращает последние выполненные запросы.
    """
    try:
        # Получаем репозиторий из app.state
        request_stats_repo = request.app.state.request_stats_repo
        requests = await request_stats_repo.get_recent(limit=limit)
        
        return RequestHistoryResponse(
            requests=[
                RequestHistoryItem(
                    id=req.id or 0,
                    method_name=req.method_name,
                    chat_id=req.chat_id,
                    priority=req.priority,
                    execution_time_ms=req.execution_time_ms,
                    is_success=req.is_success,
                    error_message=req.error_message,
                    created_at=req.created_at.isoformat() if req.created_at else None,
                )
                for req in requests if req.id is not None
            ],
            total=len(requests),
        )
    except Exception:
        logger.exception("Ошибка получения истории запросов")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Internal server error")
            ).model_dump(),
        )


__all__ = ["router"]
