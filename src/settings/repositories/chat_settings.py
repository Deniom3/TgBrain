"""
Агрегирующий модуль для репозитория настроек чатов.

Объединяет функциональность из отдельных модулей:
- chat_settings_base: Базовые CRUD операции
- chat_settings_bulk: Массовые операции и мониторинг
- chat_summary_settings: Summary настройки
"""

import json
import logging
import asyncio
import ipaddress
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, cast
from urllib.parse import parse_qsl, urlparse, urlunparse

import asyncpg

from ...domain.models.chat_filter_config import ChatFilterConfig
from ...models.data_models import ChatSetting, JsonValue, WebhookConfig
from ...models.sql import (
    SQL_DISABLE_WEBHOOK,
    SQL_GET_CHAT_FILTER_CONFIGS,
    SQL_GET_WEBHOOK_CONFIG,
    SQL_SET_WEBHOOK_CONFIG,
)
from .chat_settings_base import ChatSettingsBaseRepository
from .chat_settings_bulk import ChatSettingsBulkRepository
from .chat_summary_settings import ChatSummarySettingsRepository

logger = logging.getLogger(__name__)


class ChatSettingsRepositoryError(Exception):
    """Базовая ошибка репозитория настроек чатов."""


class WebhookConfigValidationError(ChatSettingsRepositoryError):
    """Ошибка валидации webhook конфигурации."""


ALLOWED_WEBHOOK_CONFIG_FIELDS = {
    "type",
    "url",
    "method",
    "headers",
    "body_template",
    "message_thread_id",
}
ALLOWED_WEBHOOK_METHODS = {"POST", "GET", "PUT", "PATCH", "DELETE"}
SENSITIVE_HEADER_MARKERS = {
    "authorization",
    "token",
    "secret",
    "password",
    "api-key",
    "apikey",
    "x-api-key",
    "cookie",
    "set-cookie",
    "proxy-authorization",
    "x-auth-token",
}
MAX_WEBHOOK_URL_LENGTH = 2048
MAX_WEBHOOK_HEADERS_COUNT = 50
MAX_WEBHOOK_HEADER_KEY_LENGTH = 128
MAX_WEBHOOK_HEADER_VALUE_LENGTH = 4096
MAX_WEBHOOK_BODY_TEMPLATE_LENGTH = 20000
MAX_WEBHOOK_BODY_TEMPLATE_DEPTH = 8

BLOCKED_WEBHOOK_HOSTS = {
    "localhost",
    "127.0.0.1",
    "::1",
    "169.254.169.254",
    "metadata.google.internal",
}

SAFE_HEADER_ALLOWLIST = {
    "content-type",
    "accept",
    "user-agent",
    "x-request-id",
}

BLOCKED_IPS = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("100.100.100.200"),
}


