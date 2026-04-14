"""
RAGService — Координация поиска и генерации ответов.

Использует RAGSearch для поиска по сообщениям,
ChatSummarySearchService для поиска по summary,
ContextExpander для расширения контекста,
LLMClient для генерации ответов.
"""

from .context_expander import ContextExpander, ExpandConfig, GroupConfig
from .exceptions import DatabaseQueryError, InvalidEmbeddingError, RagSearchError
from .protocols import EmbeddingGeneratorProtocol, WebhookDispatcherProtocol
from .search import RAGSearch
from .service import RAGService
from .summary_task_service import SummaryTaskService

__all__ = [
    "RAGService",
    "SummaryTaskService",
    "ContextExpander",
    "ExpandConfig",
    "GroupConfig",
    "RAGSearch",
    "RagSearchError",
    "DatabaseQueryError",
    "InvalidEmbeddingError",
    "EmbeddingGeneratorProtocol",
    "WebhookDispatcherProtocol",
]
