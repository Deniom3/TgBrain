"""
Генератор эмбеддингов для summary.

Адаптер для делегирования генерации и сохранения эмбеддингов
с graceful degradation.
"""

import logging

from src.rag.summary_embeddings_service import SummaryEmbeddingsService

logger = logging.getLogger(__name__)


class SummaryEmbeddingGenerator:
    """Генерация и сохранение эмбеддинга summary с graceful degradation."""

    def __init__(
        self,
        embeddings_service: SummaryEmbeddingsService,
        logger: logging.Logger,
    ) -> None:
        self._embeddings_service = embeddings_service
        self._logger = logger

    async def dispatch_embedding(
        self,
        task_id: int,
        digest: str,
        model_name: str,
    ) -> bool:
        """
        Сгенерировать и сохранить эмбеддинг для summary.

        Args:
            task_id: ID задачи summary.
            digest: Текст summary для векторизации.
            model_name: Название модели эмбеддингов.

        Returns:
            True если успешно, False при ошибке (graceful degradation).
        """
        try:
            await self._embeddings_service.generate_and_save_embedding(
                task_id,
                digest,
                model_name,
            )
            return True
        except Exception as e:
            self._logger.warning(
                "Не удалось сохранить эмбеддинг для задачи %d: %s",
                task_id,
                type(e).__name__,
            )
            self._logger.debug(
                "Детали ошибки эмбеддинга: %s",
                str(e),
                exc_info=True,
            )
            return False
