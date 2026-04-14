"""Пакет UseCase-классов для оркестрации бизнес-потоков.

Каждый UseCase зависит от протоколов (не конкретных классов)
и возвращает типизированный Result[T, E].
"""

from src.application.usecases.ask_question import (
    AskQuestionRequest,
    AskQuestionUseCase,
    AskResult,
)
from src.application.usecases.generate_summary import (
    DEFAULT_PERIOD_MINUTES,
    GenerateSummaryUseCase,
    SummaryRequest,
    SummaryTaskResult,
)
from src.application.usecases.protocols import (
    ChatAccessInfo,
    ChatExistenceChecker,
    ChatSettingsData,
    ConnectionProviderPort,
    EmbeddingDispatcherPort,
    EmbeddingGeneratorPort,
    ExternalMessageData,
    FileStoragePort,
    FileValidationPort,
    LLMGenerationPort,
    MessageFetcherPort,
    MessageIngestionPort,
    MessageRecord,
    SaveResult,
    SummaryGenerationPort,
    SummaryRecord,
    SummaryRepositoryPort,
    SummarySearchPort,
    ValidationResult,
    VectorSearchPort,
    WebhookDispatcherPort,
)
from src.application.usecases.result import Failure, Result, Success  # noqa: F401 — Success экспортируется для использования в тестах

__all__ = [
    "AskQuestionRequest",
    "AskQuestionUseCase",
    "AskResult",
    "ChatAccessInfo",
    "ChatExistenceChecker",
    "ChatSettingsData",
    "ConnectionProviderPort",
    "DEFAULT_PERIOD_MINUTES",
    "EmbeddingDispatcherPort",
    "EmbeddingGeneratorPort",
    "ExternalMessageData",
    "Failure",
    "FileStoragePort",
    "FileValidationPort",
    "GenerateSummaryUseCase",
    "LLMGenerationPort",
    "MessageFetcherPort",
    "MessageIngestionPort",
    "MessageRecord",
    "Result",
    "SaveResult",
    "SummaryGenerationPort",
    "SummaryRecord",
    "SummaryRepositoryPort",
    "SummaryRequest",
    "SummarySearchPort",
    "SummaryTaskResult",
    "ValidationResult",
    "VectorSearchPort",
    "WebhookDispatcherPort",
]
