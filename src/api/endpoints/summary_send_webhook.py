"""
Summary Send Webhook API endpoint.

Endpoint:
- POST /api/v1/chats/{chat_id}/summary/send-webhook — отправить summary на webhook по запросу
"""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ...api.dependencies.auth import AuthenticatedUser, get_current_user
from ...api.dependencies.services import get_summary_webhook_service
from ...api.dependencies.rate_limiter import webhook_rate_limit
from ...protocols.isummary_webhook_service import ISummaryWebhookService
from ...domain.exceptions import (
    WebhookGenerationError,
    WebhookNotConfiguredError,
    WebhookNotFoundError,
)

router = APIRouter(tags=["Summary"], prefix="/api/v1/chats")

MAX_MESSAGES_FOR_SUMMARY = 100
CUSTOM_PROMPT_MAX_LENGTH = 4096


class SummarySendWebhookRequest(BaseModel):
    """Запрос на отправку summary."""

    period_minutes: int = Field(
        default=1440,
        ge=5,
        le=10080,
        description="Период сбора сообщений в минутах",
    )
    custom_prompt: Optional[str] = Field(
        default=None,
        description="Кастомный промпт для генерации",
        max_length=CUSTOM_PROMPT_MAX_LENGTH,
    )
    use_cache: bool = Field(default=True, description="Использовать кэш при наличии")


class SummarySendWebhookResponse(BaseModel):
    """Ответ на отправку summary."""

    success: bool
    chat_id: int
    summary_id: Optional[int] = None
    task_id: Optional[int] = None
    from_cache: bool
    status: Optional[str] = None
    webhook_sent: bool = False
    webhook_pending: bool = False
    message: str


@router.post(
    "/{chat_id}/summary/send-webhook",
    response_model=SummarySendWebhookResponse,
    summary="Отправить summary на webhook",
    responses={
        200: {"description": "Summary получено из кэша и отправлено"},
        202: {"description": "Summary генерируется, webhook будет отправлен позже"},
    },
)
async def send_summary_webhook(
    chat_id: int,
    request: SummarySendWebhookRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    _rate_limit: AuthenticatedUser = Depends(webhook_rate_limit),
    summary_webhook_service: ISummaryWebhookService = Depends(get_summary_webhook_service),
) -> SummarySendWebhookResponse:
    """
    Отправить summary чата на webhook URL.
    
    Используется кэширование для оптимизации.
    
    Error codes:
    - WHK-001 — Chat not found
    - WHK-006 — Webhook не настроен
    
    Returns:
        202 Accepted — если summary генерируется
        200 OK — если summary получено из кэша
    """
    try:
        result = await summary_webhook_service.generate_and_send_webhook(
            chat_id=chat_id,
            period_minutes=request.period_minutes,
            custom_prompt=request.custom_prompt,
            use_cache=request.use_cache,
        )
    except WebhookNotFoundError:
        return SummarySendWebhookResponse(
            success=False,
            chat_id=chat_id,
            from_cache=False,
            webhook_sent=False,
            webhook_pending=False,
            message=f"Чат {chat_id} не найден",
        )
    except WebhookNotConfiguredError:
        return SummarySendWebhookResponse(
            success=False,
            chat_id=chat_id,
            from_cache=False,
            webhook_sent=False,
            webhook_pending=False,
            message="Webhook не настроен для данного чата",
        )
    except WebhookGenerationError:
        return SummarySendWebhookResponse(
            success=False,
            chat_id=chat_id,
            from_cache=False,
            webhook_sent=False,
            webhook_pending=False,
            message="Ошибка генерации summary",
        )

    if result.from_cache and result.webhook_sent:
        return SummarySendWebhookResponse(
            success=True,
            chat_id=chat_id,
            summary_id=result.summary.id if result.summary.id else None,
            from_cache=True,
            webhook_sent=True,
            message="Summary отправлено на webhook (из кэша)",
        )
    elif result.webhook_pending and result.summary.id:
        return SummarySendWebhookResponse(
            success=True,
            chat_id=chat_id,
            task_id=result.summary.id,
            from_cache=False,
            webhook_pending=True,
            status="pending",
            message="Summary генерируется, webhook будет отправлен после завершения",
        )
    elif result.webhook_pending:
        return SummarySendWebhookResponse(
            success=True,
            chat_id=chat_id,
            from_cache=False,
            webhook_pending=True,
            status="pending",
            message="Summary генерируется, webhook будет отправлен после завершения",
        )
    else:
        return SummarySendWebhookResponse(
            success=True,
            chat_id=chat_id,
            summary_id=result.summary.id if result.summary.id else None,
            from_cache=result.from_cache,
            webhook_sent=False,
            message="Summary получено, webhook не отправлен",
        )
