"""
Исключения уровня Infrastructure layer.

Модуль содержит исключения для infrastructure слоя, которые используются
для сигнализации об ошибках при работе с внешними системами:
базы данных, файловые хранилища, внешние API.
"""

from __future__ import annotations


class InfrastructureError(Exception):
    """Базовое исключение infrastructure слоя.
    
    Используется как родительский класс для всех исключений,
    возникающих в infrastructure слое.
    
    Attributes:
        message: Сообщение об ошибке.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class DatabaseError(InfrastructureError):
    """Ошибка базы данных.
    
    Возникает при ошибках выполнения SQL запросов,
    проблем с подключением или транзакциями.
    
    Attributes:
        message: Сообщение об ошибке.
        query: SQL запрос (опционально).
    """

    def __init__(self, message: str, query: str | None = None) -> None:
        self.message = message
        self.query = query
        super().__init__(message)

    def __str__(self) -> str:
        if self.query:
            return f"DatabaseError(query={self.query!r}): {self.message}"
        return f"DatabaseError: {self.message}"


class ExternalServiceError(InfrastructureError):
    """Ошибка внешнего сервиса.
    
    Возникает при ошибках взаимодействия с внешними API:
    Telegram API, LLM провайдеры, embedding сервисы.
    
    Attributes:
        message: Сообщение об ошибке.
        service_name: Имя внешнего сервиса (опционально).
        status_code: HTTP статус код (опционально).
    """

    def __init__(
        self,
        message: str,
        service_name: str | None = None,
        status_code: int | None = None,
    ) -> None:
        self.message = message
        self.service_name = service_name
        self.status_code = status_code
        super().__init__(message)

    def __str__(self) -> str:
        parts = []
        if self.service_name:
            parts.append(f"service={self.service_name!r}")
        if self.status_code:
            parts.append(f"status={self.status_code}")
        context = f"({', '.join(parts)})" if parts else ""
        return f"ExternalServiceError{context}: {self.message}"


class FileStorageError(InfrastructureError):
    """Ошибка файлового хранилища.
    
    Возникает при ошибках чтения/записи файлов,
    проблем с правами доступа или местом на диске.
    
    Attributes:
        message: Сообщение об ошибке.
        file_path: Путь к файлу (опционально).
    """

    def __init__(self, message: str, file_path: str | None = None) -> None:
        self.message = message
        self.file_path = file_path
        super().__init__(message)

    def __str__(self) -> str:
        if self.file_path:
            return f"FileStorageError(path={self.file_path!r}): {self.message}"
        return f"FileStorageError: {self.message}"


class SessionNotConfiguredError(InfrastructureError):
    """Сессия Telegram не настроена (session_data отсутствует)."""

    def __init__(self) -> None:
        super().__init__("Сессия Telegram не настроена")


class SessionNotAuthorizedError(InfrastructureError):
    """Сессия Telegram не авторизована."""

    def __init__(self) -> None:
        super().__init__("Сессия Telegram не авторизована")


class SessionDecryptionError(InfrastructureError):
    """Ошибка расшифровки сессии Telegram (APP-108)."""

    def __init__(self) -> None:
        super().__init__("Ошибка расшифровки сессии Telegram")
