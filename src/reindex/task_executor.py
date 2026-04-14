"""
Исполнитель задач переиндексации.

Классы:
- TaskExecutor: Выполнение задач переиндексации с миграцией размерности
"""

import asyncio
import logging
from datetime import datetime

import asyncpg

from src.embeddings import EmbeddingsClient
from src.models.data_models import ReindexSettings, ReindexTask
from src.reindex.batch_processor import BatchProcessor
from src.reindex.models import ReindexPriority, ReindexStats, ReindexStatus
from src.reindex.progress_tracker import ProgressTracker
from src.reindex.repository import (
    ReindexSettingsRepository,
    ReindexTaskRepository,
)
from src.reindex.sql_queries import SQL_GET_CURRENT_EMBEDDING_DIMENSION

logger = logging.getLogger(__name__)


async def _migrate_embedding_dimension_if_needed(
    pool: asyncpg.Pool,
    embeddings_client,
    target_model: str,
) -> None:
    """
    Проверить и выполнить миграцию размерности вектора если нужно.

    Args:
        pool: Пул соединений БД.
        embeddings_client: Клиент эмбеддингов.
        target_model: Целевая модель эмбеддинга.
    """
    import logging
    from src.reindex.sql_queries import SQL_GET_CURRENT_EMBEDDING_DIMENSION
    
    logger = logging.getLogger(__name__)
    
    try:
        # Получаем требуемую размерность от провайдера
        required_dim = embeddings_client.embedding_dim

        if not required_dim or required_dim <= 0:
            logger.warning(
                "Не удалось получить размерность эмбеддинга, пропускаем миграцию"
            )
            return

        # Получаем текущую размерность из БД
        current_dim_record = await pool.fetchrow(
            SQL_GET_CURRENT_EMBEDDING_DIMENSION
        )
        current_dim = (
            current_dim_record["current_dim"]
            if current_dim_record
            else None
        )

        logger.info(
            f"Проверка размерности: текущая={current_dim}, требуемая={required_dim}"
        )

        # Если размерности отличаются, выполняем миграцию
        if current_dim is not None and current_dim != required_dim:
            logger.info(
                f"Миграция размерности вектора: {current_dim} -> {required_dim}"
            )

            # ШАГ 1: Удаляем представление
            await pool.execute("DROP VIEW IF EXISTS v_embedding_dimension")
            logger.info(
                "Представление v_embedding_dimension удалено"
            )

            # ШАГ 2: Очищаем старые эмбеддинги в messages
            await pool.execute(
                "UPDATE messages SET embedding = NULL, embedding_model = NULL WHERE embedding IS NOT NULL"
            )
            logger.info("Старые эмбеддинги в messages очищены")

            # ШАГ 2.1: Очищаем старые эмбеддинги в chat_summaries
            await pool.execute(
                "UPDATE chat_summaries SET embedding = NULL, embedding_model = NULL WHERE embedding IS NOT NULL"
            )
            logger.info("Старые эмбеддинги в chat_summaries очищены")

            # Валидация required_dim для защиты от SQL injection
            if not isinstance(required_dim, int) or required_dim <= 0 or required_dim > 2048:
                raise ValueError(f"Invalid embedding dimension: {required_dim}")

            # ШАГ 3: Изменяем тип колонки в messages
            await pool.execute(
                f"ALTER TABLE messages ALTER COLUMN embedding TYPE VECTOR({required_dim})"
            )
            logger.info(
                f"Тип колонки embedding в messages изменён на VECTOR({required_dim})"
            )

            # ШАГ 3.1: Изменяем тип колонки в chat_summaries
            await pool.execute(
                f"ALTER TABLE chat_summaries ALTER COLUMN embedding TYPE VECTOR({required_dim})"
            )
            logger.info(
                f"Тип колонки embedding в chat_summaries изменён на VECTOR({required_dim})"
            )

            # ШАГ 4: Пересоздаём индекс HNSW
            # Временное увеличение maintenance_work_mem
            await pool.execute("SET maintenance_work_mem = '256MB'")

            # Удаление старого индекса
            await pool.execute("DROP INDEX IF EXISTS idx_embedding")

            # Создание HNSW индекса с параметрами для Ryzen 7
            await pool.execute("""
                CREATE INDEX idx_embedding
                ON messages USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 128)
            """)
            logger.info("Индекс idx_embedding (HNSW) пересоздан")

            # Сброс maintenance_work_mem
            await pool.execute("RESET maintenance_work_mem")

            # Установка ef_search для оптимальной производительности поиска
            await pool.execute("SET hnsw.ef_search = 64")

            # ШАГ 5: Восстанавливаем представление
            await pool.execute(
                """
                CREATE VIEW v_embedding_dimension AS
                SELECT 
                    COALESCE(
                        (SELECT atttypmod 
                         FROM pg_attribute 
                         WHERE attrelid = 'messages'::regclass 
                         AND attname = 'embedding'),
                        0
                    ) as embedding_dim
                """
            )
            logger.info(
                "Представление v_embedding_dimension восстановлено"
            )

            logger.info(
                f"Размерность вектора успешно изменена на {required_dim}"
            )

    except Exception as e:
        logger.error(f"Ошибка миграции размерности: {e}", exc_info=True)
        raise


