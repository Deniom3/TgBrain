"""
Исключения уровня Application layer.

Модуль содержит исключения для application слоя, которые используются
для сигнализации об ошибках при выполнении use cases и сервисов.

Эти исключения оркестрируют workflow и координируют работу репозиториев.
"""

from __future__ import annotations


class ApplicationError(Exception):
    """Базовое исключение application слоя.
    
    Используется как родительский класс для всех исключений,
    возникающих в application слое.
    
    Attributes:
        message: Сообщение об ошибке.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class UseCaseError(ApplicationError):
    """Ошибка выполнения use case.
    
    Возникает при ошибке в сценарии использования, когда
    use case не может быть выполнен корректно.
    
    Attributes:
        message: Сообщение об ошибке.
        use_case_name: Имя use case (опционально).
    """

    def __init__(self, message: str, use_case_name: str | None = None) -> None:
        self.message = message
        self.use_case_name = use_case_name
        super().__init__(message)

    def __str__(self) -> str:
        if self.use_case_name:
            return f"UseCaseError(use_case={self.use_case_name!r}): {self.message}"
        return f"UseCaseError: {self.message}"


class ServiceUnavailableError(ApplicationError):
    """Сервис недоступен.
    
    Возникает когда зависимый сервис (LLM, embeddings, external API)
    недоступен или вернул ошибку.
    
    Attributes:
        message: Сообщение об ошибке.
        service_name: Имя сервиса (опционально).
    """

    def __init__(self, message: str, service_name: str | None = None) -> None:
        self.message = message
        self.service_name = service_name
        super().__init__(message)

    def __str__(self) -> str:
        if self.service_name:
            return f"ServiceUnavailableError(service={self.service_name!r}): {self.message}"
        return f"ServiceUnavailableError: {self.message}"


class DuplicateError(ApplicationError):
    """Дублирующаяся запись.
    
    Возникает при попытке создать запись, которая уже существует.
    
    Attributes:
        message: Сообщение об ошибке.
        entity_type: Тип сущности (опционально).
    """

    def __init__(self, message: str, entity_type: str | None = None) -> None:
        self.message = message
        self.entity_type = entity_type
        super().__init__(message)

    def __str__(self) -> str:
        if self.entity_type:
            return f"DuplicateError(entity={self.entity_type!r}): {self.message}"
        return f"DuplicateError: {self.message}"


class ChatNotFoundError(UseCaseError):
    """Чат не найден.
    
    Возникает когда указанный chat_id не существует в базе данных.
    """

    def __init__(self, chat_id: int) -> None:
        self.chat_id = chat_id
        super().__init__(message="Chat not found", use_case_name="AskQuestionUseCase")


class NoResultsFoundError(UseCaseError):
    """Результаты поиска не найдены.
    
    Возникает когда ни один источник не вернул релевантных результатов.
    """

    def __init__(self, question: str, search_source: str) -> None:
        self.question = question
        self.search_source = search_source
        super().__init__(
            message=f"No results found for question in {search_source}",
            use_case_name="AskQuestionUseCase",
        )


class EmbeddingGenerationError(UseCaseError):
    """Ошибка генерации эмбеддинга.
    
    Возникает когда сервис эмбеддингов недоступен или вернул ошибку.
    """

    def __init__(self, original_error: str) -> None:
        self.original_error = original_error
        super().__init__(
            message=f"Embedding generation failed: {original_error}",
            use_case_name="AskQuestionUseCase",
        )


class LLMGenerationError(UseCaseError):
    """Ошибка генерации ответа LLM.
    
    Возникает когда LLM-сервис недоступен или вернул ошибку.
    """

    def __init__(self, original_error: str) -> None:
        self.original_error = original_error
        super().__init__(
            message=f"LLM generation failed: {original_error}",
            use_case_name="AskQuestionUseCase",
        )


class DatabaseError(UseCaseError):
    """Ошибка базы данных.

    Возникает при сбое запроса к PostgreSQL.
    """

    def __init__(self, original_error: str) -> None:
        self.original_error = original_error
        super().__init__(
            message=f"Database error: {original_error}",
            use_case_name="AskQuestionUseCase",
        )


class InvalidInputError(UseCaseError):
    """Некорректные входные данные (EXT-001).

    Возникает когда входные параметры UseCase не проходят валидацию.
    """

    def __init__(self, detail: str = "Invalid input") -> None:
        super().__init__(message=detail, use_case_name="ImportMessagesUseCase")


class FileTooLargeError(UseCaseError):
    """Файл превышает допустимый размер (EXT-008).

    Возникает когда размер загружаемого файла превышает лимит 500MB.
    """

    def __init__(self, detail: str = "File too large (max 500MB)") -> None:
        super().__init__(message=detail, use_case_name="ImportMessagesUseCase")


class TooManyMessagesError(UseCaseError):
    """Превышен лимит сообщений (EXT-015).

    Возникает когда количество сообщений в файле или JSON превышает допустимый лимит.
    """

    def __init__(self, count: int = 0, max_count: int = 0) -> None:
        del count
        del max_count
        super().__init__(
            message="Too many messages in file",
            use_case_name="ImportMessagesUseCase",
        )


class AccessDeniedError(UseCaseError):
    """Нет доступа к чату (EXT-014).

    Возникает когда пользователь не имеет прав доступа к указанному чату.
    """

    def __init__(self, chat_id: int) -> None:
        self.chat_id = chat_id
        super().__init__(
            message=f"Access denied to chat {chat_id}",
            use_case_name="ImportMessagesUseCase",
        )


class TaskNotFoundError(UseCaseError):
    """Задача не найдена (EXT-013).

    Возникает когда указанная задача импорта не существует.
    """

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(
            message=f"Task not found: {task_id}",
            use_case_name="ImportMessagesUseCase",
        )
