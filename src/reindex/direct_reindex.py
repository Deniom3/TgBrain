"""
Прямая переиндексация (без очереди).

Функции:
- reindex_all: Переиндексировать все сообщения
"""

import logging
from datetime import datetime
from typing import Callable, Optional

import asyncpg

from src.database import get_pool
from src.embeddings import EmbeddingsClient
from src.reindex.batch_processor import BatchProcessor
from src.reindex.models import ReindexStats

logger = logging.getLogger(__name__)


async def _reindex_summaries_if_needed(
    pool: asyncpg.Pool,
    embeddings_client: EmbeddingsClient,
    target_model: str,
) -> dict:
    """
    Переиндексировать summary если необходимо.
    
    Args:
        pool: Пул соединений БД.
        embeddings_client: Клиент для генерации эмбеддингов.
        target_model: Целевая модель.
    
    Returns:
        Словарь {processed: int, failed: int}
    """
    result = {"processed": 0, "failed": 0}
    
    try:
        from src.rag.summary_reindex import reindex_summaries, check_summaries_reindex_needed
        
        needs_reindex, count = await check_summaries_reindex_needed(pool, target_model)
        
        if not needs_reindex:
            logger.info("Переиндексация summary не требуется (модель не изменилась)")
            return result
        
        if count == 0:
            logger.info("Нет completed summary для переиндексации")
            return result
        
        logger.info(f"Начало переиндексации {count} summary (модель: {target_model})")
        
        reindex_result = await reindex_summaries(
            pool=pool,
            embeddings_client=embeddings_client,
            target_model=target_model,
            batch_size=20,
            delay_between_batches=1.0,
        )
        
        result = {
            "processed": reindex_result.get("processed", 0),
            "failed": reindex_result.get("failed", 0),
        }
        
        logger.info(
            f"Переиндексация summary завершена: "
            f"успешно={result['processed']}, ошибок={result['failed']}"
        )
        
    except ImportError:
        logger.warning("Модуль summary_reindex не найден, пропускаем переиндексацию summary")
    except Exception as e:
        logger.error(f"Ошибка переиндексации summary: {e}", exc_info=True)
    
    return result


async def reindex_all(
    embeddings_client: EmbeddingsClient,
    stats: ReindexStats,
    batch_size: int = 100,
    delay_between_batches: float = 0.5,
    progress_callback: Optional[Callable[[ReindexStats], None]] = None,
) -> ReindexStats:
    """
    Переиндексировать все сообщения с текущей моделью.

    Args:
        embeddings_client: Клиент для генерации эмбеддингов.
        stats: Статистика переиндексации.
        batch_size: Размер пакета.
        delay_between_batches: Задержка между пакетами.
        progress_callback: Функция обратного вызова для прогресса.

    Returns:
        Статистика переиндексации.

    Raises:
        RuntimeError: Если переиндексация уже запущена.
        ValueError: Если не установлен клиент эмбеддингов.
    """
    if stats.is_running:
        raise RuntimeError("Переиндексация уже запущена")

    if not embeddings_client:
        raise ValueError("Не установлен embeddings_client")

    stats.is_running = True
    stats.started_at = datetime.now()
    stats.reindexed_count = 0
    stats.failed_count = 0
    stats.errors = []
    stats.current_model = embeddings_client.get_model_name()

    logger.info(f"Начало переиндексации: модель={stats.current_model}")

    summary_result = {"processed": 0, "failed": 0}

    try:
        pool = await get_pool()

        from src.reindex.task_executor import _migrate_embedding_dimension_if_needed
        await _migrate_embedding_dimension_if_needed(pool, embeddings_client, stats.current_model)

        total_record = await pool.fetchrow("SELECT COUNT(*) as count FROM messages")
        stats.total_messages = total_record["count"] if total_record else 0

        needs_reindex, count = await _check_reindex_needed(
            pool, stats.current_model
        )
        stats.messages_to_reindex = count

        if not needs_reindex:
            logger.info("Переиндексация сообщений не требуется")
        else:
            logger.info(f"Переиндексация {count} сообщений (пакеты по {batch_size})")

            processor = BatchProcessor(
                embeddings_client,
                batch_size=batch_size,
                delay_between_batches=delay_between_batches,
            )

            await processor.process_all(
                pool,
                stats.current_model,
                stats,
                progress_callback,
            )

        summary_result = await _reindex_summaries_if_needed(
            pool, embeddings_client, stats.current_model
        )

    except Exception as e:
        logger.error(f"Ошибка переиндексации: {e}", exc_info=True)
        stats.errors.append(f"Critical error: {str(e)}")
        raise

    finally:
        stats.completed_at = datetime.now()
        stats.is_running = False

        # Объединённый лог
        if summary_result["processed"] > 0 or summary_result["failed"] > 0:
            logger.info(
                f"Переиндексация завершена: "
                f"сообщения={stats.reindexed_count}/{stats.failed_count}, "
                f"summary={summary_result['processed']}/{summary_result['failed']}, "
                f"время={stats.elapsed_seconds:.2f}с"
            )
        else:
            logger.info(
                f"Переиндексация завершена: "
                f"успешно={stats.reindexed_count}, "
                f"ошибок={stats.failed_count}, "
                f"время={stats.elapsed_seconds:.2f}с"
            )

    return stats


async def _check_reindex_needed(pool, target_model: str) -> tuple[bool, int]:
    """
    Проверить необходимость переиндексации.

    Args:
        pool: Пул соединений БД.
        target_model: Целевая модель эмбеддинга.

    Returns:
        Кортеж (необходима_ли переиндексация, количество сообщений).
    """
    record = await pool.fetchrow(
        "SELECT COUNT(*) as count FROM messages WHERE embedding IS NULL OR embedding_model != $1::TEXT",
        target_model,
    )

    count = record["count"] if record else 0
    return count > 0, count
