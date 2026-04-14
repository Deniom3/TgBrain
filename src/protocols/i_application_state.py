"""
Protocol IApplicationState — интерфейс состояния приложения.

Используется для dependency injection и строгой типизации app.state.
"""

from typing import Any, Optional, Protocol

from src.ingestion.saver import IMessageSaver
from src.protocols.iembeddings_client import IEmbeddingsClient
from src.protocols.illm_client import ILLMClient
from src.protocols.irag_service import IRAGService
from src.protocols.ireindex_service import IReindexService
from src.protocols.isummary_task_service import ISummaryTaskService


class IApplicationState(Protocol):
    """
    Интерфейс состояния приложения.
    
    Используется для dependency injection в сервисах
    без прямой зависимости от FastAPI app.state.
    """
    
    @property
    def db_pool(self) -> Any:
        """Пул подключений к БД."""
        ...
    
    @property
    def embeddings(self) -> IEmbeddingsClient:
        """Клиент эмбеддингов."""
        ...
    
    @property
    def llm(self) -> ILLMClient:
        """LLM клиент."""
        ...
    
    @property
    def rag(self) -> IRAGService:
        """RAG сервис."""
        ...
    
    @property
    def reindex(self) -> IReindexService:
        """Сервис переиндексации."""
        ...
    
    @property
    def rate_limiter(self) -> Optional[Any]:  # TODO: создать ITelegramRateLimiter Protocol
        """Rate limiter."""
        ...
    
    @property
    def message_saver(self) -> IMessageSaver:
        """Сервис сохранения сообщений."""
        ...
    
    @property
    def ingester(self) -> Optional[Any]:
        """Telegram ingester."""
        ...
    
    @property
    def ingestion_task(self) -> Optional[Any]:
        """Задача ingestion."""
        ...
    
    @property
    def cleanup_task(self) -> Optional[Any]:
        """Задача cleanup."""
        ...
    
    @property
    def background_tasks(self) -> set[Any]:
        """Фоновые задачи."""
        ...
    
    @property
    def summary_task_service(self) -> Optional[ISummaryTaskService]:
        """SummaryTaskService."""
        ...
    
    @property
    def summary_usecase(self) -> Any:
        """GenerateSummaryUseCase."""
        ...
    
    @property
    def import_usecase(self) -> Any:
        """ImportMessagesUseCase."""
        ...
    
    @property
    def chat_settings_repo(self) -> Any:
        """ChatSettingsRepository."""
        ...
    
    @property
    def summary_repo(self) -> Any:
        """ChatSummaryRepository."""
        ...
    
    @property
    def summary_webhook_service(self) -> Any:
        """SummaryWebhookService."""
        ...
