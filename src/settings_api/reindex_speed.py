"""
Reindex Speed API endpoint — управление скоростью реиндексации.

Endpoints:
- PATCH /api/v1/settings/reindex/speed — установка режима скорости
- GET /api/v1/settings/reindex/speed — получение текущего режима
"""

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api.models import ErrorDetail, ErrorResponse

from ..models.data_models import ReindexSettings
from ..reindex import ReindexService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/settings/reindex", tags=["Settings/Reindex"])

# ======================================================================
# Request/Response модели
# ======================================================================

class ReindexSpeedResponse(BaseModel):
    """Ответ с режимом скорости реиндексации."""
    speed_mode: str = Field(..., description="Текущий режим: low, medium, aggressive")
    batch_size: int = Field(..., description="Текущий размер пакета")
    delay_between_batches: float = Field(..., description="Текущая задержка между пакетами")
    description: str = Field(..., description="Описание режима")


class ReindexSpeedUpdateRequest(BaseModel):
    """Запрос на обновление режима скорости."""
    speed_mode: Literal["low", "medium", "aggressive"] = Field(
        ...,
        description="Режим скорости: low, medium, aggressive"
    )


# ======================================================================
# Конфигурация режимов
# ======================================================================

SPEED_MODES = {
    "low": {
        "batch_size": 20,
        "delay_between_batches": 3.0,
        "description": "Низкая скорость: 20 сообщений, задержка 3 сек (безопасный режим)"
    },
    "medium": {
        "batch_size": 50,
        "delay_between_batches": 1.0,
        "description": "Средняя скорость: 50 сообщений, задержка 1 сек (баланс)"
    },
    "aggressive": {
        "batch_size": 100,
        "delay_between_batches": 0.5,
        "description": "Агрессивный: 100 сообщений, задержка 0.5 сек (максимальная скорость)"
    }
}


def _get_reindex_service() -> ReindexService:
    """Получить сервис переиндексации из глобального состояния."""
    from ..settings_api.reindex import get_reindex_service
    return get_reindex_service()


# ======================================================================
# Endpoints
# ======================================================================

@router.get("/speed", response_model=ReindexSpeedResponse)
async def get_reindex_speed():
    """
    Получить текущий режим скорости реиндексации.

    Возвращает настройки скорости обработки сообщений.
    """
    try:
        service = _get_reindex_service()
        repo = service._reindex_settings_repo
        settings = await repo.get() or ReindexSettings()
        mode = SPEED_MODES.get(settings.speed_mode, SPEED_MODES["medium"])

        return ReindexSpeedResponse(
            speed_mode=settings.speed_mode,
            batch_size=settings.current_batch_size,
            delay_between_batches=settings.delay_between_batches,
            description=str(mode["description"]),
        )
    except Exception:
        logger.exception("Ошибка получения режима скорости")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Internal server error")
            ).model_dump(),
        )


@router.patch("/speed", response_model=ReindexSpeedResponse)
async def update_reindex_speed(request: ReindexSpeedUpdateRequest):
    """
    Обновить режим скорости реиндексации.

    Изменяет агрессивность сбора данных:
    - **low**: 20 сообщений, задержка 3 сек (безопасный режим)
    - **medium**: 50 сообщений, задержка 1 сек (баланс)
    - **aggressive**: 100 сообщений, задержка 0.5 сек (максимальная скорость)
    """
    try:
        service = _get_reindex_service()
        repo = service._reindex_settings_repo

        settings = await repo.get() or ReindexSettings()

        settings.speed_mode = request.speed_mode

        mode_config = SPEED_MODES.get(request.speed_mode, SPEED_MODES["medium"])
        settings.batch_size = int(mode_config["batch_size"])  # type: ignore
        settings.delay_between_batches = float(mode_config["delay_between_batches"])  # type: ignore
        settings.current_batch_size = int(mode_config["batch_size"])  # type: ignore

        updated = await repo.upsert(settings)

        return ReindexSpeedResponse(
            speed_mode=updated.speed_mode,
            batch_size=updated.current_batch_size,
            delay_between_batches=updated.delay_between_batches,
            description=str(mode_config["description"]),
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Ошибка обновления режима скорости")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Internal server error")
            ).model_dump(),
        )


__all__ = ["router"]
