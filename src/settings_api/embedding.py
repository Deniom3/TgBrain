"""
Embedding Providers API endpoints.
"""

import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.api.models import ErrorDetail, ErrorResponse

from ..settings.repositories.embedding_providers import EmbeddingProvidersRepository
from ..config import reload_settings
from ..config.masking import mask_api_key

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Settings/Embedding"])


class EmbeddingDimensionError(ValueError):
    """Ошибка при получении некорректной размерности эмбеддинга от провайдера."""
    pass


class EmbeddingProviderRequest(BaseModel):
    """Запрос на обновление настроек провайдера эмбеддингов."""
    is_active: bool = Field(default=False)
    api_key: str | None = Field(default=None)
    base_url: str
    model: str
    is_enabled: bool = Field(default=True)
    priority: int = Field(default=0, ge=0)
    description: str | None = Field(default=None)
    embedding_dim: int = Field(default=768, ge=1)
    max_retries: int = Field(default=3, ge=1)
    timeout: int = Field(default=30, ge=1)
    normalize: bool = Field(default=False)


class EmbeddingProviderResponse(BaseModel):
    """Ответ с настройками провайдера эмбеддингов."""
    id: int | None
    name: str
    is_active: bool
    api_key_masked: str | None = None
    base_url: str
    model: str
    is_enabled: bool
    priority: int
    description: str | None
    embedding_dim: int
    max_retries: int
    timeout: int
    normalize: bool
    updated_at: str | None
    is_working: bool | None = None


class ProviderHealthResponse(BaseModel):
    """Ответ проверки провайдера."""
    name: str
    is_available: bool
    error: str | None = None
    response_time_ms: float | None = None
    model: str | None = None


class ModelUpdateRequest(BaseModel):
    """Запрос на обновление модели эмбеддинга."""
    model: str = Field(..., description="Название модели")
    embedding_dim: int = Field(default=768, ge=1, description="Размерность вектора")


def _get_embedding_repo(request: Request) -> EmbeddingProvidersRepository:
    """Получить EmbeddingProvidersRepository из app.state."""
    repo = getattr(request.app.state, "embedding_providers_repo", None)
    if repo is None:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Embedding providers repository not initialized")
            ).model_dump(),
        )
    return repo


@router.get("/embedding", response_model=list[EmbeddingProviderResponse])
async def get_all_embedding_providers(request: Request) -> list[EmbeddingProviderResponse]:
    """Получить настройки всех провайдеров эмбеддингов."""
    repo = _get_embedding_repo(request)
    providers = await repo.get_all()

    return [
        EmbeddingProviderResponse(
            id=p.id,
            name=p.name,
            is_active=p.is_active,
            api_key_masked=mask_api_key(p.api_key),
            base_url=p.base_url,
            model=p.model,
            is_enabled=p.is_enabled,
            priority=p.priority,
            description=p.description,
            embedding_dim=p.embedding_dim,
            max_retries=p.max_retries,
            timeout=p.timeout,
            normalize=p.normalize,
            updated_at=p.updated_at.isoformat() if p.updated_at else None,
            is_working=None,
        )
        for p in providers
    ]


@router.get("/embedding/{provider_name}", response_model=EmbeddingProviderResponse)
async def get_embedding_provider(provider_name: str, request: Request) -> EmbeddingProviderResponse:
    """Получить настройки конкретного провайдера эмбеддингов."""
    repo = _get_embedding_repo(request)
    provider = await repo.get(provider_name)

    if not provider:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-103", message="Provider not found")
            ).model_dump(),
        )

    return EmbeddingProviderResponse(
        id=provider.id,
        name=provider.name,
        is_active=provider.is_active,
        api_key_masked=mask_api_key(provider.api_key),
        base_url=provider.base_url,
        model=provider.model,
        is_enabled=provider.is_enabled,
        priority=provider.priority,
        description=provider.description,
        embedding_dim=provider.embedding_dim,
        max_retries=provider.max_retries,
        timeout=provider.timeout,
        normalize=provider.normalize,
        updated_at=provider.updated_at.isoformat() if provider.updated_at else None,
        is_working=None,
    )


