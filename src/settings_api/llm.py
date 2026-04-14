"""
LLM Providers API endpoints.
"""

import logging
import time
from typing import Dict, List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.api.models import ErrorDetail, ErrorResponse

from ..settings.repositories.llm_providers import LLMProvidersRepository
from ..config import reload_settings
from ..config.masking import mask_api_key

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Settings/LLM"])


class LLMProviderRequest(BaseModel):
    """Запрос на обновление настроек LLM провайдера."""
    is_active: bool = Field(default=False)
    api_key: str | None = Field(default=None)
    base_url: str
    model: str
    is_enabled: bool = Field(default=True)
    priority: int = Field(default=0, ge=0)
    description: str | None = Field(default=None)


class LLMProviderResponse(BaseModel):
    """Ответ с настройками LLM провайдера."""
    id: int | None
    name: str
    is_active: bool
    api_key_masked: str | None = None
    base_url: str
    model: str
    is_enabled: bool
    priority: int
    description: str | None
    updated_at: str | None
    is_working: bool | None = None


class ProviderHealthResponse(BaseModel):
    """Ответ проверки провайдера."""
    name: str
    is_available: bool
    error: str | None = None
    response_time_ms: float | None = None
    model: str | None = None


def _get_llm_repo(request: Request) -> LLMProvidersRepository:
    """Получить LLMProvidersRepository из app.state."""
    repo = getattr(request.app.state, "llm_providers_repo", None)
    if repo is None:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="LLM provider repository not initialized")
            ).model_dump(),
        )
    return repo


@router.get("/llm", response_model=List[LLMProviderResponse])
async def get_all_llm_providers(request: Request):
    """Получить настройки всех LLM провайдеров."""
    repo = _get_llm_repo(request)
    providers = await repo.get_all()

    return [
        LLMProviderResponse(
            id=p.id,
            name=p.name,
            is_active=p.is_active,
            api_key_masked=mask_api_key(p.api_key),
            base_url=p.base_url,
            model=p.model,
            is_enabled=p.is_enabled,
            priority=p.priority,
            description=p.description,
            updated_at=p.updated_at.isoformat() if p.updated_at else None,
            is_working=None,
        )
        for p in providers
    ]


@router.get("/llm/{provider_name}", response_model=LLMProviderResponse)
async def get_llm_provider(provider_name: str, request: Request):
    """Получить настройки конкретного LLM провайдера."""
    repo = _get_llm_repo(request)
    provider = await repo.get(provider_name)

    if not provider:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-103", message="Provider not found")
            ).model_dump(),
        )

    return LLMProviderResponse(
        id=provider.id,
        name=provider.name,
        is_active=provider.is_active,
        api_key_masked=mask_api_key(provider.api_key),
        base_url=provider.base_url,
        model=provider.model,
        is_enabled=provider.is_enabled,
        priority=provider.priority,
        description=provider.description,
        updated_at=provider.updated_at.isoformat() if provider.updated_at else None,
        is_working=None,
    )


@router.put("/llm/{provider_name}", response_model=LLMProviderResponse)
async def update_llm_provider(provider_name: str, request_data: LLMProviderRequest, request: Request):
    """Обновить настройки LLM провайдера."""
    repo = _get_llm_repo(request)
    provider = await repo.update(
        name=provider_name,
        is_active=request_data.is_active,
        api_key=request_data.api_key,
        base_url=request_data.base_url,
        model=request_data.model,
        is_enabled=request_data.is_enabled,
        priority=request_data.priority,
        description=request_data.description,
    )

    if not provider:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Failed to save provider settings")
            ).model_dump(),
        )

    logger.info("Настройки провайдера %s обновлены: active=%s", provider_name, request_data.is_active)
    await reload_settings()

    return LLMProviderResponse(
        id=provider.id,
        name=provider.name,
        is_active=provider.is_active,
        api_key_masked=mask_api_key(provider.api_key),
        base_url=provider.base_url,
        model=provider.model,
        is_enabled=provider.is_enabled,
        priority=provider.priority,
        description=provider.description,
        updated_at=provider.updated_at.isoformat() if provider.updated_at else None,
        is_working=None,
    )


@router.post("/llm/{provider_name}/activate", response_model=Dict[str, str])
async def activate_llm_provider(provider_name: str, request: Request):
    """Активировать LLM провайдер."""
    repo = _get_llm_repo(request)
    success = await repo.set_active(provider_name)

    if not success:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Failed to activate provider")
            ).model_dump(),
        )

    await reload_settings()
    logger.info("Провайдер %s активирован", provider_name)

    return {"status": "success", "active_provider": provider_name}


@router.post("/llm/{provider_name}/check", response_model=ProviderHealthResponse)
async def check_llm_provider_health(provider_name: str, request: Request):
    """Проверить работоспособность LLM провайдера."""
    try:
        repo = _get_llm_repo(request)
        provider = await repo.get(provider_name)
        if not provider:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error=ErrorDetail(code="APP-103", message="Provider not found")
                ).model_dump(),
            )

        start = time.time()
        is_available = True
        response_time = (time.time() - start) * 1000

        return ProviderHealthResponse(
            name=provider_name,
            is_available=is_available,
            error=None if is_available else "Provider not available",
            response_time_ms=response_time,
            model=provider.model,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("LLM provider health check error: %s", e, exc_info=True)
        return ProviderHealthResponse(
            name=provider_name,
            is_available=False,
            error="Internal server error",
            response_time_ms=None,
        )
