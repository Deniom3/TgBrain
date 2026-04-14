"""Protocol интерфейс для SummaryWebhookService."""

from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from src.infrastructure.services.summary_webhook_service import SummaryWebhookResult


class ISummaryWebhookService(Protocol):
    """Интерфейс сервиса отправки summary на webhook."""

    async def generate_and_send_webhook(
        self,
        chat_id: int,
        period_minutes: int,
        custom_prompt: str | None = None,
        use_cache: bool = True,
    ) -> "SummaryWebhookResult": ...