class TaskExecutor:
    """
    Исполнитель задач переиндексации.

    Обрабатывает задачи из очереди с:
    - Миграцией размерности вектора
    - Batch processing
    - Progress tracking
    - Retry logic
    """

    def __init__(
        self,
        embeddings_client: EmbeddingsClient,
        settings: ReindexSettings,
        stats: ReindexStats,
        progress_tracker: ProgressTracker,
        task_repo: ReindexTaskRepository,
        settings_repo: ReindexSettingsRepository,
        db_pool: asyncpg.Pool,
    ):
        """
        Инициализация исполнителя.

        Args:
            embeddings_client: Клиент для генерации эмбеддингов.
            settings: Настройки переиндексации.
            stats: Статистика переиндексации.
            progress_tracker: Трекер прогресса.
            task_repo: Репозиторий задач переиндексации.
            settings_repo: Репозиторий настроек переиндексации.
            db_pool: Пул подключений к БД.
        """
        self._embeddings_client = embeddings_client
        self._settings = settings
        self._stats = stats
        self._progress_tracker = progress_tracker
        self._task_repo = task_repo
        self._settings_repo = settings_repo
        self._db_pool = db_pool

    async def execute_task(
        self,
        task: ReindexTask,
        running: bool,
        paused: bool,
        cancelled: bool,
    ) -> None:
        """
        Выполнить задачу переиндексации.

        Args:
            task: Задача для выполнения.
            running: Флаг работы сервиса.
            paused: Флаг приостановки.
            cancelled: Флаг отмены.
        """
        task.status = ReindexStatus.RUNNING.value
        task.started_at = datetime.now()

        await self._task_repo.save(task)

        logger.info(
            f"Начало переиндексации: {task.id} (модель: {task.target_model})"
        )

        try:
            pool = self._db_pool

            # === ШАГ 1: Проверка и миграция размерности вектора ===
            await self._migrate_embedding_dimension_if_needed(
                pool, task.target_model
            )

            # Получение общего количества
            _, total = await self._check_reindex_needed(
                pool, task.target_model
            )
            task.total_messages = total

            logger.info(
                f"Переиндексация {total} сообщений (пакеты по {task.batch_size})"
            )

            # Выбор задержки на основе приоритета
            delay = self._get_delay_for_priority(task)

            # Создание batch процессора
            processor = BatchProcessor(
                self._embeddings_client,
                batch_size=task.batch_size,
                delay_between_batches=delay,
            )

            # Events для управления
            pause_event = asyncio.Event()
            cancel_event = asyncio.Event()

            # Запуск progress tracker
            self._stats.messages_to_reindex = total
            self._stats.is_running = True
            self._progress_tracker.start(self._stats)

            last_id = 0

            while running and not paused:
                # Проверка отмены
                if cancelled or cancel_event.is_set():
                    break

                # Обработка пакета с cursor-based pagination
                success, failed, new_last_id = await processor.process_batch_cursor(
                    pool,
                    task.target_model,
                    last_id,
                    self._stats,
                    pause_event if paused else None,
                    cancel_event if cancelled else None,
                )

                if success == 0 and failed == 0:
                    break

                last_id = new_last_id

                # Обновление прогресса
                if task.total_messages > 0:
                    task.processed_count += success
                    task.failed_count += failed
                    task.progress_percent = (
                        task.processed_count / task.total_messages
                    ) * 100

                # Сохранение прогресса в БД
                await self._task_repo.update(task)

                # Обновление progress tracker
                self._progress_tracker.update(self._stats)

            task.status = ReindexStatus.COMPLETED.value
            task.completed_at = datetime.now()
            
            # Обновляем общий прогресс
            task.total_progress_percent = self._stats.total_progress_percent

            # === ШАГ 2: Фиксация last_reindex_model ===
            await self._finalize_reindex(task.target_model)

            summary_result = await self._reindex_summaries_if_needed(
                pool, task.target_model
            )
            
            # Обновляем поля summary в задаче
            task.summaries_processed_count = self._stats.summaries_reindexed_count
            task.summaries_failed_count = self._stats.summaries_failed_count
            task.summaries_progress_percent = self._stats.summaries_progress_percent
            task.total_progress_percent = self._stats.total_progress_percent

            # Завершение progress tracker
            self._progress_tracker.finish(self._stats, "completed")
            self._stats.is_running = False

            # Объединённый лог
            if summary_result and (summary_result.get("processed", 0) > 0 or summary_result.get("failed", 0) > 0):
                logger.info(
                    f"Переиндексация завершена: {task.id} | "
                    f"сообщения={task.processed_count}/{task.failed_count}, "
                    f"summary={summary_result['processed']}/{summary_result['failed']}"
                )
            else:
                logger.info(
                    f"Переиндексация завершена: {task.id} | "
                    f"успешно={task.processed_count}, ошибок={task.failed_count}"
                )

        except Exception as e:
            task.status = ReindexStatus.ERROR.value
            task.error = f"Task failed: {type(e).__name__}"
            task.completed_at = datetime.now()

            self._progress_tracker.finish(self._stats, "error")
            self._stats.is_running = False

            logger.error(f"Ошибка переиндексации {task.id}: {e}", exc_info=True)
            raise

    def _get_delay_for_priority(self, task: ReindexTask) -> float:
        """
        Получить задержку на основе приоритета.

        Args:
            task: Задача переиндексации.

        Returns:
            Задержка в секундах.
        """
        delay = task.delay_between_batches
        if delay == self._settings.delay_between_batches:
            if task.priority == ReindexPriority.LOW.value:
                delay = self._settings.low_priority_delay
            elif task.priority == ReindexPriority.HIGH.value:
                delay = self._settings.high_priority_delay
            else:
                delay = self._settings.normal_priority_delay
        return delay

    async def _migrate_embedding_dimension_if_needed(
        self, pool: asyncpg.Pool, target_model: str
    ) -> None:
        """
        Проверить и выполнить миграцию размерности вектора если нужно.

        Args:
            pool: Пул соединений БД.
            target_model: Целевая модель эмбеддинга.
        """
        try:
            # Получаем требуемую размерность от провайдера
            required_dim = self._embeddings_client.embedding_dim

            if not required_dim or required_dim <= 0:
                logger.warning(
                    "Не удалось получить размерность эмбеддинга, пропускаем миграцию"
                )
                return

            # Получаем текущую размерность из БД
            current_dim_record = await pool.fetchrow(
                SQL_GET_CURRENT_EMBEDDING_DIMENSION
            )
            current_dim = (
                current_dim_record["current_dim"]
                if current_dim_record
                else None
            )

            logger.info(
                f"Проверка размерности: текущая={current_dim}, требуемая={required_dim}"
            )

            # Если размерности отличаются, выполняем миграцию
            if current_dim is not None and current_dim != required_dim:
                logger.info(
                    f"Миграция размерности вектора: {current_dim} -> {required_dim}"
                )

                # ШАГ 1: Удаляем представление
                await pool.execute("DROP VIEW IF EXISTS v_embedding_dimension")
                logger.info(
                    "Представление v_embedding_dimension удалено"
                )

                # ШАГ 2: Очищаем старые эмбеддинги в messages
                await pool.execute(
                    "UPDATE messages SET embedding = NULL, embedding_model = NULL WHERE embedding IS NOT NULL"
                )
                logger.info("Старые эмбеддинги в messages очищены")

                # ШАГ 2.1: Очищаем старые эмбеддинги в chat_summaries
                await pool.execute(
                    "UPDATE chat_summaries SET embedding = NULL, embedding_model = NULL WHERE embedding IS NOT NULL"
                )
                logger.info("Старые эмбеддинги в chat_summaries очищены")

                # Валидация required_dim для защиты от SQL injection
                if not isinstance(required_dim, int) or required_dim <= 0 or required_dim > 2048:
                    raise ValueError(f"Invalid embedding dimension: {required_dim}")

                # ШАГ 3: Изменяем тип колонки в messages
                await pool.execute(
                    f"ALTER TABLE messages ALTER COLUMN embedding TYPE VECTOR({required_dim})"
                )
                logger.info(
                    f"Тип колонки embedding в messages изменён на VECTOR({required_dim})"
                )

                # ШАГ 3.1: Изменяем тип колонки в chat_summaries
                await pool.execute(
                    f"ALTER TABLE chat_summaries ALTER COLUMN embedding TYPE VECTOR({required_dim})"
                )
                logger.info(
                    f"Тип колонки embedding в chat_summaries изменён на VECTOR({required_dim})"
                )

                # ШАГ 4: Пересоздаём индекс HNSW
                # Временное увеличение maintenance_work_mem
                await pool.execute("SET maintenance_work_mem = '256MB'")
                
                # Удаление старого индекса
                await pool.execute("DROP INDEX IF EXISTS idx_embedding")
                
                # Создание HNSW индекса с параметрами для Ryzen 7
                await pool.execute("""
                    CREATE INDEX idx_embedding 
                    ON messages USING hnsw (embedding vector_cosine_ops)
                    WITH (m = 16, ef_construction = 128)
                """)
                logger.info("Индекс idx_embedding (HNSW) пересоздан")
                
                # Сброс maintenance_work_mem
                await pool.execute("RESET maintenance_work_mem")
                
                # Установка ef_search для оптимальной производительности поиска
                await pool.execute("SET hnsw.ef_search = 64")

                # ШАГ 5: Восстанавливаем представление
                await pool.execute(
                    """
                    CREATE VIEW v_embedding_dimension AS
                    SELECT
                        embedding_model,
                        COUNT(*) as message_count,
                        vector_dims(embedding) as dimension,
                        MIN(message_date) as first_message,
                        MAX(message_date) as last_message
                    FROM messages
                    WHERE embedding IS NOT NULL
                    GROUP BY embedding_model, vector_dims(embedding)
                    ORDER BY message_count DESC
                """
                )
                logger.info(
                    "Представление v_embedding_dimension восстановлено"
                )

                logger.info(
                    f"Размерность вектора успешно изменена на {required_dim}"
                )
            else:
                logger.info("Размерность вектора не требует изменений")

        except Exception as e:
            logger.error(f"Ошибка миграции размерности: {e}", exc_info=True)
            raise

    async def _finalize_reindex(self, target_model: str) -> None:
        """
        Завершение переиндексации: фиксация last_reindex_model.

        Args:
            target_model: Целевая модель эмбеддинга.
        """
        try:
            await self._settings_repo.set_last_reindex_model(target_model)
            logger.info(f"Зафиксирована last_reindex_model: {target_model}")

            if self._settings:
                self._settings.last_reindex_model = target_model
        except Exception as e:
            logger.error(f"Ошибка фиксации last_reindex_model: {e}")

    async def _reindex_summaries_if_needed(
        self,
        pool: asyncpg.Pool,
        target_model: str,
    ) -> dict:
        """
        Переиндексировать summary если необходимо.

        Args:
            pool: Пул соединений БД.
            target_model: Целевая модель эмбеддинга.

        Returns:
            Словарь {processed: int, failed: int}
        """
        result = {"processed": 0, "failed": 0}

        try:
            from src.rag.summary_reindex import check_summaries_reindex_needed

            needs_reindex, count = await check_summaries_reindex_needed(pool, target_model)

            if not needs_reindex:
                logger.info("Переиндексация summary не требуется (модель не изменилась)")
                return result

            if count == 0:
                logger.info("Нет completed summary для переиндексации")
                return result

            self._stats.summaries_to_reindex = count
            logger.info(f"Начало переиндексации {count} summary (модель: {target_model})")

            from src.rag.summary_reindex import SummaryBatchProcessor
            
            processor = SummaryBatchProcessor(
                embeddings_client=self._embeddings_client,
                batch_size=20,
                delay_between_batches=1.0,
            )

            offset = 0
            while offset < count:
                success, failed = await processor.process_batch(
                    pool, target_model, offset
                )
                
                if success == 0 and failed == 0:
                    break
                
                self._stats.summaries_reindexed_count += success
                self._stats.summaries_failed_count += failed
                
                self._progress_tracker.update(self._stats)
                
                result["processed"] += success
                result["failed"] += failed
                offset += processor.batch_size

            logger.info(
                f"Переиндексация summary завершена: "
                f"успешно={result['processed']}, ошибок={result['failed']}"
            )

        except ImportError:
            logger.warning("Модуль summary_reindex не найден, пропускаем переиндексацию summary")
        except Exception as e:
            logger.error(f"Ошибка переиндексации summary: {e}", exc_info=True)

        return result

    async def _check_reindex_needed(
        self, pool: asyncpg.Pool, target_model: str
    ) -> tuple[bool, int]:
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
        needs_reindex = count > 0

        logger.info(
            f"Проверка переиндексации: модель={target_model}, "
            f"сообщений для переиндексации={count}"
        )

        return needs_reindex, count
