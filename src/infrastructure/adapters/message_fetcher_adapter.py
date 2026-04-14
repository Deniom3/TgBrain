"""Адаптеры infrastructure-компонентов к портам application слоя."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.application.usecases.protocols import MessageFetcherPort
from src.models.data_models import MessageRecord

if TYPE_CHECKING:
    from src.rag.search import RAGSearch


class RAGSearchMessageFetcherAdapter(MessageFetcherPort):
    """Адаптирует RAGSearch под интерфейс MessageFetcherPort."""

    def __init__(self, rag_search: RAGSearch) -> None:
        self._rag_search = rag_search

    async def get_messages_by_period(
        self,
        chat_id: int,
        period_hours: float,
        max_messages: int,
    ) -> list[MessageRecord]:
        """Делегирует вызов к RAGSearch с period_hours."""
        return await self._rag_search.get_messages_by_period(
            period_hours=int(period_hours),
            max_messages=max_messages,
            chat_id=chat_id,
        )
