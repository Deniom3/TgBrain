"""
Ре-экспорт из подпакета repositories для обратной совместимости.
"""

from ..repositories.chat_summary.repository import ChatSummaryRepository

__all__ = ["ChatSummaryRepository"]