@router.put("/embedding/{provider_name}/model", response_model=dict[str, Any])
async def update_embedding_model(provider_name: str, request_data: ModelUpdateRequest, http_request: Request) -> dict[str, Any]:
    """Обновить модель эмбеддинга для провайдера."""
    repo = _get_embedding_repo(http_request)
    current = await repo.get(provider_name)
    if not current:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-103", message="Provider not found")
            ).model_dump(),
        )

    logger.info("Обновление модели для %s: %s", provider_name, request_data.model)

    old_model = current.model
    model_changed = request_data.model != old_model

    embedding_dim = request_data.embedding_dim
    if provider_name == "ollama":
        try:
            from ..embeddings.providers import OllamaEmbeddingProvider
            from ..config import settings

            emb_cfg = settings.embedding_config.ollama

            logger.info("Запрос размерности для модели %s...", request_data.model)

            temp_provider = OllamaEmbeddingProvider(
                base_url=emb_cfg.url,
                model=request_data.model,
                dimension=0
            )

            embedding_dim = await temp_provider.get_embedding_dimension(force=True)
            await temp_provider.close()

            if embedding_dim <= 0:
                raise EmbeddingDimensionError("Получена некорректная размерность")

            logger.info("Получена размерность: %s", embedding_dim)
        # PY-004: Fallback handler — catches EmbeddingDimensionError,
        # OllamaEmbeddingError, and network errors; falls back to request-provided dimension
        except Exception as e:
            logger.warning("Не удалось получить размерность, используем из запроса: %s", e)
            embedding_dim = request_data.embedding_dim if request_data.embedding_dim > 0 else 768

    provider = await repo.update(
        name=provider_name,
        is_active=current.is_active,
        api_key=current.api_key,
        base_url=current.base_url,
        model=request_data.model,
        is_enabled=current.is_enabled,
        priority=current.priority,
        description=current.description,
        embedding_dim=embedding_dim,
        max_retries=current.max_retries,
        timeout=current.timeout,
        normalize=current.normalize,
    )

    if not provider:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Ошибка сохранения настроек провайдера")
            ).model_dump(),
        )

    logger.info(
        "Модель провайдера %s обновлена: %s -> %s (dim=%s)",
        provider_name, old_model, request_data.model, embedding_dim,
    )

    await reload_settings()

    embeddings_client = None
    reindex_started = False

    try:
        from src.embeddings import EmbeddingsClient
        from src.config import settings as global_settings

        embeddings_client = http_request.app.state.embeddings

        if isinstance(embeddings_client, EmbeddingsClient):
            await embeddings_client.reload_provider(global_settings)
            logger.info(
                "EmbeddingsClient перезапущен. Модель: %s, dim=%s",
                embeddings_client.get_model_name(), embeddings_client.embedding_dim,
            )
        else:
            logger.warning("embeddings_client не является EmbeddingsClient")
    # PY-004: API boundary — broad except justified; logs warning and continues without failing the request
    except Exception as e:
        logger.warning("Не удалось перезагрузить EmbeddingsClient: %s", e)

    if model_changed and embeddings_client:
        try:
            from src.reindex import ReindexService, ReindexPriority

            reindex_settings_repo = http_request.app.state.reindex_settings_repo
            if reindex_settings_repo is not None:
                await reindex_settings_repo.update_last_reindex_model(None)
                logger.info("last_reindex_model сброшен для запуска переиндексации")

            reindex_service = http_request.app.state.reindex
            if isinstance(reindex_service, ReindexService):
                await reindex_service.load_settings()
                logger.info("Настройки reindex сервиса обновлены")

                task_id = reindex_service.schedule_reindex(
                    priority=ReindexPriority.HIGH,
                    batch_size=50,
                    delay=0.5
                )
                if task_id:
                    reindex_started = True
                    logger.info("Запущена переиндексация (Smart Trigger): %s", task_id)
                else:
                    logger.info("Переиндексация не запущена: модель не изменилась")
        # PY-004: API boundary — broad except justified; logs warning and continues without failing the request
        except Exception as e:
            logger.warning("Не удалось запустить переиндексацию: %s", e)
    elif not model_changed:
        logger.info("Модель не изменилась, переиндексация не требуется (Smart Trigger)")

    return {
        "status": "success",
        "message": f"Модель обновлена на {request_data.model}",
        "provider": provider_name,
        "old_model": old_model,
        "model": request_data.model,
        "embedding_dim": embedding_dim,
        "model_changed": model_changed,
        "reindex_started": reindex_started,
    }


@router.put("/embedding/{provider_name}", response_model=EmbeddingProviderResponse)
async def update_embedding_provider(provider_name: str, payload: EmbeddingProviderRequest, request: Request) -> EmbeddingProviderResponse:
    """Обновить настройки провайдера эмбеддинга."""
    repo = _get_embedding_repo(request)
    provider = await repo.update(
        name=provider_name,
        is_active=payload.is_active,
        api_key=payload.api_key,
        base_url=payload.base_url,
        model=payload.model,
        is_enabled=payload.is_enabled,
        priority=payload.priority,
        description=payload.description,
        embedding_dim=payload.embedding_dim,
        max_retries=payload.max_retries,
        timeout=payload.timeout,
        normalize=payload.normalize,
    )

    if not provider:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Failed to save provider settings")
            ).model_dump(),
        )

    logger.info(
        "Настройки провайдера эмбеддинга %s обновлены: active=%s",
        provider_name, payload.is_active,
    )

    await reload_settings()

    return EmbeddingProviderResponse(
        id=provider.id,
        name=provider.name,
        is_active=provider.is_active,
        api_key_masked=mask_api_key(provider.api_key),
        base_url=provider.base_url,
        model=provider.model,
        is_enabled=provider.is_enabled,
        priority=provider.priority,
        description=provider.description,
        embedding_dim=provider.embedding_dim,
        max_retries=provider.max_retries,
        timeout=provider.timeout,
        normalize=provider.normalize,
        updated_at=provider.updated_at.isoformat() if provider.updated_at else None,
        is_working=None,
    )