class ChatSettingsRepository(ChatSettingsBaseRepository, ChatSettingsBulkRepository):
    """
    Основной репозиторий для управления настройками чатов.
    
    Объединяет методы из:
    - ChatSettingsBaseRepository: upsert, get, get_all, update, delete
    - ChatSettingsBulkRepository: bulk_upsert, get_monitored_chats, toggle_chat_monitoring, etc.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        """
        Инициализировать репозиторий.

        Args:
            pool: Pool соединений с БД.
        """
        self._pool = pool
        self._summary_repo: Optional[ChatSummarySettingsRepository] = None

    def _get_summary_repo(self) -> ChatSummarySettingsRepository:
        """Получить или создать summary репозиторий."""
        if self._summary_repo is None:
            self._summary_repo = ChatSummarySettingsRepository(self._pool)
        return self._summary_repo

    # ==================== Summary Management (прокси-методы) ====================

    async def enable_summary(self, chat_id: int) -> Optional[ChatSetting]:
        """Включить генерацию summary для чата."""
        return await self._get_summary_repo().enable_summary(chat_id)

    async def disable_summary(self, chat_id: int) -> Optional[ChatSetting]:
        """Отключить генерацию summary для чата."""
        return await self._get_summary_repo().disable_summary(chat_id)

    async def toggle_summary(self, chat_id: int) -> Optional[ChatSetting]:
        """Переключить статус генерации summary для чата."""
        return await self._get_summary_repo().toggle_summary(chat_id)

    async def set_summary_period(self, chat_id: int, minutes: int) -> Optional[ChatSetting]:
        """Установить период сбора сообщений для summary."""
        return await self._get_summary_repo().set_summary_period(chat_id, minutes)

    async def set_summary_schedule(self, chat_id: int, schedule: str) -> Optional[ChatSetting]:
        """Установить расписание генерации summary."""
        return await self._get_summary_repo().set_summary_schedule(chat_id, schedule)

    async def clear_summary_schedule(self, chat_id: int) -> Optional[ChatSetting]:
        """Отключить расписание генерации summary."""
        return await self._get_summary_repo().clear_summary_schedule(chat_id)

    async def get_summary_settings(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """Получить настройки summary для чата."""
        return await self._get_summary_repo().get_summary_settings(chat_id)

    async def set_custom_prompt(self, chat_id: int, prompt: str) -> Optional[ChatSetting]:
        """Установить кастомный промпт для summary."""
        return await self._get_summary_repo().set_custom_prompt(chat_id, prompt)

    async def get_custom_prompt(self, chat_id: int) -> Optional[str]:
        """Получить кастомный промпт для чата."""
        return await self._get_summary_repo().get_custom_prompt(chat_id)

    async def clear_custom_prompt(self, chat_id: int) -> Optional[ChatSetting]:
        """Сбросить кастомный промпт на дефолтный."""
        return await self._get_summary_repo().clear_custom_prompt(chat_id)

    # ==================== Helper Methods ====================

    def _parse_webhook_config(self, value: object) -> Optional[WebhookConfig]:
        if value is None:
            return None

        if isinstance(value, dict):
            return cast(WebhookConfig, value)

        if isinstance(value, str):
            try:
                parsed_value = json.loads(value)
            except json.JSONDecodeError:
                return None
            if isinstance(parsed_value, dict):
                return cast(WebhookConfig, parsed_value)
            return None

        return None

    @staticmethod
    def _is_sensitive_header_key(header_key: str) -> bool:
        normalized = header_key.lower().strip()
        if normalized not in SAFE_HEADER_ALLOWLIST:
            return True
        return any(marker in normalized for marker in SENSITIVE_HEADER_MARKERS)

    @staticmethod
    def _mask_secret_string(secret_value: str) -> str:
        if len(secret_value) <= 6:
            return "***"
        return f"{secret_value[:3]}***{secret_value[-3:]}"

    @staticmethod
    def _sanitize_webhook_url(url: str) -> str:
        parsed = urlparse(url)

        redacted_path_segments: List[str] = []
        for segment in parsed.path.split("/"):
            if not segment:
                redacted_path_segments.append(segment)
                continue

            lower_segment = segment.lower()
            if any(marker in lower_segment for marker in SENSITIVE_HEADER_MARKERS):
                redacted_path_segments.append("***")
            elif lower_segment.startswith("bot") and len(segment) > 6:
                redacted_path_segments.append(f"bot{ChatSettingsRepository._mask_secret_string(segment[3:])}")
            else:
                redacted_path_segments.append(segment)

        redacted_query = []
        for key, value in parse_qsl(parsed.query, keep_blank_values=True):
            if ChatSettingsRepository._is_sensitive_header_key(key):
                redacted_query.append((key, "***"))
            else:
                redacted_query.append((key, value))

        redacted_netloc = parsed.netloc
        if parsed.username is not None or parsed.password is not None:
            if parsed.port is None:
                redacted_netloc = parsed.hostname or ""
            else:
                redacted_netloc = f"{parsed.hostname}:{parsed.port}"

        return urlunparse(
            (
                parsed.scheme,
                redacted_netloc,
                "/".join(redacted_path_segments),
                parsed.params,
                "&".join(f"{k}={v}" for k, v in redacted_query),
                parsed.fragment,
            )
        )

    @staticmethod
    def _mask_webhook_config(config: WebhookConfig) -> WebhookConfig:
        masked = cast(WebhookConfig, dict(config))
        headers = config.get("headers")
        if isinstance(headers, dict):
            masked_headers: Dict[str, str] = {}
            for key, value in headers.items():
                if not isinstance(key, str) or not isinstance(value, str):
                    continue
                masked_headers[key] = "***" if ChatSettingsRepository._is_sensitive_header_key(key) else value
            masked["headers"] = masked_headers

        url = config.get("url")
        if isinstance(url, str):
            masked["url"] = ChatSettingsRepository._sanitize_webhook_url(url)

        return masked

    @staticmethod
    def _validate_webhook_url(url: str) -> None:
        if not url or len(url) > MAX_WEBHOOK_URL_LENGTH:
            raise WebhookConfigValidationError("Некорректная длина URL webhook")

        parsed_url = urlparse(url)
        if parsed_url.scheme not in {"http", "https"}:
            raise WebhookConfigValidationError("Webhook URL должен использовать http/https")
        if parsed_url.scheme == "http":
            raise WebhookConfigValidationError("Webhook URL должен использовать https")
        if not parsed_url.netloc:
            raise WebhookConfigValidationError("Webhook URL должен содержать хост")

        host = parsed_url.hostname
        if host is None:
            raise WebhookConfigValidationError("Webhook URL должен содержать корректный host")

        lowered_host = host.lower()
        if lowered_host in BLOCKED_WEBHOOK_HOSTS:
            raise WebhookConfigValidationError("Webhook URL указывает на запрещённый host")

        try:
            ip = ipaddress.ip_address(lowered_host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                raise WebhookConfigValidationError("Webhook URL указывает на недопустимый IP")
            if ip in BLOCKED_IPS:
                raise WebhookConfigValidationError("Webhook URL указывает на запрещённый служебный IP")
        except ValueError:
            blocked_suffixes = (
                ".local",
                ".localhost",
                ".internal",
            )
            if lowered_host.endswith(blocked_suffixes):
                raise WebhookConfigValidationError("Webhook URL указывает на недопустимый внутренний host")

    @staticmethod
    async def _validate_webhook_dns(host: str) -> None:
        loop = asyncio.get_running_loop()

        try:
            resolved_hosts = await loop.getaddrinfo(host, None)
        except OSError as error:
            raise WebhookConfigValidationError("Не удалось разрешить host webhook URL") from error

        if not resolved_hosts:
            raise WebhookConfigValidationError("Не удалось разрешить host webhook URL")

        for addr_info in resolved_hosts:
            ip_value = addr_info[4][0]
            resolved_ip = ipaddress.ip_address(ip_value)
            if (
                resolved_ip.is_private
                or resolved_ip.is_loopback
                or resolved_ip.is_link_local
                or resolved_ip.is_reserved
                or resolved_ip.is_multicast
                or resolved_ip in BLOCKED_IPS
            ):
                raise WebhookConfigValidationError(
                    "Webhook URL разрешается во внутренний/служебный адрес"
                )

    @staticmethod
    def _validate_webhook_headers(headers: object) -> Dict[str, str]:
        if headers is None:
            return {}
        if not isinstance(headers, dict):
            raise WebhookConfigValidationError("headers должен быть объектом")
        if len(headers) > MAX_WEBHOOK_HEADERS_COUNT:
            raise WebhookConfigValidationError("Превышено допустимое число headers")

        validated_headers: Dict[str, str] = {}
        for key, value in headers.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise WebhookConfigValidationError("Ключи и значения headers должны быть строками")
            if not key.strip():
                raise WebhookConfigValidationError("Имя header не может быть пустым")
            if len(key) > MAX_WEBHOOK_HEADER_KEY_LENGTH:
                raise WebhookConfigValidationError("Имя header превышает допустимую длину")
            if len(value) > MAX_WEBHOOK_HEADER_VALUE_LENGTH:
                raise WebhookConfigValidationError("Значение header превышает допустимую длину")
            validated_headers[key] = value
        return validated_headers

    @staticmethod
    def _validate_body_template_json(
        value: JsonValue,
        depth: int = 0,
    ) -> None:
        if depth > MAX_WEBHOOK_BODY_TEMPLATE_DEPTH:
            raise WebhookConfigValidationError("body_template превышает допустимую глубину")

        if isinstance(value, dict):
            for nested_value in value.values():
                ChatSettingsRepository._validate_body_template_json(nested_value, depth + 1)
            return

        if isinstance(value, list):
            for item in value:
                ChatSettingsRepository._validate_body_template_json(item, depth + 1)
            return

        if isinstance(value, (str, int, float, bool)) or value is None:
            return

        raise WebhookConfigValidationError("body_template содержит неподдерживаемый тип данных")

    @staticmethod
    async def _validate_webhook_config(config: Mapping[str, object]) -> WebhookConfig:
        unknown_fields = set(config.keys()) - ALLOWED_WEBHOOK_CONFIG_FIELDS
        if unknown_fields:
            raise WebhookConfigValidationError("Обнаружены неподдерживаемые поля webhook_config")

        method_raw = config.get("method")
        if not isinstance(method_raw, str):
            raise WebhookConfigValidationError("Поле method обязательно и должно быть строкой")
        method = method_raw.upper().strip()
        if method not in ALLOWED_WEBHOOK_METHODS:
            raise WebhookConfigValidationError("Неподдерживаемый HTTP метод webhook")

        url_raw = config.get("url")
        if not isinstance(url_raw, str):
            raise WebhookConfigValidationError("Поле url обязательно и должно быть строкой")
        url = url_raw.strip()
        ChatSettingsRepository._validate_webhook_url(url)

        parsed_url = urlparse(url)
        host = parsed_url.hostname
        if host is None:
            raise WebhookConfigValidationError("Webhook URL должен содержать корректный host")
        await ChatSettingsRepository._validate_webhook_dns(host)

        headers = ChatSettingsRepository._validate_webhook_headers(config.get("headers"))

        body_template_raw = config.get("body_template")
        if not isinstance(body_template_raw, dict):
            raise WebhookConfigValidationError("Поле body_template обязательно и должно быть объектом")

        body_template_json = json.dumps(body_template_raw, ensure_ascii=False)
        if len(body_template_json) > MAX_WEBHOOK_BODY_TEMPLATE_LENGTH:
            raise WebhookConfigValidationError("body_template превышает допустимую длину")
        ChatSettingsRepository._validate_body_template_json(cast(JsonValue, body_template_raw))

        config_type_raw = config.get("type")
        config_type: Optional[str] = None
        if config_type_raw is not None:
            if not isinstance(config_type_raw, str):
                raise WebhookConfigValidationError("Поле type должно быть строкой")
            if not config_type_raw.strip():
                raise WebhookConfigValidationError("Поле type не может быть пустым")
            config_type = config_type_raw.strip()

        validated_config: WebhookConfig = {
            "url": url,
            "method": method,
            "headers": headers,
            "body_template": cast(dict[str, JsonValue], body_template_raw),
        }
        if config_type is not None:
            validated_config["type"] = config_type

        message_thread_id = config.get("message_thread_id")
        if message_thread_id is not None:
            if isinstance(message_thread_id, bool):
                raise WebhookConfigValidationError("message_thread_id не может быть bool")
            if isinstance(message_thread_id, int):
                if message_thread_id <= 0:
                    raise WebhookConfigValidationError("message_thread_id должен быть положительным")
                validated_config["message_thread_id"] = message_thread_id
            elif isinstance(message_thread_id, str):
                if not message_thread_id.strip():
                    raise WebhookConfigValidationError("message_thread_id не может быть пустым")
                validated_config["message_thread_id"] = message_thread_id.strip()
            else:
                raise WebhookConfigValidationError("message_thread_id имеет неверный тип")

        return validated_config

    async def _validate_loaded_config(
        self,
        config: WebhookConfig,
        *,
        sanitize: bool,
    ) -> WebhookConfig:
        validated = await self._validate_webhook_config(config)
        if sanitize:
            return self._mask_webhook_config(validated)
        return validated

    def _build_chat_setting_from_row(self, row: asyncpg.Record) -> ChatSetting:
        row_data: Dict[str, Any] = dict(row)
        row_data["webhook_config"] = self._parse_webhook_config(
            row_data.get("webhook_config")
        )
        return ChatSetting(**row_data)

    # ==================== Конфигурация webhook ====================

    async def set_webhook_config(
        self,
        chat_id: int,
        config: Dict[str, object]
    ) -> Optional[ChatSetting]:
        """Установить webhook конфигурацию для чата."""
        try:
            validated_config = await self._validate_webhook_config(config)
        except WebhookConfigValidationError:
            logger.warning("Webhook конфигурация отклонена для чата %s", chat_id)
            return None

        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(
                    SQL_SET_WEBHOOK_CONFIG,
                    chat_id,
                    json.dumps(validated_config),
                )
                if row:
                    return self._build_chat_setting_from_row(row)
                return None
            except (asyncpg.PostgresError, ValueError, TypeError):
                logger.error("Ошибка сохранения webhook конфигурации для чата %s", chat_id, exc_info=True)
                return None

    async def get_webhook_config(self, chat_id: int) -> Optional[Dict[str, object]]:
        """Получить webhook конфигурацию чата для API."""
        return await self._get_webhook_config(chat_id, sanitize=True)

    async def get_webhook_config_raw(self, chat_id: int) -> Optional[Dict[str, object]]:
        """Получить webhook конфигурацию чата для внутреннего использования."""
        return await self._get_webhook_config(chat_id, sanitize=False)

    async def _get_webhook_config(
        self,
        chat_id: int,
        *,
        sanitize: bool,
    ) -> Optional[Dict[str, object]]:
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(SQL_GET_WEBHOOK_CONFIG, chat_id)
                if not row:
                    return None

                parsed_config = self._parse_webhook_config(row["webhook_config"])
                if parsed_config is None:
                    return None

                validated_config = await self._validate_loaded_config(parsed_config, sanitize=sanitize)
                return dict(validated_config)
            except WebhookConfigValidationError:
                logger.warning("Webhook конфигурация в БД нарушает контракт для чата %s", chat_id)
                return None
            except (asyncpg.PostgresError, ValueError, TypeError, KeyError):
                logger.error("Ошибка получения webhook конфигурации для чата %s", chat_id, exc_info=True)
                return None

    async def disable_webhook(self, chat_id: int) -> Optional[ChatSetting]:
        """Отключить webhook для чата."""
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(SQL_DISABLE_WEBHOOK, chat_id)
                if row:
                    return self._build_chat_setting_from_row(row)
                return None
            except asyncpg.PostgresError:
                logger.error("Ошибка отключения webhook для чата %s", chat_id, exc_info=True)
                return None

    async def get_chats_with_schedule(self) -> list[ChatSetting]:
        """
        Получить все чаты с активным расписанием, требующие обработки.

        Returns:
            Список ChatSetting с summary_schedule и next_schedule_run <= now.
        """
        return await self._get_summary_repo().get_chats_with_schedule()

    async def update_next_schedule_run(
        self,
        chat_id: int,
        next_run: datetime
    ) -> Optional[ChatSetting]:
        """
        Обновить следующее время запуска расписания для чата.

        Args:
            chat_id: ID чата.
            next_run: Следующее время запуска в UTC.

        Returns:
            Обновлённый ChatSetting или None.
        """
        from ...models.sql import SQL_UPDATE_NEXT_SCHEDULE_RUN

        async with self._pool.acquire() as conn:
            try:
                next_run_value = next_run
                if next_run_value.tzinfo is not None:
                    next_run_value = next_run_value.replace(tzinfo=None)
                row = await conn.fetchrow(
                    SQL_UPDATE_NEXT_SCHEDULE_RUN,
                    chat_id,
                    next_run_value,
                )
                if row:
                    return self._build_chat_setting_from_row(row)
                return None
            except asyncpg.PostgresError:
                logger.error(
                    f"Ошибка обновления next_schedule_run для чата {chat_id}",
                    exc_info=True,
                )
                return None

    async def get_monitored_chat_ids(self) -> List[int]:
        """
        Получить ID чатов, которые нужно мониторить.

        Returns:
            Список ID чатов.
        """
        settings = await self.get_monitored_chats()
        return [s.chat_id for s in settings]

    async def get_enabled_summary_chat_ids(self) -> List[int]:
        """Получить ID чатов с включённой генерацией summary."""
        return await self._get_summary_repo().get_enabled_summary_chat_ids()

    async def get_chat_filter_configs(self) -> dict[int, ChatFilterConfig]:
        """Получить конфигурации фильтров для всех мониторимых чатов."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(SQL_GET_CHAT_FILTER_CONFIGS)
            return {
                row["chat_id"]: ChatFilterConfig(
                    filter_bots=row["filter_bots"],
                    filter_actions=row["filter_actions"],
                    filter_min_length=row["filter_min_length"],
                    filter_ads=row["filter_ads"],
                )
                for row in rows
            }
