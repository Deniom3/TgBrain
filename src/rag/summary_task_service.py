"""
Сервис управления задачами генерации summary.

Асинхронная генерация с поддержкой кэширования и фонового выполнения.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, TYPE_CHECKING

import asyncpg

from ..config import Settings
from ..embeddings import EmbeddingsClient
from ..llm_client import LLMClient
from .summary import RAGSummary
from ..settings.repositories.chat_summary.repository import ChatSummaryRepository
from .summary_cache_helpers import calculate_cache_ttl, generate_params_hash
from .protocols import EmbeddingGeneratorProtocol, WebhookDispatcherProtocol

if TYPE_CHECKING:
    from ..rag import RAGService

logger = logging.getLogger(__name__)


class SummaryTaskService:
    """Сервис для асинхронной генерации summary."""

    MAX_CONCURRENT_TASKS = 10
    MIN_PERIOD_HOURS = 1
    MAX_PERIOD_HOURS = 2160

    def __init__(
        self,
        config: Settings,
        search: "RAGService",
        llm_client: LLMClient,
        embeddings_client: EmbeddingsClient,
        db_pool: asyncpg.Pool,
        embedding_generator: EmbeddingGeneratorProtocol,
        webhook_dispatcher: WebhookDispatcherProtocol,
    ):
        if db_pool is None:
            raise RuntimeError("db_pool не настроен")

        self._summary_repo = ChatSummaryRepository(db_pool)
        self.config = config
        self.search = search
        self.llm = llm_client
        self.embeddings = embeddings_client
        self.db_pool = db_pool

        self.rag_summary = RAGSummary(config, search.search, llm_client, db_pool=db_pool)

        # Настройки
        self.task_timeout_seconds = 300

        # Адаптеры для делегирования
        self.embedding_generator = embedding_generator
        self.webhook_dispatcher = webhook_dispatcher

    def refresh_config(self, new_settings: Settings) -> None:
        """Обновить ссылку на Settings после reload.

        Args:
            new_settings: Новый экземпляр Settings.
        """
        self.config = new_settings
        self.rag_summary.refresh_config(new_settings)
        logger.debug("SummaryTaskService обновлён")

    def get_cache_ttl(
        self,
        period_start: datetime,
        period_end: datetime,
    ) -> Optional[int]:
        """Рассчитать TTL для кэширования summary (Задача 26)."""
        return calculate_cache_ttl(period_start, period_end)

    def generate_params_hash(
        self,
        chat_id: int,
        period_start: datetime,
        period_end: datetime,
        prompt_version: str = "v1",
        model_name: Optional[str] = None,
    ) -> str:
        """Сгенерировать хеш параметров для кэширования (Задача 26)."""
        return generate_params_hash(
            chat_id, period_start, period_end,
            prompt_version=prompt_version,
            model_name=model_name,
        )


