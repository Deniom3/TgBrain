"""Protocol интерфейсы для dependency injection."""
from .i_application_state import IApplicationState
from .iembeddings_client import IEmbeddingsClient
from .illm_client import ILLMClient
from .irag_service import IRAGService
from .ireindex_service import IReindexService
from .isummary_task_service import ISummaryTaskService
from .isummary_webhook_service import ISummaryWebhookService

__all__ = [
    "IApplicationState",
    "IEmbeddingsClient",
    "ILLMClient",
    "IRAGService",
    "IReindexService",
    "ISummaryTaskService",
    "ISummaryWebhookService",
]
