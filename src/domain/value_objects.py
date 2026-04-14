"""
Value Objects для предметной области.

Модуль предоставляет неизменяемые объекты-значения для использования
в моделях данных. Каждый Value Object инкапсулирует валидацию
и обеспечивает целостность данных.
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse

from src.domain.exceptions import ValidationError


class ApiId:
    """Value Object для API ID Telegram.

    Атрибуты:
        value: Положительное целое число API ID.

    Raises:
        ValidationError: Если значение не положительное.
    """

    def __init__(self, value: int) -> None:
        if value <= 0:
            raise ValidationError("api_id должен быть положительным числом", field="value")
        self._value = value

    @property
    def value(self) -> int:
        return self._value

    def to_int(self) -> int:
        """Конвертировать в int."""
        return self._value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ApiId):
            return NotImplemented
        return self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __str__(self) -> str:
        return str(self._value)


class ApiHash:
    """Value Object для API Hash Telegram.

    Атрибуты:
        value: Строка длиной 32 символа.

    Raises:
        ValidationError: Если строка пустая или длина не 32 символа.
    """

    EXPECTED_LENGTH = 32

    def __init__(self, value: str) -> None:
        if not value:
            raise ValidationError("api_hash не может быть пустым", field="value")
        if len(value) != self.EXPECTED_LENGTH:
            raise ValidationError(
                f"api_hash должен быть {self.EXPECTED_LENGTH} символов, получено {len(value)}",
                field="value"
            )
        self._value = value

    @property
    def value(self) -> str:
        return self._value

    def to_str(self) -> str:
        """Конвертировать в str."""
        return self._value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ApiHash):
            return NotImplemented
        return self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __str__(self) -> str:
        return self._value


class PhoneNumber:
    """Value Object для номера телефона Telegram.
    
    Атрибуты:
        value: Номер телефона, начинающийся с '+'.
    
    Raises:
        ValidationError: Если номер пустой или не начинается с '+'.
    """

    def __init__(self, value: str) -> None:
        if not value:
            raise ValidationError("phone_number не может быть пустым", field="value")
        if not value.startswith('+'):
            raise ValidationError("phone_number должен начинаться с '+'", field="value")
        self._value = value

    @property
    def value(self) -> str:
        return self._value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PhoneNumber):
            return NotImplemented
        return self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __str__(self) -> str:
        return self._value


class SessionName:
    """Value Object для имени сессии Telegram.

    Атрибуты:
        value: Непустая строка имени сессии.

    Raises:
        ValidationError: Если имя сессии пустое или содержит запрещённые символы.
    """

    FORBIDDEN_CHARS = {'/', '\\', '\x00'}  # Только символы
    FORBIDDEN_PATTERNS = {'..'}  # Отдельно паттерны
    VALID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')

    def __init__(self, value: str) -> None:
        if not value:
            raise ValidationError("session_name не может быть пустым", field="value")

        # 1. Сначала regex (самая строгая проверка)
        if not self.VALID_PATTERN.match(value):
            raise ValidationError(
                "session_name должен содержать только буквы, цифры, подчёркивание и дефис",
                field="value"
            )

        # 2. Проверка запрещённых символов
        for char in self.FORBIDDEN_CHARS:
            if char in value:
                raise ValidationError(
                    f"session_name содержит запрещённый символ: {char!r}",
                    field="value"
                )

        # 3. Проверка запрещённых паттернов
        for pattern in self.FORBIDDEN_PATTERNS:
            if pattern in value:
                raise ValidationError(
                    f"session_name содержит запрещённый паттерн: {pattern!r}",
                    field="value"
                )

        # 4. Проверка на абсолютный путь (Windows и Unix)
        if value.startswith(('/', '\\')) or (len(value) > 1 and value[1] == ':'):
            raise ValidationError("session_name не может быть абсолютным путём", field="value")

        self._value = value

    @property
    def value(self) -> str:
        return self._value

    def to_str(self) -> str:
        """Конвертировать в str."""
        return self._value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SessionName):
            return NotImplemented
        return self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __str__(self) -> str:
        return self._value


class SessionData:
    """Value Object для данных сессии Telegram.

    Атрибуты:
        value: Непустые байтовые данные сессии (минимум 28KB).

    Raises:
        ValidationError: Если данные сессии пустые или меньше минимального размера.
    """

    MIN_SIZE = 28 * 1024  # 28KB минимальный размер .session файла

    def __init__(self, value: bytes) -> None:
        if not value:
            raise ValidationError("session_data не может быть пустыми", field="value")
        if len(value) < self.MIN_SIZE:
            raise ValidationError(
                f"session_data слишком маленький: {len(value)} байт "
                f"(минимум {self.MIN_SIZE} байт)",
                field="value"
            )
        self._value = value

    @property
    def value(self) -> bytes:
        return self._value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SessionData):
            return NotImplemented
        return self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __str__(self) -> str:
        return f"SessionData({len(self._value)} bytes)"


class MessageText:
    """Value Object для текста сообщения."""
    
    def __init__(self, value: str | None = None) -> None:
        # Allow empty text for media messages (photos, videos, files without caption)
        if value is None:
            self._value = ""
        else:
            self._value = value
    
    @property
    def value(self) -> str:
        return self._value
    
    def __str__(self) -> str:
        return self._value
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MessageText):
            return NotImplemented
        return self._value == other._value
    
    def __len__(self) -> int:
        return len(self._value)


class SenderName:
    """Value Object для имени отправителя."""
    
    DEFAULT: str = "Аноним"
    
    def __init__(self, value: str | None = None) -> None:
        self._value = value or self.DEFAULT
    
    @property
    def value(self) -> str:
        return self._value
    
    def __str__(self) -> str:
        return self._value
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SenderName):
            return NotImplemented
        return self._value == other._value


class ChatTitle:
    """Value Object для названия чата."""
    
    DEFAULT: str = "Unknown"
    
    def __init__(self, value: str | None = None) -> None:
        self._value = value or self.DEFAULT
        if not self._value:
            raise ValidationError("ChatTitle cannot be empty", field="value")
    
    @property
    def value(self) -> str:
        return self._value
    
    def __str__(self) -> str:
        return self._value
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ChatTitle):
            return NotImplemented
        return self._value == other._value


class ChatId:
    """Value Object для ID чата."""
    
    def __init__(self, value: int) -> None:
        if not isinstance(value, int):
            raise ValidationError("ChatId must be an integer", field="value")
        self._value = value
    
    @property
    def value(self) -> int:
        return self._value
    
    def to_int(self) -> int:
        """Конвертировать в int."""
        return self._value
    
    def __str__(self) -> str:
        return str(self._value)
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ChatId):
            return NotImplemented
        return self._value == other._value
    
    def __hash__(self) -> int:
        return hash(self._value)


class SenderId:
    """Value Object для ID отправителя."""
    
    def __init__(self, value: int | None) -> None:
        if value is not None and not isinstance(value, int):
            raise ValidationError("SenderId must be an integer or None", field="value")
        self._value = value
    
    @property
    def value(self) -> int | None:
        return self._value
    
    def to_int(self) -> int | None:
        """Конвертировать в int."""
        return self._value
    
    def __str__(self) -> str:
        return str(self._value)
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SenderId):
            return NotImplemented
        return self._value == other._value
    
    def __hash__(self) -> int:
        return hash(self._value)


class MessageLink:
    """Value Object для ссылки на сообщение."""
    
    def __init__(self, value: str | None) -> None:
        if value is not None:
            if not isinstance(value, str) or not value.strip():
                raise ValidationError("MessageLink must be a non-empty string or None", field="value")
        self._value = value
    
    @property
    def value(self) -> str | None:
        return self._value
    
    def to_str(self) -> str | None:
        """Конвертировать в str."""
        return self._value
    
    def __str__(self) -> str:
        return str(self._value)
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MessageLink):
            return NotImplemented
        return self._value == other._value
    
    def __hash__(self) -> int:
        return hash(self._value)


class ChatType:
    """Value Object для типа чата."""
    
    ALLOWED_TYPES = {"private", "group", "channel", "supergroup", "private_channel", "personal_chat"}
    
    def __init__(self, value: str) -> None:
        if not isinstance(value, str) or value not in self.ALLOWED_TYPES:
            raise ValidationError(f"ChatType must be one of {self.ALLOWED_TYPES}", field="value")
        self._value = value
    
    @property
    def value(self) -> str:
        return self._value
    
    def to_str(self) -> str:
        """Конвертировать в str."""
        return self._value
    
    def __str__(self) -> str:
        return self._value
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ChatType):
            return NotImplemented
        return self._value == other._value
    
    def __hash__(self) -> int:
        return hash(self._value)


class BooleanValue:
    """Value Object для булевых значений."""

    def __init__(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise ValidationError("Value must be boolean", field="value")
        self._value = value

    @property
    def value(self) -> bool:
        return self._value

    def __bool__(self) -> bool:
        return self._value

    def __str__(self) -> str:
        return str(self._value)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BooleanValue):
            return NotImplemented
        return self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)


class WebhookUrl:
    """Валидированный HTTPS URL для webhook.

    Проверяет:
    - Только HTTPS схема
    - Не localhost hostname
    - Не private IP адреса (если hostname — literal IP)
    - Не loopback адреса
    - Не link-local адреса

    Примечание:
        DNS rebinding protection выполняется на уровне сервиса отправки webhook,
        а не в Value Object, чтобы избежать blocking network calls в конструкторе.

    Raises:
        ValidationError: Если URL не соответствует требованиям безопасности.
    """

    def __init__(self, value: str) -> None:
        parsed = urlparse(value)

        # Только HTTPS
        if parsed.scheme != "https":
            raise ValidationError(f"Webhook URL должен быть HTTPS: {value}", field="value")

        hostname = parsed.hostname
        if not hostname:
            raise ValidationError(f"Hostname не указан: {value}", field="value")

        # Проверка localhost по имени
        if hostname.lower() in ("localhost", "localhost.localdomain"):
            raise ValidationError(f"Localhost запрещён: {hostname}", field="value")

        # Если hostname — literal IP, проверить напрямую
        try:
            ip_obj = ipaddress.ip_address(hostname)
        except ValueError:
            pass  # Не IP, это домен
        else:
            # Это IP адрес, проверяем на private/loopback/link-local
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
                raise ValidationError(f"Private IP запрещён: {hostname}", field="value")

        self._value = value

    @property
    def value(self) -> str:
        return self._value

    def __str__(self) -> str:
        return self._value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, WebhookUrl):
            return NotImplemented
        return self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)


class WebhookMethod:
    """Валидированный HTTP метод для webhook.

    Разрешённые методы: GET, POST, PUT, PATCH, DELETE

    Raises:
        ValidationError: Если метод не входит в разрешённый список или не str.
    """

    ALLOWED = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})

    def __init__(self, value: str) -> None:
        if not isinstance(value, str):
            raise ValidationError(f"Method must be str, got {type(value).__name__}", field="value")

        upper = value.upper()
        if upper not in self.ALLOWED:
            raise ValidationError(f"Метод {upper} не разрешён. Разрешены: {self.ALLOWED}", field="value")
        self._value = upper

    @property
    def value(self) -> str:
        return self._value

    def __str__(self) -> str:
        return self._value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, WebhookMethod):
            return NotImplemented
        return self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)


class AppSettingValue:
    """Value Object для значения настройки приложения.

    Инкапсулирует валидацию значения настройки:
    - Может быть str или None
    - Не может быть пустой строкой

    Raises:
        ValidationError: Если значение не str/None или пустая строка.
    """

    def __init__(self, value: str | None) -> None:
        if value is not None and not isinstance(value, str):
            raise ValidationError("AppSettingValue должен быть str или None", field="value")
        if value is not None and len(value) == 0:
            raise ValidationError("AppSettingValue не может быть пустой строкой", field="value")
        self._value = value

    @property
    def value(self) -> str | None:
        return self._value

    def __str__(self) -> str:
        return self._value or ""

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AppSettingValue):
            return NotImplemented
        return self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)


class WebhookBodyTemplate:
    """Value Object для шаблона тела webhook.

    Инкапсулирует валидацию шаблона тела webhook:
    - Должен быть dict
    - Разрешены только ключи, которые передаются в контекст шаблона:
      summary, chat_id, chat_title, period_start, period_end,
      messages_count, message_thread_id

    Raises:
        ValidationError: Если шаблон не dict или содержит неизвестные ключи.
    """

    ALLOWED_KEYS = frozenset({
        "summary",
        "chat_id",
        "chat_title",
        "period_start",
        "period_end",
        "messages_count",
        "message_thread_id",
    })

    def __init__(self, template: dict[str, object]) -> None:
        if not isinstance(template, dict):
            raise ValidationError("WebhookBodyTemplate должен быть dict", field="template")

        if len(template) == 0:
            raise ValidationError("WebhookBodyTemplate не может быть пустым", field="template")

        unknown_keys = set(template.keys()) - self.ALLOWED_KEYS
        if unknown_keys:
            raise ValidationError(
                f"Неизвестное поле в шаблоне: {', '.join(sorted(unknown_keys))}",
                field="template"
            )

        self._template = template

    @property
    def template(self) -> dict[str, object]:
        return self._template

    def render(self, context: dict[str, object]) -> dict[str, object]:
        """Рендерит шаблон с подстановкой значений.

        Args:
            context: Контекст для подстановки значений.

        Returns:
            Отрендеренный шаблон с подставленными значениями.
        """
        result: dict[str, object] = {}
        for key, value in self._template.items():
            if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
                var_name = value[2:-2].strip()
                result[key] = context.get(var_name, value)
            else:
                result[key] = value
        return result

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, WebhookBodyTemplate):
            return NotImplemented
        return self._template == other._template

    def __hash__(self) -> int:
        return hash(frozenset(self._template.items()))
