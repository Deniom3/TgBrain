"""
Диспетчер webhook для summary.

Адаптер для получения конфигурации webhook и fire-and-forget отправки
после генерации summary с graceful degradation.
"""

import asyncio
import logging

from src.settings.repositories.chat_settings import ChatSettingsRepository

from .summary_webhook_service import SummaryWebhookService

logger = logging.getLogger(__name__)


class SummaryWebhookDispatcher:
    """Получение конфига webhook и fire-and-forget отправка после генерации."""

    def __init__(
        self,
        webhook_service: SummaryWebhookService,
        chat_settings_repo: ChatSettingsRepository,
        logger: logging.Logger,
    ) -> None:
        self._webhook_service = webhook_service
        self._chat_settings_repo = chat_settings_repo
        self._logger = logger
        self._pending_tasks: set[asyncio.Task] = set()

    async def dispatch_webhook_on_completion(
        self,
        task_id: int,
        chat_id: int,
    ) -> bool:
        """
        Получить конфигурацию webhook и запланировать отправку.

        Args:
            task_id: ID задачи summary.
            chat_id: ID чата.

        Returns:
            True если webhook запланирован, False если нет или ошибка.
        """
        try:
            webhook_config = await self._chat_settings_repo.get_webhook_config_raw(
                chat_id,
            )
            if webhook_config:
                task = asyncio.create_task(
                    self._webhook_service.send_webhook_after_generation(
                        task_id=task_id,
                        chat_id=chat_id,
                        config=webhook_config,
                    ),
                )
                self._pending_tasks.add(task)
                task.add_done_callback(self._pending_tasks.discard)
                task.add_done_callback(self._log_task_result)
                self._logger.info(
                    "Задача %d: webhook запланирован к отправке для чата %d",
                    task_id,
                    chat_id,
                )
                return True
            return False
        except Exception as e:
            self._logger.warning(
                "Ошибка при подготовке отправки webhook для задачи %d: %s",
                task_id,
                type(e).__name__,
            )
            self._logger.debug(
                "Детали ошибки webhook: %s",
                str(e),
                exc_info=True,
            )
            return False

    def _log_task_result(self, task: asyncio.Task) -> None:
        """Логирование результата webhook задачи."""
        if task.exception():
            self._logger.error("Webhook task failed: %s", task.exception())