@router.post("/embedding/{provider_name}/activate", response_model=dict[str, str])
async def activate_embedding_provider(provider_name: str, request: Request) -> dict[str, str]:
    """Активировать провайдер эмбеддингов."""
    repo = _get_embedding_repo(request)
    success = await repo.set_active(provider_name)

    if not success:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Failed to activate provider")
            ).model_dump(),
        )

    await reload_settings()
    logger.info("Провайдер эмбеддинга %s активирован", provider_name)

    return {"status": "success", "active_provider": provider_name}


@router.post("/embedding/{provider_name}/refresh-dimension", response_model=dict[str, Any])
async def refresh_embedding_dimension(provider_name: str, request: Request) -> dict[str, Any]:
    """Принудительно обновить размерность эмбеддинга для модели."""
    from ..embeddings.providers import OllamaEmbeddingProvider
    from ..config import settings

    if provider_name != "ollama":
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-102", message="Обновление размерности поддерживается только для Ollama")
            ).model_dump(),
        )

    try:
        temp_provider = OllamaEmbeddingProvider(
            base_url=settings.embedding_config.ollama.url,
            model=settings.embedding_config.ollama.model,
            dimension=768
        )

        dimension = await temp_provider.get_embedding_dimension(force=True)
        await temp_provider.close()

        if not dimension or dimension <= 0:
            raise HTTPException(
                status_code=500,
                detail=ErrorResponse(
                    error=ErrorDetail(code="APP-101", message="Не удалось получить размерность от сервера")
                ).model_dump(),
            )

        repo = _get_embedding_repo(request)
        provider = await repo.get(provider_name)
        if provider:
            await repo.update(
                name=provider_name,
                is_active=provider.is_active,
                api_key=provider.api_key,
                base_url=provider.base_url,
                model=provider.model,
                is_enabled=provider.is_enabled,
                priority=provider.priority,
                description=provider.description,
                embedding_dim=dimension,
                max_retries=provider.max_retries,
                timeout=provider.timeout,
                normalize=provider.normalize,
            )
            settings = settings.model_copy(update={"ollama_embedding_dim": dimension})
            import src.config as config_module
            config_module.settings = settings

            logger.debug("Settings updated: ollama_embedding_dim changed to %s", dimension)

        logger.info(
            "Обновлена размерность для %s/%s: %s",
            provider_name, settings.embedding_config.ollama.model, dimension,
        )

        return {
            "status": "success",
            "provider": provider_name,
            "model": settings.embedding_config.ollama.model,
            "dimension": dimension,
            "message": f"Размерность обновлена: {dimension}",
        }

    except HTTPException:
        raise
    # PY-004: API boundary — broad except justified, logs error and returns 500
    except Exception as e:
        logger.error("Ошибка обновления размерности эмбеддинга: %s", type(e).__name__)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Internal server error")
            ).model_dump(),
        )


@router.post("/embedding/{provider_name}/check", response_model=ProviderHealthResponse)
async def check_embedding_provider_health(provider_name: str, request: Request) -> ProviderHealthResponse:
    """Проверить работоспособность провайдера эмбеддингов."""
    from ..embeddings import EmbeddingsClient
    from ..config import settings

    try:
        repo = _get_embedding_repo(request)
        provider = await repo.get(provider_name)
        model_name = provider.model if provider else None

        client = EmbeddingsClient(settings, provider_name=provider_name)
        await client.initialize_provider()

        start = time.time()
        is_available = await client.check_health()
        response_time = (time.time() - start) * 1000

        return ProviderHealthResponse(
            name=provider_name,
            is_available=is_available,
            error=None if is_available else "Provider not available",
            response_time_ms=response_time,
            model=model_name,
        )
    except HTTPException:
        raise
    # PY-004: API boundary — broad except justified, logs error and returns degraded response
    except Exception as e:
        logger.error("Embedding provider health check error: %s", type(e).__name__)
        return ProviderHealthResponse(
            name=provider_name,
            is_available=False,
            error="Internal server error",
            response_time_ms=None,
        )
