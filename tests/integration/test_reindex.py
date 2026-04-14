"""
Integration тесты для модуля переиндексации.

Тесты полного цикла переиндексации с реальными вызовами.
"""

import pytest
from unittest.mock import AsyncMock

from src.reindex import ReindexService
from src.embeddings import EmbeddingsClient, EmbeddingsError

pytestmark = pytest.mark.integration


class TestReindexServiceIntegration:
    """Integration тесты сервиса переиндексации."""

    @pytest.fixture
    def mock_db_pool(self):
        """Фикстура для мок-пула БД."""
        pool = AsyncMock()
        pool.fetchrow = AsyncMock(return_value=None)
        pool.fetch = AsyncMock(return_value=[])
        pool.execute = AsyncMock()
        return pool

    @pytest.fixture
    def mock_embeddings_client(self):
        """Фикстура для мок-клиента эмбеддингов."""
        client = AsyncMock(spec=EmbeddingsClient)
        client.get_model_name.return_value = "ollama/nomic-embed-text"
        client.get_embedding = AsyncMock(return_value=[0.1] * 768)
        client.provider.dimension = 768
        return client

    @pytest.fixture
    def reindex_service(self, mock_embeddings_client, mock_db_pool):
        """Фикстура для сервиса переиндексации."""
        service = ReindexService(
            embeddings_client=mock_embeddings_client,
            db_pool=mock_db_pool,
        )
        return service

    @pytest.mark.asyncio
    async def test_reindex_all_no_messages_to_reindex(self, reindex_service):
        """Тест когда нечего переиндексировать."""
        stats = await reindex_service.reindex_all()

        assert stats.is_running is False
        assert stats.reindexed_count == 0

    @pytest.mark.asyncio
    async def test_reindex_all_success(self, reindex_service):
        """Тест успешной переиндексации."""
        stats = await reindex_service.reindex_all(batch_size=10, delay_between_batches=0)

        assert stats.reindexed_count == 2
        assert stats.failed_count == 0
        assert stats.is_running is False

    @pytest.mark.asyncio
    async def test_reindex_all_with_errors(self, reindex_service):
        """Тест переиндексации с ошибками."""
        reindex_service._embeddings_client.get_embedding = AsyncMock(
            side_effect=EmbeddingsError("Test error")
        )

        stats = await reindex_service.reindex_all(batch_size=10, delay_between_batches=0)

        assert stats.reindexed_count == 0
        assert stats.failed_count == 2
        assert len(stats.errors) == 2

    @pytest.mark.asyncio
    async def test_reindex_batch(self, reindex_service, mock_db_pool):
        """Тест переиндексации одного пакета."""
        from src.reindex.batch_processor import BatchProcessor

        mock_db_pool.fetch = AsyncMock(return_value=[
            {"id": 1, "message_text": "Test 1"},
            {"id": 2, "message_text": "Test 2"},
        ])
        mock_db_pool.execute = AsyncMock()

        processor = BatchProcessor(reindex_service._embeddings_client, batch_size=100, delay_between_batches=0)
        success, failed = await processor.process_batch(
            mock_db_pool,
            "test-model",
            0,
            reindex_service._stats
        )

        assert success == 2
        assert failed == 0
