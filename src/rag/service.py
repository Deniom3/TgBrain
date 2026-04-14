"""RAGService — Координация поиска и генерации ответов."""

import logging
import time
from typing import Any, Optional, Tuple

from ..config import Settings
from ..embeddings import EmbeddingsClient
from ..llm_client import LLMClient
from ..settings.repositories.chat_summary.search import ChatSummarySearchService
from .search import RAGSearch
from .summary import RAGSummary

logger = logging.getLogger(__name__)


class RAGService:
    """
    Сервис RAG-поиска и генерации ответов.

    Предоставляет низкоуровневые операции для UseCase-адаптеров:
    - check_chat_exists — проверка существования чата
    - search.search_similar — векторный поиск сообщений
    - search.expand_search_results — расширение контекста
    - summary_search.search_summaries — поиск по summary
    """

    def __init__(
        self,
        config: Settings,
        db_pool: Any,
        embeddings_client: EmbeddingsClient,
        llm_client: LLMClient,
        prompts_dir: str = "promt",
    ) -> None:
        """
        Инициализация RAGService.

        Args:
            config: Конфигурация приложения.
            db_pool: Пул подключений к PostgreSQL.
            embeddings_client: Клиент для генерации эмбеддингов.
            llm_client: Клиент для генерации ответов.
            prompts_dir: Директория с шаблонами промптов.
        """
        self.config = config
        self.db_pool = db_pool
        self.embeddings = embeddings_client
        self.llm = llm_client
        self.prompts_dir = prompts_dir

        self.search = RAGSearch(config, db_pool)
        self.summary_search = ChatSummarySearchService(db_pool)
        self.summary_service = RAGSummary(
            config,
            self.search,
            llm_client,
            prompts_dir,
            db_pool=db_pool,
        )

        self._chat_cache: dict[int, Tuple[float, bool]] = {}
        self._cache_ttl = 300

        logger.info("RAGService инициализирован")

    @property
    def rag_summary(self) -> RAGSummary:
        """Доступ к сервису суммаризации."""
        return self.summary_service

    def refresh_config(self, new_settings: Settings) -> None:
        """Обновить ссылку на Settings после reload.

        Args:
            new_settings: Новый экземпляр Settings.
        """
        self.config = new_settings
        self.summary_service.refresh_config(new_settings)
        logger.debug("RAGService обновлён")

    async def check_chat_exists(self, chat_id: int) -> bool:
        """
        Проверка существования чата по ID с кэшированием.

        Args:
            chat_id: ID чата для проверки.

        Returns:
            True если чат существует, False иначе.

        Raises:
            asyncpg.PostgresError: При ошибке подключения к БД.
        """
        import asyncpg

        from src.models.sql import SQL_CHECK_CHAT_EXISTS

        now = time.time()
        if chat_id in self._chat_cache:
            cached_time, exists = self._chat_cache[chat_id]
            if now - cached_time < self._cache_ttl:
                return exists

        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(SQL_CHECK_CHAT_EXISTS, chat_id)
                exists = row is not None

                self._chat_cache[chat_id] = (now, exists)

                return exists
        except asyncpg.PostgresError as e:
            logger.error("Ошибка БД при проверке чата %s: %s", chat_id, e)
            raise

    async def clear_chat_cache(self) -> None:
        """Очистка кэша чатов."""
        self._chat_cache.clear()
        logger.debug("Кэш чатов очищен")

    async def summary(
        self,
        period_hours: Optional[int] = None,
        max_messages: Optional[int] = None,
    ) -> str:
        """Генерация дайджеста за период."""
        period = period_hours or self.config.summary_default_hours
        max_msgs = max_messages or self.config.summary_max_messages
        return await self.summary_service.summary(period, max_msgs)

    async def close(self) -> None:
        """Закрытие клиентов."""
        await self.embeddings.close()
        await self.llm.close()
        logger.info("RAGService закрыт")

    async def __aenter__(self) -> "RAGService":
        return self

    async def __aexit__(
        self,
        exc_type: Any,
        exc_val: Any,
        exc_tb: Any,
    ) -> None:
        await self.close()
