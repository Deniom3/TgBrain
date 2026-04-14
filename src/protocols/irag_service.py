"""Protocol интерфейс для RAG сервиса."""

from typing import TYPE_CHECKING, Optional, Protocol, runtime_checkable

if TYPE_CHECKING:
    from src.rag.summary import RAGSummary


@runtime_checkable
class IRAGService(Protocol):
    """Интерфейс RAG сервиса."""

    async def check_chat_exists(self, chat_id: int) -> bool: ...
    async def clear_chat_cache(self) -> None: ...
    async def summary(
        self,
        period_hours: Optional[int] = None,
        max_messages: Optional[int] = None,
    ) -> str: ...
    async def close(self) -> None: ...

    @property
    def rag_summary(self) -> "RAGSummary": ...
