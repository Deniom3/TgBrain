"""
API Endpoint: POST /api/v1/ask

Семантический поиск по базе знаний с генерацией ответа через LLM.

Поддерживает:
- Фильтрацию по конкретному чату (chat_id)
- Поиск по сообщениям, summary, или обоим источникам
- Автоматическое расширение контекста для коротких сообщений
- Группировку последовательных сообщений от одного пользователя
"""

import logging

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from starlette.requests import Request

from src.api.error_codes import APP_ERROR_CODES, RAG_ERROR_CODES
from src.api.models import (
    AskRequest,
    AskResponse,
    AskSource,
    ErrorDetail,
    ErrorResponse,
    ResponseMetadata,
    SearchSource,
)
from src.api.utils import sanitize_for_log
from src.application.exceptions import (
    ChatNotFoundError,
    DatabaseError,
    EmbeddingGenerationError,
    LLMGenerationError,
    NoResultsFoundError,
)
from src.application.usecases.ask_question import AskQuestionRequest, AskQuestionUseCase
from src.application.usecases.result import Failure
from src.embeddings.providers.base import EmbeddingProviderError
from src.providers import LocalLLMError
from src.rate_limiter import RequestPriority, TelegramRateLimiter

logger = logging.getLogger(__name__)

router = APIRouter()


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


def get_ask_usecase(request: Request) -> AskQuestionUseCase:
    """Получение AskQuestionUseCase из app.state."""
    usecase = request.app.state.ask_usecase
    if usecase is None:
        ec = APP_ERROR_CODES["APP-106"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )
    return usecase


@router.post(
    "/ask",
    response_model=AskResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Ошибка валидации"},
        404: {"model": ErrorResponse, "description": "Ничего не найдено"},
        500: {"model": ErrorResponse, "description": "Ошибка сервера"},
    },
    summary="RAG поиск по базе знаний",
    description="Семантический поиск по сообщениям и summary Telegram-чатов с генерацией ответа через LLM.",
    tags=["RAG Search"],
)
async def ask(
    request: AskRequest,
    usecase: AskQuestionUseCase = Depends(get_ask_usecase),
    limiter: TelegramRateLimiter = Depends(get_rate_limiter),
) -> AskResponse:
    """
    RAG поиск по базе знаний.

    Выполняет семантический поиск по сообщениям и/или summary
    с генерацией ответа через LLM.

    Поддерживает:
    - Фильтрацию по конкретному чату (chat_id)
    - Поиск по сообщениям, summary, или обоим источникам
    - Автоматическое расширение контекста для коротких сообщений
    - Группировку последовательных сообщений от одного пользователя
    """
    safe_question = sanitize_for_log(request.question)
    logger.info("POST /api/v1/ask: question=%s", safe_question)

    async def _execute_ask() -> AskResponse:
        usecase_request = AskQuestionRequest(
            question=request.question,
            chat_id=request.chat_id,
            search_in=request.search_in.value,
            expand_context=request.expand_context,
            top_k=request.top_k,
            context_window=request.context_window,
        )

        result = await usecase.execute(usecase_request)

        if isinstance(result, Failure):
            error = result.error
            if isinstance(error, ChatNotFoundError):
                error_code = RAG_ERROR_CODES["RAG-002"]
                raise HTTPException(
                    status_code=error_code.http_status,
                    detail=ErrorResponse(
                        error=ErrorDetail(code=error_code.code, message=error_code.message)
                    ).model_dump(),
                )
            if isinstance(error, NoResultsFoundError):
                error_code = RAG_ERROR_CODES["RAG-005"]
                raise HTTPException(
                    status_code=error_code.http_status,
                    detail=ErrorResponse(
                        error=ErrorDetail(code=error_code.code, message=error_code.message)
                    ).model_dump(),
                )
            if isinstance(error, EmbeddingGenerationError):
                error_code = RAG_ERROR_CODES["RAG-006"]
                raise HTTPException(
                    status_code=error_code.http_status,
                    detail=ErrorResponse(
                        error=ErrorDetail(code=error_code.code, message=error_code.message)
                    ).model_dump(),
                )
            if isinstance(error, LLMGenerationError):
                error_code = RAG_ERROR_CODES["RAG-007"]
                raise HTTPException(
                    status_code=error_code.http_status,
                    detail=ErrorResponse(
                        error=ErrorDetail(code=error_code.code, message=error_code.message)
                    ).model_dump(),
                )
            if isinstance(error, DatabaseError):
                error_code = RAG_ERROR_CODES["RAG-008"]
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

        value = result.unwrap("AskQuestionUseCase")
        sources = [
            AskSource(
                id=s["id"],
                type=s["type"],
                text=s["text"],
                date=s["date"],
                chat_title=s["chat_title"],
                link=s.get("link"),
                similarity_score=s["similarity_score"],
                is_expanded=s.get("is_expanded", False),
                grouped_count=s.get("grouped_count", 1),
            )
            for s in value.sources
        ]

        metadata = ResponseMetadata(
            search_source=SearchSource(value.search_source),
            total_found=value.total_found,
            context_expanded=value.context_expanded,
        )

        return AskResponse(
            answer=value.answer,
            sources=sources,
            query=value.query,
            metadata=metadata,
        )

    try:
        return await limiter.execute(RequestPriority.NORMAL, _execute_ask)
    except HTTPException:
        raise
    except EmbeddingProviderError as e:
        error_code = RAG_ERROR_CODES["RAG-006"]
        logger.error("Embedding generation failed: %s", type(e).__name__)
        raise HTTPException(
            status_code=error_code.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=error_code.code, message=error_code.message)
            ).model_dump(),
        )
    except LocalLLMError as e:
        error_code = RAG_ERROR_CODES["RAG-007"]
        logger.error("LLM generation failed: %s", type(e).__name__)
        raise HTTPException(
            status_code=error_code.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=error_code.code, message=error_code.message)
            ).model_dump(),
        )
    except asyncpg.PostgresError as e:
        error_code = RAG_ERROR_CODES["RAG-008"]
        logger.error("Database query failed: %s", type(e).__name__)
        raise HTTPException(
            status_code=error_code.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=error_code.code, message=error_code.message)
            ).model_dump(),
        )
    except Exception as e:
        logger.error("Ошибка /api/v1/ask: %s", e, exc_info=True)
        ec = APP_ERROR_CODES["APP-101"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )
