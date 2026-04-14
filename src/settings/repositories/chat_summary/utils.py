"""
Chat Summary Repository — вспомогательные функции.
"""

import json
import logging

from ....models.data_models import ChatSummary, SummaryStatus

logger = logging.getLogger(__name__)


def _row_to_chat_summary(row: dict) -> ChatSummary:
    """Конвертировать строку БД в ChatSummary."""
    # Десериализуем metadata из JSON
    metadata = row.get("metadata")
    if isinstance(metadata, str):
        metadata = json.loads(metadata)

    # Определяем статус
    status_str = row.get("status", "pending")
    status = SummaryStatus(status_str) if status_str else SummaryStatus.PENDING

    return ChatSummary(
        id=row["id"],
        chat_id=row["chat_id"],
        created_at=row["created_at"],
        period_start=row["period_start"],
        period_end=row["period_end"],
        result_text=row.get("result_text", "") or "",
        messages_count=row.get("messages_count", 0),
        embedding=row.get("embedding"),
        embedding_model=row.get("embedding_model"),
        generated_by=row.get("generated_by", "llm"),
        metadata=metadata,
        status=status,
        params_hash=row.get("params_hash"),
        updated_at=row.get("updated_at"),
    )


__all__ = ["_row_to_chat_summary"]
