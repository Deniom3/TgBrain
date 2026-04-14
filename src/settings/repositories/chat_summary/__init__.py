"""
Пакет для управления результатами суммаризации чатов.

✨ Используется только кэширование по params_hash через SummaryTaskService.
"""

from .repository import ChatSummaryRepository
from .utils import _row_to_chat_summary
from .search import ChatSummarySearchService

__all__ = ["ChatSummaryRepository", "_row_to_chat_summary", "ChatSummarySearchService"]
