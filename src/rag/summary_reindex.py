"""
Summary Reindex — переиндексация summary через существующий ReindexService.

Интеграция с существующим механизмом:
- Использует тот же EmbeddingsClient
- Поддерживает Smart Trigger (проверка смены модели)
- Batch processing с retry logic
- Фоновая обработка без блокировки API

Использование через существующий API:
- POST /api/v1/settings/reindex/start?include_summaries=true
- POST /api/v1/settings/reindex/schedule?include_summaries=true
"""

import asyncio
import logging
from typing import Tuple

import asyncpg

from src.embeddings import EmbeddingsClient, EmbeddingsError
from src.models.data_models import ReindexSettings
from src.reindex.repository import ReindexSettingsRepository

logger = logging.getLogger(__name__)


class SummaryBatchProcessor:
    """
    Batch-процессор для переиндексации summary.
    
    Аналогично BatchProcessor для сообщений но для таблицы chat_summaries.
    """

    def __init__(
        self,
        embeddings_client: EmbeddingsClient,
        batch_size: int = 20,
        delay_between_batches: float = 1.0,
        max_retries: int = 3,
    ):
        self.embeddings = embeddings_client
        self.batch_size = batch_size
        self.delay_between_batches = delay_between_batches
        self.max_retries = max_retries

    async def process_batch(
        self,
        pool: asyncpg.Pool,
        target_model: str,
        offset: int,
    ) -> Tuple[int, int]:
        """
        Обработать пакет summary.
        
        Args:
            pool: Пул соединений.
            target_model: Целевая модель.
            offset: Смещение.
            
        Returns:
            (success_count, failed_count)
        """
        # Получение пакета summary (только completed с непустым текстом)
        rows = await pool.fetch("""
            SELECT id, result_text FROM chat_summaries
            WHERE status = 'completed'
              AND result_text IS NOT NULL
              AND result_text != ''
              AND (embedding IS NULL OR embedding_model IS NULL OR embedding_model != $3::TEXT)
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
        """, self.batch_size, offset, target_model)
        
        if not rows:
            return 0, 0
        
        success_count = 0
        failed_count = 0
        
        # Обработка каждого summary
        for row in rows:
            # Проверка на пустой текст (дополнительная)
            if not row["result_text"] or not row["result_text"].strip():
                logger.debug(f"Summary {row['id']}: пустой текст, пропускаем")
                failed_count += 1
                continue
            
            try:
                # Генерация нового эмбеддинга
                embedding: list[float] = await self.embeddings.get_embedding(row["result_text"])
                
                # Сохранение в БД
                await pool.execute("""
                    UPDATE chat_summaries
                    SET embedding = $2::VECTOR,
                        embedding_model = $3,
                        updated_at = NOW()
                    WHERE id = $1
                """, row["id"], embedding, target_model)
                
                success_count += 1
                
            except EmbeddingsError as e:
                logger.error(f"Ошибка эмбеддинга summary {row['id']}: {e}")
                failed_count += 1
            except Exception as e:
                logger.error(f"Ошибка обработки summary {row['id']}: {e}")
                failed_count += 1
        
        # Задержка между пакетами
        if offset + self.batch_size < len(rows):
            await asyncio.sleep(self.delay_between_batches)
        
        return success_count, failed_count


async def reindex_summaries(
    pool: asyncpg.Pool,
    embeddings_client: EmbeddingsClient,
    target_model: str,
    batch_size: int = 20,
    delay_between_batches: float = 1.0,
) -> dict:
    """
    Переиндексировать все summary.
    
    Args:
        pool: Пул соединений БД.
        embeddings_client: Клиент для генерации эмбеддингов.
        target_model: Модель для генерации эмбеддингов.
        batch_size: Размер пакета.
        delay_between_batches: Задержка между пакетами.
        
    Returns:
        Статистика: {processed, failed, total}
    """
    processor = SummaryBatchProcessor(
        embeddings_client=embeddings_client,
        batch_size=batch_size,
        delay_between_batches=delay_between_batches,
    )
    
    row = await pool.fetchrow("""
        SELECT COUNT(*) as count FROM chat_summaries
        WHERE status = 'completed'
          AND result_text IS NOT NULL
          AND result_text != ''
    """)
    total = row["count"] if row else 0
    
    logger.info(f"Переиндексация {total} summary (модель: {target_model})")
    
    processed = 0
    failed = 0
    offset = 0
    
    while offset < total:
        success, fail = await processor.process_batch(pool, target_model, offset)
        processed += success
        failed += fail
        offset += batch_size
        
        logger.debug(f"Обработано {processed}/{total} summary")
    
    settings_repo = ReindexSettingsRepository(pool)
    settings = await settings_repo.get() or ReindexSettings()
    settings.last_reindex_model = target_model
    await settings_repo.upsert(settings)
    
    return {
        "processed": processed,
        "failed": failed,
        "total": total,
    }


