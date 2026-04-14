"""
WebhookService — отправка summary по webhook URL.
"""

import asyncio
import ipaddress
import logging
import random
import re
import socket
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from ..domain.value_objects import WebhookMethod, WebhookUrl
from .exceptions import WebhookDeliveryError, WebhookValidationError
from .template_engine import TemplateEngine

logger = logging.getLogger(__name__)

MAX_LOGGED_RESPONSE_TEXT_LENGTH = 500
MASKED_TOKEN_VALUE = "***"
BOT_TOKEN_PREFIX = "bot"
MESSAGE_THREAD_ID_KEY = "message_thread_id"
CHAT_ID_KEY = "chat_id"
PARSE_MODE_KEY = "parse_mode"
TEXT_KEY = "text"
SUMMARY_KEY = "summary"

TELEGRAM_PARSE_ERROR_PATTERNS = [
    "can't parse entities",
    "can't find end of the entity",
]
MESSAGE_THREAD_PLACEHOLDER = f"{{{{{MESSAGE_THREAD_ID_KEY}}}}}"

# Поля, которые следует маскировать в логах из соображений безопасности
SENSITIVE_PAYLOAD_FIELDS = {
    "token",
    "password",
    "secret",
    "api_key",
    "apikey",
    "api-key",
    "auth",
    "authorization",
    "bearer",
    "credential",
    "private_key",
    "access_token",
    "bot_token",
    "pass",
}

# Точные ключи query параметров для маскировки (case-insensitive)
EXACT_SENSITIVE_KEYS = {
    "token",
    "api_key",
    "apikey",
    "api-key",
    "secret",
    "password",
    "pass",
    "auth",
    "authorization",
    "bearer",
    "private_key",
    "credential",
    "access_token",
    "bot_token",
    "cookie",
}


