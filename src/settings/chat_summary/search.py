"""
Ре-экспорт из подпакета repositories для обратной совместимости.
"""

from ..repositories.chat_summary.search import ChatSummarySearchService

__all__ = ["ChatSummarySearchService"]
