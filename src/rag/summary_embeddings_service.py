"""
Summary Embeddings Service — векторизация и сохранение эмбеддингов для summary.

Аналогично MessageIngester но для summary:
- Генерация эмбеддингов для result_text
- Сохранение в БД (колонка embedding в chat_summaries)
- Поддержка batch обработки
- Интеграция с существующим EmbeddingsClient
"""

import logging
from typing import Optional

import asyncpg

from src.embeddings import EmbeddingsClient, EmbeddingsError

logger = logging.getLogger(__name__)


class SummaryEmbeddingsService:
    """
    Сервис для генерации и сохранения эмбеддингов summary.
    
    Использование:
        service = SummaryEmbeddingsService(embeddings_client, db_pool)
        await service.generate_and_save_embedding(summary_id, summary_text)
    """

    def __init__(self, embeddings_client: EmbeddingsClient, db_pool: asyncpg.Pool):
        """
        Инициализация сервиса.
        
        Args:
            embeddings_client: Клиент для генерации эмбеддингов.
            db_pool: Пул соединений БД.
        """
        self.embeddings = embeddings_client
        self.db_pool = db_pool
        logger.info("SummaryEmbeddingsService инициализирован")

    async def generate_and_save_embedding(
        self,
        summary_id: int,
        summary_text: str,
        embedding_model: Optional[str] = None,
    ) -> bool:
        """
        Сгенерировать эмбеддинг и сохранить в БД.
        
        Args:
            summary_id: ID summary в БД.
            summary_text: Текст summary для векторизации.
            embedding_model: Название модели (опционально).
            
        Returns:
            True если успешно, False если ошибка.
        """
        if not summary_text or not summary_text.strip():
            logger.warning(f"Summary {summary_id}: пустой текст для эмбеддинга")
            return False

        try:
            # Генерация эмбеддинга
            embedding = await self.embeddings.get_embedding(summary_text)
            
            if not embedding_model:
                embedding_model = self.embeddings.get_model_name()
            
            # Сохранение в БД
            await self._save_embedding_to_db(summary_id, embedding, embedding_model)
            
            logger.info(f"Summary {summary_id}: эмбеддинг сгенерирован и сохранён ({len(embedding)} dim, модель: {embedding_model})")
            return True
            
        except EmbeddingsError as e:
            logger.error(f"Summary {summary_id}: ошибка генерации эмбеддинга: {e}")
            return False
        except Exception as e:
            logger.error(f"Summary {summary_id}: неожиданная ошибка: {e}", exc_info=True)
            return False

    async def _save_embedding_to_db(
        self,
        summary_id: int,
        embedding: list[float],
        embedding_model: str,
    ) -> None:
        """
        Сохранить эмбеддинг в БД.
        
        Args:
            summary_id: ID summary.
            embedding: Вектор эмбеддинга.
            embedding_model: Название модели.
        """
        await self.db_pool.execute("""
            UPDATE chat_summaries
            SET embedding = $2::VECTOR,
                embedding_model = $3,
                updated_at = NOW()
            WHERE id = $1
        """, summary_id, embedding, embedding_model)
        
        logger.debug(f"Summary {summary_id}: эмбеддинг сохранён в БД")

    async def generate_batch_embeddings(
        self,
        summary_ids: list[int],
        summary_texts: list[str],
        embedding_model: Optional[str] = None,
    ) -> int:
        """
        Сгенерировать эмбеддинги для пакета summary.
        
        Args:
            summary_ids: Список ID summary.
            summary_texts: Список текстов summary.
            embedding_model: Название модели (опционально).
            
        Returns:
            Количество успешно обработанных summary.
        """
        if not embedding_model:
            embedding_model = self.embeddings.get_model_name()
        
        success_count = 0
        
        for summary_id, summary_text in zip(summary_ids, summary_texts):
            if await self.generate_and_save_embedding(summary_id, summary_text, embedding_model):
                success_count += 1
        
        return success_count

    async def reindex_summary_embedding(
        self,
        summary_id: int,
        new_model: str,
    ) -> bool:
        """
        Перегенерировать эмбеддинг с новой моделью (реиндексация).
        
        Args:
            summary_id: ID summary.
            new_model: Новая модель для генерации.
            
        Returns:
            True если успешно.
        """
        row = await self.db_pool.fetchrow("""
            SELECT id, result_text FROM chat_summaries
            WHERE id = $1 AND status = 'completed'
        """, summary_id)
        
        if not row or not row["result_text"]:
            logger.warning(f"Summary {summary_id}: не найдено или пустой текст")
            return False
        
        logger.info(f"Summary {summary_id}: перегенерация эмбеддинга (модель: {new_model})")
        
        return await self.generate_and_save_embedding(
            summary_id,
            row["result_text"],
            new_model,
        )
