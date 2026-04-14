"""
Webhook Service для отправки summary.

Асинхронная генерация и отправка webhook.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import asyncpg
import aiohttp

from ...config import Settings
from ...llm_client import LLMClient
from ...rag.search import RAGSearch
from ...embeddings import EmbeddingsClient
from ...webhook.webhook_service import WebhookService
from ...settings.repositories.chat_settings import ChatSettingsRepository
from ...settings.repositories.chat_summary.repository import ChatSummaryRepository
from ...models.data_models import ChatSummary, SummaryStatus
from ...application.usecases.generate_summary import GenerateSummaryUseCase, SummaryRequest
from ...application.usecases.result import Success
from ...domain.exceptions import (
    WebhookGenerationError,
    WebhookNotConfiguredError,
    WebhookNotFoundError,
)
from ...webhook.exceptions import WebhookError

logger = logging.getLogger(__name__)


class SummaryWebhookResult:
    """Результат операции отправки summary на webhook."""

    def __init__(
        self,
        summary: ChatSummary,
        from_cache: bool,
        webhook_sent: bool,
        webhook_pending: bool = False,
    ) -> None:
        self._summary = summary
        self._from_cache = from_cache
        self._webhook_sent = webhook_sent
        self._webhook_pending = webhook_pending

    @property
    def summary(self) -> ChatSummary:
        return self._summary

    @property
    def from_cache(self) -> bool:
        return self._from_cache

    @property
    def webhook_sent(self) -> bool:
        return self._webhook_sent

    @property
    def webhook_pending(self) -> bool:
        return self._webhook_pending


class SummaryWebhookService:
    """
    Infrastructure service for summary webhook orchestration.

    Coordinates summary generation and webhook delivery.
    """

    def __init__(
        self,
        config: Settings,
        rag_search: RAGSearch,
        llm_client: LLMClient,
        embeddings_client: EmbeddingsClient,
        db_pool: asyncpg.Pool,
        webhook_service: WebhookService,
        chat_settings_repo: ChatSettingsRepository,
        summary_usecase: Optional[GenerateSummaryUseCase] = None,
        summary_repo: Optional[ChatSummaryRepository] = None,
    ) -> None:
        """
        Initialize service.

        Args:
            config: Application settings.
            rag_search: RAG search component.
            llm_client: LLM client.
            embeddings_client: Embeddings service.
            db_pool: Database connection pool.
            webhook_service: Webhook delivery service.
            chat_settings_repo: Chat settings repository.
            summary_usecase: GenerateSummaryUseCase для создания задач.
            summary_repo: Chat summary repository (optional, uses class directly if None).
        """
        self._config = config
        self._rag_search = rag_search
        self._llm_client = llm_client
        self._embeddings_client = embeddings_client
        self._db_pool = db_pool
        self._webhook_service = webhook_service
        self._chat_settings_repo = chat_settings_repo
        self._summary_usecase: Optional[GenerateSummaryUseCase] = summary_usecase
        self._summary_repo = summary_repo

    @property
    def summary_usecase(self) -> Optional[GenerateSummaryUseCase]:
        """GenerateSummaryUseCase для создания задач."""
        return self._summary_usecase

    @summary_usecase.setter
    def summary_usecase(self, value: GenerateSummaryUseCase) -> None:
        """Установить GenerateSummaryUseCase."""
        self._summary_usecase = value

    def refresh_config(self, new_settings: Settings) -> None:
        """Обновить ссылку на Settings после reload.

        Args:
            new_settings: Новый экземпляр Settings.
        """
        self._config = new_settings
        logger.debug("SummaryWebhookService обновлён")

    async def generate_and_send_webhook(
        self,
        chat_id: int,
        period_minutes: int,
        custom_prompt: Optional[str] = None,
        use_cache: bool = True,
    ) -> SummaryWebhookResult:
        """
        Generate summary and send webhook.

        Args:
            chat_id: Chat identifier.
            period_minutes: Summary period in minutes.
            custom_prompt: Optional custom prompt.
            use_cache: Use cached summary if available.

        Returns:
            SummaryWebhookResult с информацией о результате.

        Raises:
            WebhookNotFoundError: WHK-001 если чат не найден.
            WebhookNotConfiguredError: WHK-006 если webhook не настроен.
            WebhookGenerationError: WHK-007 если ошибка генерации summary.
        """
        del use_cache

        setting = await self._chat_settings_repo.get(chat_id)
        if not setting:
            raise WebhookNotFoundError(chat_id)

        config = await self._chat_settings_repo.get_webhook_config_raw(chat_id)
        if not config or not setting.webhook_enabled:
            raise WebhookNotConfiguredError(chat_id)

        period_end = datetime.now(timezone.utc)
        period_start = period_end - timedelta(minutes=period_minutes)

        if self._summary_usecase is None:
            raise RuntimeError("GenerateSummaryUseCase не инициализирован")

        request = SummaryRequest(
            chat_id=chat_id,
            period_start=period_start,
            period_end=period_end,
            period_minutes=None,
            custom_prompt=custom_prompt,
            max_messages=100,
        )

        result = await self._summary_usecase.get_or_create_task(request)

        if not isinstance(result, Success):
            raise WebhookGenerationError()

        task_result = result.value

        if task_result.from_cache:
            if self._summary_repo is None:
                raise RuntimeError("Summary repository не инициализирован")
            async with self._db_pool.acquire() as conn:
                cached_summary = await self._summary_repo.get_summary_task(conn, task_result.task_id)

            if cached_summary and cached_summary.result_text:
                setting = await self._chat_settings_repo.get(chat_id)
                config = await self._chat_settings_repo.get_webhook_config_raw(chat_id)

                if config and setting and setting.webhook_enabled:
                    try:
                        webhook_sent = await self._webhook_service.send_summary_webhook(
                            webhook_config=config,
                            summary_text=cached_summary.result_text,
                            chat_id=chat_id,
                            chat_title=setting.title or str(chat_id),
                            period_start=period_start,
                            period_end=period_end,
                            messages_count=cached_summary.messages_count or 0,
                        )
                        return SummaryWebhookResult(
                            summary=cached_summary,
                            from_cache=True,
                            webhook_sent=webhook_sent,
                            webhook_pending=False,
                        )
                    except (ConnectionError, TimeoutError, aiohttp.ClientError) as e:
                        logger.error(
                            "Webhook network error для чата %d: %s",
                            chat_id,
                            e,
                            exc_info=True,
                        )
                        return SummaryWebhookResult(
                            summary=cached_summary,
                            from_cache=True,
                            webhook_sent=False,
                            webhook_pending=False,
                        )
                    except WebhookError as e:
                        logger.error(
                            "Webhook error для чата %d: %s (%s)",
                            chat_id,
                            e.message,
                            e.code,
                            exc_info=True,
                        )
                        return SummaryWebhookResult(
                            summary=cached_summary,
                            from_cache=True,
                            webhook_sent=False,
                            webhook_pending=False,
                        )

        fallback_summary = ChatSummary(
            id=task_result.task_id,
            chat_id=chat_id,
            status=SummaryStatus(task_result.status),
            created_at=datetime.now(timezone.utc),
            result_text="",
            period_start=period_start,
            period_end=period_end,
        )

        return SummaryWebhookResult(
            summary=fallback_summary,
            from_cache=task_result.from_cache,
            webhook_sent=False,
            webhook_pending=not task_result.from_cache,
        )

    async def send_webhook_for_summary(
        self,
        task_id: int,
        chat_id: int,
        config: dict,
    ) -> bool:
        """
        Send webhook for existing summary.

        Used as background task after summary generation completes.

        Args:
            task_id: Summary task identifier.
            chat_id: Chat identifier.
            config: Webhook configuration.

        Returns:
            True if webhook sent successfully.
        """
        if self._summary_repo is None:
            logger.warning("Summary repository not initialized — webhook delivery skipped")
            return False

        try:
            async with self._db_pool.acquire() as conn:
                summary = await self._summary_repo.get_summary_task(conn, task_id)

            if not summary:
                logger.error("Summary %d not found", task_id)
                return False

            if not summary.result_text:
                logger.warning(
                    "Summary %d has no result (status: %s)",
                    task_id,
                    summary.status,
                )
                return False

            setting = await self._chat_settings_repo.get(chat_id)

            success = await self._webhook_service.send_summary_webhook(
                webhook_config=config,
                summary_text=summary.result_text,
                chat_id=chat_id,
                chat_title=setting.title if setting and setting.title else str(chat_id),
                period_start=summary.period_start,
                period_end=summary.period_end,
                messages_count=summary.messages_count,
            )

            if success:
                logger.info("Webhook sent for summary %d", task_id)
            else:
                logger.warning("Webhook not sent for summary %d", task_id)

            return success

        except (asyncpg.PostgresError, asyncpg.InterfaceError) as e:
            logger.error(
                "Database error sending webhook for summary %d: %s",
                task_id,
                e,
                exc_info=True,
            )
            return False
        except (ConnectionError, TimeoutError, aiohttp.ClientError) as e:
            logger.error(
                "Network error sending webhook for summary %d: %s",
                task_id,
                e,
                exc_info=True,
            )
            return False
        except WebhookError as e:
            logger.error(
                "Webhook error sending webhook for summary %d: %s (%s)",
                task_id,
                e.message,
                e.code,
                exc_info=True,
            )
            return False

    async def send_webhook_after_generation(
        self,
        task_id: int,
        chat_id: int,
        config: dict,
    ) -> None:
        """
        Отправить webhook после генерации summary.

        Если summary ещё не completed, ждёт до 5 минут.

        Args:
            task_id: Summary task identifier.
            chat_id: Chat identifier.
            config: Webhook configuration.
        """
        if self._summary_repo is None:
            logger.warning("Summary repository not initialized — webhook delivery skipped")
            return

        # Ждём завершения задачи если она ещё pending/processing
        for attempt in range(30):  # максимум 5 минут (30 * 10s)
            try:
                async with self._db_pool.acquire() as conn:
                    summary = await self._summary_repo.get_summary_task(conn, task_id)

                if not summary:
                    logger.error("Summary %d not found", task_id)
                    return

                if summary.result_text:
                    # Summary готов — отправляем webhook
                    success = await self.send_webhook_for_summary(
                        task_id=task_id,
                        chat_id=chat_id,
                        config=config,
                    )

                    if success:
                        logger.info("Webhook отправлен для summary %d", task_id)
                    else:
                        logger.warning(
                            "Webhook не отправлен для summary %d, требуется retry",
                            task_id,
                            extra={"task_id": task_id, "chat_id": chat_id}
                        )
                    return

                if summary.status in ("failed", "error"):
                    logger.warning(
                        "Summary %d завершена с ошибкой (%s), webhook не отправлен",
                        task_id,
                        summary.status,
                    )
                    return

                # Ещё processing — ждём
                await asyncio.sleep(10)

            except (asyncpg.PostgresError, asyncpg.InterfaceError) as e:
                logger.error(
                    "Database error checking summary %d: %s",
                    task_id,
                    e,
                    exc_info=True,
                )
                await asyncio.sleep(10)
            except Exception as e:
                logger.error(
                    "Unexpected error waiting for summary %d: %s",
                    task_id,
                    type(e).__name__,
                    exc_info=True,
                )
                return

        logger.warning(
            "Timeout waiting for summary %d, webhook не отправлен",
            task_id,
        )
