"""
Исключения уровня Domain layer.

Модуль содержит базовые исключения для domain слоя, которые используются
для сигнализации о нарушении бизнес-правил, инвариантов и валидации.

Эти исключения не зависят от фреймворков и инфраструктуры.
"""

from __future__ import annotations


class DomainError(Exception):
    """Базовое исключение domain слоя.
    
    Используется как родительский класс для всех исключений,
    возникающих в domain слое при нарушении бизнес-правил.
    
    Attributes:
        message: Сообщение об ошибке.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class ValidationError(DomainError):
    """Ошибка валидации domain объекта.
    
    Возникает при нарушении инвариантов Value Objects или Entity.
    
    Attributes:
        message: Сообщение об ошибке.
        field: Имя поля, которое не прошло валидацию (опционально).
    """

    def __init__(self, message: str, field: str | None = None) -> None:
        self.message = message
        self.field = field
        super().__init__(message)

    def __str__(self) -> str:
        if self.field:
            return f"ValidationError(field={self.field!r}): {self.message}"
        return f"ValidationError: {self.message}"


class BusinessRuleError(DomainError):
    """Нарушение бизнес-правила.
    
    Возникает при попытке выполнить действие, которое нарушает
    бизнес-правила предметной области.
    
    Attributes:
        message: Сообщение об ошибке.
        rule_code: Код нарушенного правила (опционально).
    """

    def __init__(self, message: str, rule_code: str | None = None) -> None:
        self.message = message
        self.rule_code = rule_code
        super().__init__(message)

    def __str__(self) -> str:
        if self.rule_code:
            return f"BusinessRuleError(code={self.rule_code!r}): {self.message}"
        return f"BusinessRuleError: {self.message}"


class NotFoundError(DomainError):
    """Объект не найден.
    
    Возникает при попытке получить объект, который не существует.
    
    Attributes:
        entity_type: Тип сущности (например, "Chat", "Message").
        identifier: Идентификатор, по которому искали объект (не включается в сообщение для безопасности).
    """

    def __init__(self, entity_type: str, identifier: str) -> None:
        self.entity_type = entity_type
        self.identifier = identifier
        message = f"{entity_type} не найден"
        super().__init__(message)

    def __str__(self) -> str:
        return f"NotFoundError(entity={self.entity_type!r})"


class WebhookNotFoundError(DomainError):
    """Webhook-конфигурация для чата не найдена.
    
    Код ошибки: WHK-001.
    
    Attributes:
        chat_id: Идентификатор чата.
    """

    code = "WHK-001"

    def __init__(self, chat_id: int) -> None:
        self.chat_id = chat_id
        message = f"Чат {chat_id} не найден"
        super().__init__(message)

    def __str__(self) -> str:
        return f"WebhookNotFoundError(code={self.code!r}, chat_id={self.chat_id})"


class WebhookNotConfiguredError(DomainError):
    """Webhook не настроен для данного чата.
    
    Код ошибки: WHK-006.
    
    Attributes:
        chat_id: Идентификатор чата.
    """

    code = "WHK-006"

    def __init__(self, chat_id: int) -> None:
        self.chat_id = chat_id
        super().__init__("Webhook не настроен")

    def __str__(self) -> str:
        return f"WebhookNotConfiguredError(code={self.code!r}, chat_id={self.chat_id})"


class WebhookGenerationError(DomainError):
    """Ошибка генерации summary для webhook.
    
    Код ошибки: WHK-007.
    """

    code = "WHK-007"

    def __init__(self) -> None:
        super().__init__("Ошибка генерации summary")

    def __str__(self) -> str:
        return f"WebhookGenerationError(code={self.code!r})"