class WebhookService:
    """Сервис отправки summary по webhook URL."""

    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_seconds: int = 30,
    ):
        """
        Инициализировать WebhookService.

        Args:
            timeout: Таймаут запроса в секундах.
            max_retries: Максимальное количество попыток.
            backoff_seconds: Базовая задержка между попытками.
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        """
        Получить HTTP клиент (ленивая инициализация).

        Клиент создаётся при первом вызове и переиспользуется
        для всех subsequent запросов. Закрывается в lifespan shutdown.

        Returns:
            httpx.AsyncClient для отправки запросов.
        """
        if self._client is None:
            timeout = httpx.Timeout(self.timeout, connect=10.0)
            self._client = httpx.AsyncClient(
                timeout=timeout,
                verify=True,
                follow_redirects=False,
            )
        return self._client

    @staticmethod
    def _mask_url(url: str) -> str:
        """
        Замаскировать чувствительные данные в URL.

        Маскирует:
        - Userinfo (user:pass@host)
        - Bot токены в пути
        - Чувствительные query параметры (token, api_key, secret, etc.)

        Args:
            url: URL для маскировки.

        Returns:
            URL с замаскированными чувствительными данными.
        """
        parsed = urlparse(url)

        # Маскировать userinfo (user:pass@)
        if parsed.username or parsed.password:
            netloc = f"***:***@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            parsed = parsed._replace(netloc=netloc)

        path_segments = parsed.path.split("/")
        masked_segments = []
        for segment in path_segments:
            if segment.startswith(BOT_TOKEN_PREFIX) and len(segment) > len(BOT_TOKEN_PREFIX):
                masked_segments.append(f"{BOT_TOKEN_PREFIX}{MASKED_TOKEN_VALUE}")
            else:
                masked_segments.append(segment)
        masked_path = "/".join(masked_segments)

        # Маскировать query параметры с чувствительными данными (exact match)
        masked_query = []
        for key, value in parse_qsl(parsed.query, keep_blank_values=True):
            if key.lower() in EXACT_SENSITIVE_KEYS:
                masked_query.append((key, MASKED_TOKEN_VALUE))
            else:
                masked_query.append((key, value))
        encoded_query = urlencode(masked_query)

        return urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                masked_path,
                parsed.params,
                encoded_query,
                parsed.fragment,
            )
        )

    @staticmethod
    def _normalize_message_thread_id(value: object) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return str(value) if value > 0 else None
        if isinstance(value, float):
            value_int = int(value)
            return str(value_int) if value_int > 0 else None
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped or stripped == MESSAGE_THREAD_PLACEHOLDER:
                return None
            if stripped.isdigit():
                return stripped
        return None

    @staticmethod
    def _build_payload_log_data(
        payload: dict[str, object],
        summary_length: int,
    ) -> dict[str, object]:
        text_value = payload.get(TEXT_KEY)
        text_length = len(text_value) if isinstance(text_value, str) else None
        return {
            "keys": sorted(payload.keys()),
            CHAT_ID_KEY: payload.get(CHAT_ID_KEY),
            MESSAGE_THREAD_ID_KEY: payload.get(MESSAGE_THREAD_ID_KEY),
            PARSE_MODE_KEY: payload.get(PARSE_MODE_KEY),
            "text_length": text_length,
            "summary_length": summary_length,
        }

    @staticmethod
    def _mask_sensitive_data(value: object, key: str) -> object:
        """
        Замаскировать чувствительные данные в логах.

        Args:
            value: Значение для маскировки.
            key: Ключ поля.

        Returns:
            Замаскированное значение или оригинальное если не чувствительное.
        """
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in SENSITIVE_PAYLOAD_FIELDS):
            return MASKED_TOKEN_VALUE
        return value

    @staticmethod
    def _build_safe_payload_log_data(
        payload: dict[str, object],
        summary_length: int,
    ) -> dict[str, object]:
        """
        Построить безопасный для логирования payload с замаскированными чувствительными данными.

        Args:
            payload: Original payload dict.
            summary_length: Длина summary.

        Returns:
            Dict с замаскированными чувствительными полями.
        """
        text_value = payload.get(TEXT_KEY)
        text_length = len(text_value) if isinstance(text_value, str) else None
        
        # Маскируем chat_id если он чувствительный
        chat_id = payload.get(CHAT_ID_KEY)
        if chat_id is not None:
            chat_id = WebhookService._mask_sensitive_data(chat_id, CHAT_ID_KEY)
        
        # Маскируем message_thread_id если он чувствительный
        message_thread_id = payload.get(MESSAGE_THREAD_ID_KEY)
        if message_thread_id is not None:
            message_thread_id = WebhookService._mask_sensitive_data(message_thread_id, MESSAGE_THREAD_ID_KEY)

        return {
            "keys": sorted(payload.keys()),
            CHAT_ID_KEY: chat_id,
            MESSAGE_THREAD_ID_KEY: message_thread_id,
            PARSE_MODE_KEY: payload.get(PARSE_MODE_KEY),
            "text_length": text_length,
            "summary_length": summary_length,
        }

    @staticmethod
    def _mask_response_text(response_text: str) -> str:
        """
        Замаскировать чувствительные данные в тексте ответа.

        Args:
            response_text: Original response text.

        Returns:
            Response text с замаскированными чувствительными данными.
        """
        masked = response_text
        for sensitive_field in SENSITIVE_PAYLOAD_FIELDS:
            # Маскируем значения после : в JSON и других форматах
            masked = re.sub(
                rf'(["\']?{sensitive_field}["\']?\s*[:=]\s*["\']?)([^"\',\s}}]+)(["\']?)',
                rf'\1{MASKED_TOKEN_VALUE}\3',
                masked,
                flags=re.IGNORECASE,
            )
        return masked

    @staticmethod
    def _mask_sensitive_headers(headers: dict[str, str]) -> dict[str, str]:
        """
        Замаскировать чувствительные значения в headers.

        Args:
            headers: Original headers dict.

        Returns:
            Headers с замаскированными чувствительными значениями.
        """
        masked = {}
        for key, value in headers.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in SENSITIVE_PAYLOAD_FIELDS):
                masked[key] = MASKED_TOKEN_VALUE
            else:
                masked[key] = value
        return masked

    async def close(self) -> None:
        """Закрыть HTTP клиент."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _validate_ip_address(
        self,
        url: str,
        chat_id: Optional[int] = None,
    ) -> None:
        """
        Проверить IP адрес хоста на предмет private/link-local/loopback.

        Защита от SSRF через DNS rebinding атаки.

        Args:
            url: URL для проверки.
            chat_id: ID чата для audit logging (опционально).

        Raises:
            WebhookDeliveryError: Если URL разрешается в private IP.
        """
        parsed = urlparse(url)
        if not parsed.hostname:
            raise WebhookDeliveryError("Invalid hostname in webhook URL", status_code=400)

        try:
            addr_info = await asyncio.get_running_loop().getaddrinfo(
                parsed.hostname,
                0,
                family=socket.AF_UNSPEC,
                type=socket.SOCK_STREAM,
            )
            for family, socktype, proto, canonname, sockaddr in addr_info:
                ip_obj = ipaddress.ip_address(sockaddr[0])
                if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
                    logger.warning(
                        "SSRF attempt detected: %s → %s",
                        parsed.hostname,
                        ip_obj,
                        extra={
                            "event_type": "ssrf_attempt_blocked",
                            "hostname": parsed.hostname,
                            "ip_address": str(ip_obj),
                            "chat_id": chat_id,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                    raise WebhookDeliveryError(
                        "Webhook URL resolves to private IP address",
                        status_code=400,
                    )
        except (socket.gaierror, OSError) as e:
            raise WebhookDeliveryError(f"DNS resolution failed: {e}", status_code=400)

    async def send_summary_webhook(
        self,
        webhook_config: dict,
        summary_text: str,
        chat_id: int,
        chat_title: str,
        period_start: datetime,
        period_end: datetime,
        messages_count: int,
    ) -> bool:
        """
        Отправить summary по webhook URL.

        Args:
            webhook_config: Конфигурация webhook (url, method, headers, body_template).
            summary_text: Текст summary.
            chat_id: ID чата.
            chat_title: Название чата.
            period_start: Начало периода.
            period_end: Конец периода.
            messages_count: Количество сообщений.

        Returns:
            True если успешно, False иначе.
        """
        url = webhook_config.get("url")
        if not isinstance(url, str) or not url:
            raise WebhookValidationError("Webhook URL не указан")
        url_value = url

        # Валидация URL
        try:
            WebhookUrl(url_value)
        except ValueError:
            raise WebhookValidationError("Неверный формат URL webhook")

        # Валидация метода
        method = webhook_config.get("method", "POST")
        if not isinstance(method, str):
            raise WebhookValidationError("Неверный HTTP метод webhook")
        try:
            validated_method = WebhookMethod(method)
        except ValueError:
            raise WebhookValidationError("Неверный HTTP метод webhook")

        body_template = webhook_config.get("body_template", {})

        context = {
            SUMMARY_KEY: summary_text,
            CHAT_ID_KEY: str(chat_id),
            "chat_title": chat_title,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "messages_count": str(messages_count),
        }

        config_message_thread_id = self._normalize_message_thread_id(
            webhook_config.get(MESSAGE_THREAD_ID_KEY)
        )
        template_message_thread_id = None
        if isinstance(body_template, dict):
            template_message_thread_id = self._normalize_message_thread_id(
                body_template.get(MESSAGE_THREAD_ID_KEY)
            )

        resolved_message_thread_id = template_message_thread_id or config_message_thread_id
        if resolved_message_thread_id is not None:
            context[MESSAGE_THREAD_ID_KEY] = resolved_message_thread_id

        rendered_url = TemplateEngine.render(url_value, **context)
        if not isinstance(rendered_url, str):
            raise WebhookValidationError("Неверный формат URL webhook")
        rendered_url_str = rendered_url

        # Валидация rendered_url после шаблонизации (защита от SSRF)
        try:
            validated_url = WebhookUrl(rendered_url_str)
        except ValueError:
            raise WebhookValidationError("Неверный формат URL webhook")

        # Проверка IP адреса на private/link-local/loopback (защита от DNS rebinding)
        await self._validate_ip_address(rendered_url_str, chat_id=chat_id)

        headers = webhook_config.get("headers", {})
        rendered_headers = {
            key: str(TemplateEngine.render(value, **context))
            for key, value in headers.items()
        }

        body_template = webhook_config.get("body_template", {})
        rendered_body = TemplateEngine.render_dict(body_template, **context)

        client = self._get_client()

        masked_url = self._mask_url(validated_url.value)
        summary_length = len(summary_text)
        payload_log_data = self._build_safe_payload_log_data(rendered_body, summary_length)
        masked_headers_for_log = self._mask_sensitive_headers(rendered_headers)

        logger.info(
            "Webhook %s %s, headers: %s, payload: %s",
            validated_method.value,
            masked_url,
            masked_headers_for_log,
            payload_log_data,
        )

        for attempt in range(1, self.max_retries + 1):
            try:
                response = await client.request(
                    method=validated_method.value,
                    url=validated_url.value,
                    headers=rendered_headers,
                    json=rendered_body,
                )

                if response.status_code < 400:
                    logger.info(
                        "Webhook успешно отправлен (status: %d)",
                        response.status_code,
                    )
                    return True
                elif response.status_code < 500:
                    response_text = response.text[:MAX_LOGGED_RESPONSE_TEXT_LENGTH]
                    if len(response.text) > MAX_LOGGED_RESPONSE_TEXT_LENGTH:
                        response_text += "..."
                    response_text = self._mask_response_text(response_text)

                    is_parse_error = any(
                        pattern in response.text.lower()
                        for pattern in TELEGRAM_PARSE_ERROR_PATTERNS
                    )

                    if is_parse_error and "parse_mode" in rendered_body:
                        logger.warning(
                            "Telegram Markdown parse error, повтор с parse_mode=None: %s %s, response: %s",
                            validated_method.value,
                            masked_url,
                            response_text[:200],
                        )
                        fallback_body = dict(rendered_body)
                        del fallback_body["parse_mode"]

                        fallback_response = await client.request(
                            method=validated_method.value,
                            url=validated_url.value,
                            headers=rendered_headers,
                            json=fallback_body,
                        )

                        if fallback_response.status_code < 400:
                            logger.info(
                                "Webhook успешно отправлен после fallback (status: %d)",
                                fallback_response.status_code,
                            )
                            return True

                        fallback_text = fallback_response.text[:MAX_LOGGED_RESPONSE_TEXT_LENGTH]
                        logger.error(
                            "Webhook ошибка после fallback: %d, %s %s, response: %s",
                            fallback_response.status_code,
                            validated_method.value,
                            masked_url,
                            fallback_text,
                        )

                    logger.error(
                        "Webhook ошибка 4xx: %d, %s %s, response: %s, прекращение retry",
                        response.status_code,
                        validated_method.value,
                        masked_url,
                        response_text,
                    )
                    raise WebhookDeliveryError(
                        f"Client error: {response.status_code}",
                        status_code=response.status_code,
                    )
                else:
                    response_text = response.text[:MAX_LOGGED_RESPONSE_TEXT_LENGTH]
                    if len(response.text) > MAX_LOGGED_RESPONSE_TEXT_LENGTH:
                        response_text += "..."
                    # Маскируем чувствительные данные в response
                    response_text = self._mask_response_text(response_text)
                    logger.warning(
                        "Webhook вернул ошибку (status: %d, attempt: %d), response: %s",
                        response.status_code,
                        attempt,
                        response_text,
                    )
                    if attempt < self.max_retries:
                        await asyncio.sleep(
                            self.backoff_seconds * (2 ** (attempt - 1)) + random.uniform(0, 1)
                        )
                        continue
                    else:
                        raise WebhookDeliveryError(
                            f"Server error after {attempt} attempts: {response.status_code}",
                            status_code=response.status_code,
                        )

            except httpx.TimeoutException:
                logger.warning(
                    "Webhook timeout (attempt %d/%d)",
                    attempt,
                    self.max_retries,
                )
                logger.debug("Webhook timeout details", exc_info=True)
                if attempt < self.max_retries:
                    await asyncio.sleep(
                        self.backoff_seconds * (2 ** (attempt - 1)) + random.uniform(0, 1)
                    )
                    continue
                else:
                    raise WebhookDeliveryError(f"Timeout after {attempt} attempts")

            except WebhookDeliveryError:
                # Re-raise без дополнительного логирования — уже залогировано в месте возникновения
                # Re-raise policy: WebhookDeliveryError пробрасывается выше для обработки в application service
                raise

            except httpx.RequestError:
                logger.error(
                    "Webhook request error (attempt %d/%d)",
                    attempt,
                    self.max_retries,
                )
                logger.debug("Webhook request error details", exc_info=True)
                if attempt < self.max_retries:
                    await asyncio.sleep(
                        self.backoff_seconds * (2 ** (attempt - 1)) + random.uniform(0, 1)
                    )
                    continue
                else:
                    raise WebhookDeliveryError(f"Request failed after {attempt} attempts")

        logger.error("Webhook не отправлен после %d попыток", self.max_retries)
        return False
