"""
Endpoints для проверки здоровья API.

Endpoints:
- GET /health: Проверка здоровья всех компонентов
"""

import asyncio
import logging
import time

from fastapi import APIRouter, Request

from src.api.models import HealthResponse
from src.database import check_db_health
from src.domain.primitives.time import now, to_iso

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])

# Кэширование статуса health check
_health_cache: dict = {
    "llm_status": None,
    "llm_time": 0,
    "emb_status": None,
    "emb_time": 0,
    "ttl": 60  # Кэш на 60 секунд
}

_emb_lock: asyncio.Lock = asyncio.Lock()
_llm_lock: asyncio.Lock = asyncio.Lock()


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    """
    Проверка здоровья всех компонентов системы.

    Возвращает статус каждого компонента:
    - `ok` — компонент работает
    - `degraded` — компонент работает с ошибками
    - `error` — компонент не работает
    """
    app = request.app
    current_time = int(time.time())
    components = {}
    overall_status = "ok"

    # Database
    try:
        db_ok = await check_db_health()
        components["database"] = "ok" if db_ok else "error"
        if not db_ok:
            overall_status = "error"
    except OSError as e:
        components["database"] = "error"
        overall_status = "error"
        logger.error("Ошибка проверки БД (сеть/файловая система): %s", e)
    except TimeoutError as e:
        components["database"] = "error"
        overall_status = "error"
        logger.error("Таймаут проверки БД: %s", e)
    # API boundary: wide exception catch for health check resilience
    except Exception as e:
        components["database"] = "error"
        overall_status = "error"
        logger.error(
            "Неожиданная ошибка проверки БД [%s]: %s",
            type(e).__name__,
            e,
        )

    # Ollama Embeddings (с кэшированием)
    async with _emb_lock:
        if current_time - _health_cache["emb_time"] < _health_cache["ttl"]:
            emb_ok = _health_cache["emb_status"]
        else:
            emb_service = getattr(app.state, "embeddings", None)
            if emb_service is None:
                emb_ok = False
                logger.warning("Embeddings сервис не инициализирован")
            else:
                try:
                    emb_ok = await emb_service.check_health()
                    _health_cache["emb_status"] = emb_ok
                    _health_cache["emb_time"] = current_time
                except ConnectionError as e:
                    emb_ok = False
                    _health_cache["emb_status"] = False
                    _health_cache["emb_time"] = current_time
                    logger.error("Ошибка подключения к Embeddings: %s", e)
                except TimeoutError as e:
                    emb_ok = False
                    _health_cache["emb_status"] = False
                    _health_cache["emb_time"] = current_time
                    logger.error("Таймаут проверки Embeddings: %s", e)
                # API boundary: wide exception catch for health check resilience
                except Exception as e:
                    emb_ok = False
                    _health_cache["emb_status"] = False
                    _health_cache["emb_time"] = current_time
                    logger.error(
                        "Неожиданная ошибка проверки Embeddings [%s]: %s",
                        type(e).__name__,
                        e,
                    )
    components["ollama_embeddings"] = "ok" if emb_ok else "error"
    if not emb_ok and overall_status == "ok":
        overall_status = "degraded"

    # LLM (с кэшированием)
    async with _llm_lock:
        if current_time - _health_cache["llm_time"] < _health_cache["ttl"]:
            llm_ok = _health_cache["llm_status"]
        else:
            llm_service = getattr(app.state, "llm", None)
            if llm_service is None:
                llm_ok = False
                logger.warning("LLM сервис не инициализирован")
            else:
                try:
                    llm_ok = await llm_service.check_health()
                    _health_cache["llm_status"] = llm_ok
                    _health_cache["llm_time"] = current_time
                except ConnectionError as e:
                    llm_ok = False
                    _health_cache["llm_status"] = False
                    _health_cache["llm_time"] = current_time
                    logger.error("Ошибка подключения к LLM: %s", e)
                except TimeoutError as e:
                    llm_ok = False
                    _health_cache["llm_status"] = False
                    _health_cache["llm_time"] = current_time
                    logger.error("Таймаут проверки LLM: %s", e)
                # API boundary: wide exception catch for health check resilience
                except Exception as e:
                    llm_ok = False
                    _health_cache["llm_status"] = False
                    _health_cache["llm_time"] = current_time
                    logger.error(
                        "Неожиданная ошибка проверки LLM [%s]: %s",
                        type(e).__name__,
                        e,
                    )
    components["llm"] = "ok" if llm_ok else "error"
    if not llm_ok and overall_status == "ok":
        overall_status = "degraded"

    # Telegram
    try:
        telegram_configured = getattr(app.state, "telegram_configured", False)
        if not telegram_configured:
            components["telegram"] = "not_configured"
        elif hasattr(app.state, "ingester") and app.state.ingester is not None:
            ingester = app.state.ingester
            if hasattr(ingester, "is_connected"):
                tg_ok = ingester.is_connected()
                components["telegram"] = "ok" if tg_ok else "error"
            else:
                components["telegram"] = "error"
                logger.warning("Ingester не реализует is_connected()")
        else:
            components["telegram"] = "error"
        if components["telegram"] not in ("ok", "not_configured") and overall_status == "ok":
            overall_status = "degraded"
    except ConnectionError as e:
        components["telegram"] = "error"
        if overall_status == "ok":
            overall_status = "degraded"
        logger.error("Ошибка подключения к Telegram: %s", e)
    except TimeoutError as e:
        components["telegram"] = "error"
        if overall_status == "ok":
            overall_status = "degraded"
        logger.error("Таймаут проверки Telegram: %s", e)
    # API boundary: wide exception catch for health check resilience
    except Exception as e:
        components["telegram"] = "error"
        if overall_status == "ok":
            overall_status = "degraded"
        logger.error(
            "Неожиданная ошибка проверки Telegram [%s]: %s",
            type(e).__name__,
            e,
        )

    return HealthResponse(
        status=overall_status,
        components=components,
        timestamp=to_iso(now())
    )