async def check_summaries_reindex_needed(
    pool: asyncpg.Pool,
    current_model: str,
) -> Tuple[bool, int]:
    """
    Проверить необходимость переиндексации summary.

    Args:
        pool: Пул соединений БД.
        current_model: Текущая модель эмбеддингов.

    Returns:
        (needs_reindex, count)
    """
    settings_repo = ReindexSettingsRepository(pool)
    settings = await settings_repo.get()
    last_model = settings.last_reindex_model if settings else None

    if last_model is None:
        row = await pool.fetchrow(
            "SELECT COUNT(*) as count FROM chat_summaries WHERE status = 'completed' AND result_text IS NOT NULL AND result_text != '' AND LENGTH(TRIM(result_text)) > 0"
        )
        return True, row["count"] if row else 0

    if current_model == last_model:
        return False, 0

    row = await pool.fetchrow(
        "SELECT COUNT(*) as count FROM chat_summaries WHERE status = 'completed' AND result_text IS NOT NULL AND result_text != '' AND LENGTH(TRIM(result_text)) > 0 AND (embedding_model IS NULL OR embedding_model != $1)",
        current_model
    )
    return True, row["count"] if row else 0


async def generate_missing_summary_embeddings(
    pool: asyncpg.Pool,
    embeddings_client: EmbeddingsClient,
) -> dict:
    """
    Сгенерировать отсутствующие эмбеддинги для summary.
    
    Args:
        pool: Пул соединений БД.
        embeddings_client: Клиент для генерации эмбеддингов.
    
    Returns:
        Статистика: {generated, failed, total}
    """
    from src.rag.summary_embeddings_service import SummaryEmbeddingsService
    
    rows = await pool.fetch("""
        SELECT id, result_text FROM chat_summaries
        WHERE status = 'completed'
          AND result_text IS NOT NULL
          AND result_text != ''
          AND (embedding IS NULL OR embedding_model IS NULL OR embedding_model = '')
        ORDER BY created_at DESC
    """)
    
    total = len(rows)
    if total == 0:
        logger.info("Все completed summary имеют эмбеддинги")
        return {"generated": 0, "failed": 0, "total": 0}
    
    logger.info(f"Генерация {total} отсутствующих эмбеддингов")
    
    service = SummaryEmbeddingsService(embeddings_client, pool)
    generated = 0
    failed = 0
    
    for row in rows:
        try:
            if await service.generate_and_save_embedding(row["id"], row["result_text"]):
                generated += 1
            else:
                failed += 1
        except Exception as e:
            logger.error(f"Ошибка генерации эмбеддинга для summary {row['id']}: {e}")
            failed += 1
    
    return {"generated": generated, "failed": failed, "total": total}


async def get_summary_model_stats(pool: asyncpg.Pool) -> dict:
    """
    Получить статистику по моделям эмбеддингов в summary.
    
    Args:
        pool: Пул соединений БД.
    
    Returns:
        Словарь {model_name: {summary_count, first_summary, last_summary}}
    """
    rows = await pool.fetch("""
        SELECT 
            embedding_model as model_name,
            COUNT(*) as summary_count,
            MIN(created_at) as first_summary,
            MAX(created_at) as last_summary
        FROM chat_summaries
        WHERE status = 'completed'
          AND embedding IS NOT NULL
          AND embedding_model IS NOT NULL
        GROUP BY embedding_model
        ORDER BY summary_count DESC
    """)
    
    stats = {}
    for row in rows:
        stats[row["model_name"]] = {
            "summary_count": row["summary_count"],
            "first_summary": row["first_summary"],
            "last_summary": row["last_summary"],
        }
    
    return stats
