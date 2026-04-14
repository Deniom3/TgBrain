"""
Batch-процессор для переиндексации.

Обработка сообщений пакетами с:
- Retry logic при ошибках
- Progress tracking после каждого batch'а
- Поддержкой приостановки/возобновления
"""

import asyncio
import logging
from typing import Callable, Optional, Tuple

import asyncpg

from src.embeddings import EmbeddingsClient, EmbeddingsError
from src.reindex.models import ReindexStats
from src.reindex.sql_queries import (
    SQL_GET_MESSAGES_FOR_REINDEX,
    SQL_UPDATE_MESSAGE_EMBEDDING_WITH_MODEL,
)

logger = logging.getLogger(__name__)


class BatchProcessor:
    """
    Процессор пакетной обработки сообщений.

    Особенности:
    - Обработка порциями (batch processing)
    - Auto-retry при ошибках эмбеддингов
    - Progress tracking после каждого batch'а
    - Поддержка приостановки/возобновления
    """

    def __init__(
        self,
        embeddings_client: EmbeddingsClient,
        batch_size: int = 100,
        delay_between_batches: float = 0.5,
        max_retries: int = 3,
    ):
        """
        Инициализация процессора.

        Args:
            embeddings_client: Клиент для генерации эмбеддингов.
            batch_size: Размер пакета.
            delay_between_batches: Задержка между пакетами (секунды).
            max_retries: Максимальное количество попыток при ошибке.
        """
        self._embeddings_client = embeddings_client
        self._batch_size = batch_size
        self._delay_between_batches = delay_between_batches
        self._max_retries = max_retries

    async def process_batch(
        self,
        pool: asyncpg.Pool,
        target_model: str,
        offset: int,
        stats: ReindexStats,
        pause_event: Optional[asyncio.Event] = None,
        cancel_event: Optional[asyncio.Event] = None,
    ) -> Tuple[int, int]:
        """
        Обработать пакет сообщений.

        Args:
            pool: Пул соединений БД.
            target_model: Целевая модель эмбеддинга.
            offset: Смещение для выборки.
            stats: Статистика переиндексации.
            pause_event: Event для приостановки.
            cancel_event: Event для отмены.

        Returns:
            Кортеж (успешно обработано, failed count).
        """
        # Проверка приостановки
        if pause_event and pause_event.is_set():
            logger.debug("Обработка приостановлена")
            return 0, 0

        # Проверка отмены
        if cancel_event and cancel_event.is_set():
            logger.info("Обработка отменена")
            return 0, 0

        # Получение пакета сообщений
        messages = await pool.fetch(
            SQL_GET_MESSAGES_FOR_REINDEX,
            target_model,
            self._batch_size,
            offset,
        )

        if not messages:
            return 0, 0

        success_count = 0
        failed_count = 0

        # Обработка каждого сообщения в пакете
        for record in messages:
            # Проверка приостановки/отмены в процессе обработки
            if pause_event and pause_event.is_set():
                break
            if cancel_event and cancel_event.is_set():
                break

            try:
                # Генерация эмбеддинга с retry logic
                embedding = await self._generate_with_retry(
                    record["message_text"],
                    record["id"],
                )

                # Сохранение в БД (asyncpg требует строковое представление вектора)
                embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
                await pool.execute(
                    SQL_UPDATE_MESSAGE_EMBEDDING_WITH_MODEL,
                    record["id"],
                    embedding_str,
                    target_model,
                )

                success_count += 1

            except EmbeddingsError as e:
                logger.warning(
                    f"Ошибка переиндексации {record['id']}: {e}"
                )
                failed_count += 1
                stats.errors.append(f"Message {record['id']}: {str(e)}")

            except Exception as e:
                logger.error(
                    f"Неожиданная ошибка переиндексации {record['id']}: {e}",
                    exc_info=True,
                )
                failed_count += 1
                stats.errors.append(f"Message {record['id']}: {str(e)}")

        # Обновление статистики
        stats.reindexed_count += success_count
        stats.failed_count += failed_count

        # Задержка между пакетами
        if self._delay_between_batches > 0 and messages:
            await asyncio.sleep(self._delay_between_batches)

        return success_count, failed_count

    async def _generate_with_retry(
        self,
        text: str,
        message_id: int,
    ) -> list[float]:
        """
        Сгенерировать эмбеддинг с повторными попытками.

        Args:
            text: Текст сообщения.
            message_id: ID сообщения.

        Returns:
            Вектор эмбеддинга.

        Raises:
            EmbeddingsError: Если все попытки исчерпаны.
        """
        last_error: Optional[Exception] = None

        for attempt in range(self._max_retries):
            try:
                embedding = await self._embeddings_client.get_embedding(text)
                return embedding

            except EmbeddingsError as e:
                last_error = e
                if attempt < self._max_retries - 1:
                    wait_time = 2 ** attempt  # Экспоненциальная задержка
                    logger.warning(
                        f"Попытка {attempt + 1}/{self._max_retries} для сообщения {message_id}: {e}. "
                        f"Повтор через {wait_time}с"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    raise

            except Exception as e:
                last_error = e
                if attempt < self._max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(
                        f"Попытка {attempt + 1}/{self._max_retries} для сообщения {message_id}: {e}. "
                        f"Повтор через {wait_time}с"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    raise EmbeddingsError(f"Все попытки исчерпаны: {str(e)}")

        # Должно быть выброшено в цикле, но на всякий случай
        raise EmbeddingsError(f"Все попытки исчерпаны: {str(last_error)}")

    async def process_all(
        self,
        pool: asyncpg.Pool,
        target_model: str,
        stats: ReindexStats,
        progress_callback: Optional[Callable[[ReindexStats], None]] = None,
        pause_event: Optional[asyncio.Event] = None,
        cancel_event: Optional[asyncio.Event] = None,
    ) -> ReindexStats:
        """
        Обработать все сообщения.

        Использует cursor-based pagination (WHERE id > last_id) вместо
        offset-based, так как при реиндексации сообщения обновляются и
        выпадают из выборки, что ломает offset.

        Args:
            pool: Пул соединений БД.
            target_model: Целевая модель эмбеддинга.
            stats: Статистика переиндексации.
            progress_callback: Функция обратного вызова для прогресса.
            pause_event: Event для приостановки.
            cancel_event: Event для отмены.

        Returns:
            Обновлённая статистика.
        """
        last_id = 0

        while True:
            # Проверка отмены
            if cancel_event and cancel_event.is_set():
                logger.info("Обработка отменена")
                break

            # Проверка приостановки
            if pause_event and pause_event.is_set():
                logger.debug("Обработка приостановлена")
                await asyncio.sleep(1)
                continue

            # Обработка пакета с cursor-based pagination
            success, failed, new_last_id = await self.process_batch_cursor(
                pool,
                target_model,
                last_id,
                stats,
                pause_event,
                cancel_event,
            )

            # Если сообщений не осталось, завершаем
            if success == 0 and failed == 0:
                break

            last_id = new_last_id

            # Обновление прогресса
            if progress_callback:
                progress_callback(stats)

        return stats

    async def process_batch_cursor(
        self,
        pool: asyncpg.Pool,
        target_model: str,
        last_id: int,
        stats: ReindexStats,
        pause_event: Optional[asyncio.Event] = None,
        cancel_event: Optional[asyncio.Event] = None,
    ) -> Tuple[int, int, int]:
        """
        Обработать пакет сообщений с cursor-based pagination.

        Args:
            pool: Пул соединений БД.
            target_model: Целевая модель эмбеддинга.
            last_id: Последний обработанный ID (cursor).
            stats: Статистика переиндексации.
            pause_event: Event для приостановки.
            cancel_event: Event для отмены.

        Returns:
            Кортеж (успешно, failed, new_last_id).
        """
        # Проверка приостановки
        if pause_event and pause_event.is_set():
            logger.debug("Обработка приостановлена")
            return 0, 0, last_id

        # Проверка отмены
        if cancel_event and cancel_event.is_set():
            logger.info("Обработка отменена")
            return 0, 0, last_id

        # Получение пакета сообщений (cursor-based: WHERE id > last_id)
        messages = await pool.fetch(
            """
            SELECT id, message_text
            FROM messages
            WHERE id > $1
              AND (embedding IS NULL OR embedding_model IS NULL OR embedding_model != $2::TEXT)
            ORDER BY id
            LIMIT $3
            """,
            last_id,
            target_model,
            self._batch_size,
        )

        if not messages:
            return 0, 0, last_id

        success_count = 0
        failed_count = 0
        new_last_id = last_id

        # Обработка каждого сообщения в пакете
        for record in messages:
            # Проверка приостановки/отмены в процессе обработки
            if pause_event and pause_event.is_set():
                break
            if cancel_event and cancel_event.is_set():
                break

            try:
                # Генерация эмбеддинга с retry logic
                embedding = await self._generate_with_retry(
                    record["message_text"],
                    record["id"],
                )

                # Сохранение в БД (asyncpg требует строковое представление вектора)
                embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
                await pool.execute(
                    SQL_UPDATE_MESSAGE_EMBEDDING_WITH_MODEL,
                    record["id"],
                    embedding_str,
                    target_model,
                )

                success_count += 1
                new_last_id = record["id"]

            except EmbeddingsError as e:
                logger.warning(
                    f"Ошибка переиндексации {record['id']}: {e}"
                )
                failed_count += 1
                stats.errors.append(f"Message {record['id']}: {str(e)}")
                new_last_id = record["id"]

            except Exception as e:
                logger.error(
                    f"Неожиданная ошибка переиндексации {record['id']}: {e}",
                    exc_info=True,
                )
                failed_count += 1
                stats.errors.append(f"Message {record['id']}: {str(e)}")
                new_last_id = record["id"]

        # Обновление статистики
        stats.reindexed_count += success_count
        stats.failed_count += failed_count

        # Задержка между пакетами
        if self._delay_between_batches > 0 and messages:
            await asyncio.sleep(self._delay_between_batches)

        return success_count, failed_count, new_last_id
