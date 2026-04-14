"""
Webhook Settings Application Service.

Назначение:
- Инкапсуляция бизнес-логики управления webhook настройками
- Валидация конфигурации webhook
- Тестирование webhook endpoints
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import aiohttp

from ..exceptions import (
    ChatNotFoundError,
    InvalidInputError,
)
from ...settings.repositories.chat_settings import ChatSettingsRepository
from ...webhook.exceptions import WebhookDeliveryError, WebhookTimeoutError
from ...webhook.webhook_service import WebhookService
from ...models.data_models import ChatSetting

logger = logging.getLogger(__name__)


class WebhookSettingsService:
    """
    Application service для управления настройками webhook.

    Coordinates webhook configuration and testing.
    """

    def __init__(
        self,
        chat_settings_repo: ChatSettingsRepository,
        webhook_service: WebhookService,
    ) -> None:
        """
        Initialize service.

        Args:
            chat_settings_repo: Репозиторий настроек чата.
            webhook_service: Сервис отправки webhook.
        """
        self._repo = chat_settings_repo
        self._webhook = webhook_service

    async def set_webhook_config(
        self,
        chat_id: int,
        url: str,
        method: str,
        headers: dict[str, str],
        body_template: dict[str, Any],
    ) -> ChatSetting:
        """
        Установить конфигурацию webhook для чата.

        Args:
            chat_id: Chat identifier.
            url: Webhook URL.
            method: HTTP method.
            headers: HTTP headers.
            body_template: Request body template.

        Returns:
            Updated ChatSetting.

        Raises:
            ChatNotFoundError: Если чат не найден.
            InvalidInputError: Если конфигурация невалидна.
        """
        setting = await self._repo.get(chat_id)
        if not setting:
            logger.warning("Чат %d не найден для установки webhook конфигурации", chat_id)
            raise ChatNotFoundError(chat_id)

        config: dict[str, object] = {
            "url": url,
            "method": method,
            "headers": headers,
            "body_template": body_template,
        }

        setting = await self._repo.set_webhook_config(chat_id=chat_id, config=config)

        if not setting:
            logger.error("Не удалось установить webhook конфигурацию для чата %d", chat_id)
            raise InvalidInputError(f"Failed to set webhook config for chat {chat_id}")

        logger.info("Webhook конфигурация установлена для чата %d", chat_id)
        return setting

    async def get_webhook_config(
        self,
        chat_id: int,
    ) -> tuple[bool, Optional[dict[str, Any]], str]:
        """
        Получить конфигурацию webhook для чата.

        Args:
            chat_id: Chat identifier.

        Returns:
            Tuple of (webhook_enabled, webhook_config, message).

        Raises:
            ChatNotFoundError: Если чат не найден.
        """
        setting = await self._repo.get(chat_id)
        if not setting:
            logger.warning("Чат %d не найден для получения webhook конфигурации", chat_id)
            raise ChatNotFoundError(chat_id)

        config = await self._repo.get_webhook_config(chat_id)
        message = "Webhook конфигурация получена" if config else "Webhook не настроен"

        return (
            setting.webhook_enabled if setting else False,
            config,
            message,
        )

    async def disable_webhook(self, chat_id: int) -> ChatSetting:
        """
        Отключить webhook для чата.

        Args:
            chat_id: Chat identifier.

        Returns:
            Updated ChatSetting.

        Raises:
            ChatNotFoundError: Если чат не найден.
            InvalidInputError: Если отключение не удалось.
        """
        setting = await self._repo.get(chat_id)
        if not setting:
            logger.warning("Чат %d не найден для отключения webhook", chat_id)
            raise ChatNotFoundError(chat_id)

        setting = await self._repo.disable_webhook(chat_id)

        if not setting:
            logger.error("Не удалось отключить webhook для чата %d", chat_id)
            raise InvalidInputError(f"Failed to disable webhook for chat {chat_id}")

        logger.info("Webhook отключён для чата %d", chat_id)
        return setting

    async def test_webhook(self, chat_id: int) -> dict[str, Any]:
        """
        Отправить тестовый webhook.

        Args:
            chat_id: Chat identifier.

        Returns:
            Dict с результатом тестирования.

        Raises:
            ChatNotFoundError: Если чат не найден.
            InvalidInputError: Если webhook не настроен.
            WebhookDeliveryError: При ошибке доставки.
            WebhookTimeoutError: При таймауте.
        """
        setting = await self._repo.get(chat_id)
        if not setting:
            logger.warning("Чат %d не найден для тестовой отправки webhook", chat_id)
            raise ChatNotFoundError(chat_id)

        config = await self._repo.get_webhook_config_raw(chat_id)
        if not config:
            logger.warning("Webhook не настроен для чата %d", chat_id)
            raise InvalidInputError(f"Webhook not configured for chat {chat_id}")

        now = datetime.now(timezone.utc)

        try:
            success = await self._webhook.send_summary_webhook(
                webhook_config=config,
                summary_text="Тестовое сообщение",
                chat_id=chat_id,
                chat_title=setting.title or str(chat_id),
                period_start=now,
                period_end=now,
                messages_count=0,
            )

            if success:
                logger.info("Тестовый webhook успешно отправлен для чата %d", chat_id)
                return {
                    "success": True,
                    "chat_id": chat_id,
                    "message": "Тестовый webhook успешно отправлен",
                }
            else:
                logger.error("Ошибка отправки тестового webhook для чата %d", chat_id)
                raise WebhookDeliveryError("Ошибка отправки тестового webhook")

        except WebhookDeliveryError as e:
            logger.error("Webhook ошибка доставки при тестировании: %s", e, exc_info=True)
            raise
        except WebhookTimeoutError as e:
            logger.error("Webhook timeout при тестировании: %s", e, exc_info=True)
            raise
        except (ConnectionError, TimeoutError, aiohttp.ClientError) as e:
            logger.error("Network error при тестировании webhook: %s", e, exc_info=True)
            raise WebhookDeliveryError("Webhook delivery failed")


__all__ = [
    "WebhookSettingsService",
]
