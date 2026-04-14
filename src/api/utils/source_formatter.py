"""Форматирование источников для API ответа."""
import html
from typing import List, Any

from src.api.models import AskSource


def format_sources_to_ask_sources(
    sources: List[Any],
    metadata: dict,
) -> List[AskSource]:
    """Конвертация источников из UseCase результата в AskSource модели.

    Args:
        sources: Список источников (MessageRecord, SummaryRecord или MergedResult)
        metadata: Метаданные поиска

    Returns:
        Список AskSource моделей
    """
    from src.models.data_models import MessageRecord, SummaryRecord, MergedResult

    result = []

    for source in sources:
        if isinstance(source, MergedResult):
            if source.source_type == "message":
                msg: MessageRecord = source.message  # type: ignore[assignment]
                result.append(
                    AskSource(
                        id=msg.id,
                        type="message",
                        text=html.escape(str(msg.text)),
                        date=msg.date.isoformat(),
                        chat_title=html.escape(str(msg.chat_title)),
                        link=msg.link,
                        similarity_score=round(msg.similarity_score, 3),
                        is_expanded=metadata.get("is_expanded", False),
                        grouped_count=metadata.get("grouped_count", 1),
                    )
                )
            else:
                summ: SummaryRecord = source.message  # type: ignore[assignment]
                result.append(
                    AskSource(
                        id=summ.id,
                        type="summary",
                        text=html.escape(summ.result_text),
                        date=summ.created_at.isoformat() if summ.created_at else "",
                        chat_title=html.escape(str(summ.chat_title)),
                        link=None,
                        similarity_score=round(summ.similarity_score, 3),
                        is_expanded=False,
                        grouped_count=1,
                    )
                )
        elif isinstance(source, MessageRecord):
            result.append(
                AskSource(
                    id=source.id,
                    type="message",
                    text=html.escape(str(source.text)),
                    date=source.date.isoformat(),
                    chat_title=html.escape(str(source.chat_title)),
                    link=source.link,
                    similarity_score=round(source.similarity_score, 3),
                    is_expanded=metadata.get("is_expanded", False),
                    grouped_count=metadata.get("grouped_count", 1),
                )
            )
        elif isinstance(source, SummaryRecord):
            result.append(
                AskSource(
                    id=source.id,
                    type="summary",
                    text=html.escape(source.result_text),
                    date=source.created_at.isoformat() if source.created_at else "",
                    chat_title=html.escape(str(source.chat_title)),
                    link=None,
                    similarity_score=round(source.similarity_score, 3),
                    is_expanded=False,
                    grouped_count=1,
                )
            )

    return result
