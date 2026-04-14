"""
Тесты для модуля переиндексации.

Проверяют:
- Подсчёт сообщений для переиндексации
- Статистику по моделям эмбеддингов
- Порционную обработку
- Отслеживание прогресса
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock

from src.reindex import ReindexService, ReindexStats, EmbeddingModelStats
from src.embeddings import EmbeddingsClient


class TestReindexStats:
    """Тесты для модели статистики переиндексации."""

    def test_default_values(self):
        """Тест значений по умолчанию."""
        stats = ReindexStats()
        
        assert stats.total_messages == 0
        assert stats.messages_to_reindex == 0
        assert stats.reindexed_count == 0
        assert stats.failed_count == 0
        assert stats.started_at is None
        assert stats.completed_at is None
        assert stats.current_model == ""
        assert stats.is_running is False
        assert stats.errors == []

    def test_progress_percent_zero_division(self):
        """Тест деления на ноль в progress_percent."""
        stats = ReindexStats()
        assert stats.progress_percent == 100.0

    def test_progress_percent_calculation(self):
        """Тест расчёта процента выполнения."""
        stats = ReindexStats(
            messages_to_reindex=100,
            reindexed_count=50
        )
        assert stats.progress_percent == 50.0

    def test_elapsed_seconds_no_start(self):
        """Тест elapsed_seconds без started_at."""
        stats = ReindexStats()
        assert stats.elapsed_seconds == 0.0

    def test_to_dict(self):
        """Тест преобразования в словарь."""
        stats = ReindexStats(
            total_messages=1000,
            messages_to_reindex=500,
            reindexed_count=250,
            failed_count=5,
            current_model="ollama/nomic-embed-text",
            is_running=True,
            errors=["error1", "error2"]
        )
        
        result = stats.to_dict()
        
        assert result["total_messages"] == 1000
        assert result["messages_to_reindex"] == 500
        assert result["reindexed_count"] == 250
        assert result["failed_count"] == 5
        assert result["progress_percent"] == 50.0
        assert result["current_model"] == "ollama/nomic-embed-text"
        assert result["is_running"] is True
        assert result["has_errors"] is True
        assert result["error_count"] == 2


class TestReindexService:
    """Тесты для сервиса переиндексации."""

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

    def test_init(self, mock_embeddings_client, mock_db_pool):
        """Тест инициализации сервиса."""
        service = ReindexService(
            embeddings_client=mock_embeddings_client,
            db_pool=mock_db_pool,
        )

        assert service._embeddings_client == mock_embeddings_client
        assert service.is_running is False
        assert service._cancelled is False

    def test_set_embeddings_client(self):
        """Тест установки клиента эмбеддингов."""
        service = ReindexService()
        client = AsyncMock(spec=EmbeddingsClient)

        service.set_embeddings_client(client)

        assert service._embeddings_client == client

    def test_stats_property(self, reindex_service):
        """Тест свойства stats."""
        stats = reindex_service.stats
        assert isinstance(stats, ReindexStats)

    @pytest.mark.asyncio
    async def test_check_reindex_needed(self, reindex_service, mock_db_pool):
        """Тест проверки необходимости переиндексации."""
        mock_db_pool.fetchrow = AsyncMock(return_value={"count": 100})

        needs_reindex, count = await reindex_service.check_reindex_needed(
            "ollama/nomic-embed-text"
        )

        assert needs_reindex is True
        assert count == 100

    @pytest.mark.asyncio
    async def test_check_reindex_not_needed(self, reindex_service, mock_db_pool):
        """Тест когда переиндексация не требуется."""
        mock_db_pool.fetchrow = AsyncMock(return_value={"count": 0})

        needs_reindex, count = await reindex_service.check_reindex_needed(
            "ollama/nomic-embed-text"
        )

        assert needs_reindex is False
        assert count == 0

    @pytest.mark.asyncio
    async def test_get_embedding_model_stats(self, reindex_service, mock_db_pool):
        """Тест получения статистики по моделям."""
        mock_db_pool.fetch = AsyncMock(return_value=[
            {
                "embedding_model": "ollama/nomic-embed-text",
                "message_count": 500,
                "first_message": datetime(2024, 1, 1),
                "last_message": datetime(2024, 3, 1),
            },
            {
                "embedding_model": "gemini/text-embedding-004",
                "message_count": 200,
                "first_message": datetime(2024, 2, 1),
                "last_message": datetime(2024, 3, 1),
            },
        ])

        stats = await reindex_service.get_embedding_model_stats()

        assert len(stats) == 2
        assert stats[0].model_name == "ollama/nomic-embed-text"
        assert stats[0].message_count == 500
        assert stats[1].model_name == "gemini/text-embedding-004"
        assert stats[1].message_count == 200

    @pytest.mark.asyncio
    async def test_get_embedding_model_stats_dict(self, reindex_service, mock_db_pool):
        """Тест получения статистики в виде словаря."""
        mock_db_pool.fetch = AsyncMock(return_value=[
            {
                "embedding_model": "ollama/nomic-embed-text",
                "message_count": 500,
                "first_message": datetime(2024, 1, 1),
                "last_message": datetime(2024, 3, 1),
            },
        ])

        stats_dict = await reindex_service.get_embedding_model_stats_dict()

        assert "ollama/nomic-embed-text" in stats_dict
        assert stats_dict["ollama/nomic-embed-text"]["message_count"] == 500

    @pytest.mark.asyncio
    async def test_reindex_all_already_running(self, reindex_service):
        """Тест запуска когда переиндексация уже идёт."""
        reindex_service._stats.is_running = True

        with pytest.raises(RuntimeError, match="Переиндексация уже запущена"):
            await reindex_service.reindex_all()

    @pytest.mark.asyncio
    async def test_reindex_all_no_client(self):
        """Тест запуска без установленного клиента."""
        service = ReindexService()

        with pytest.raises(ValueError, match="Не установлен embeddings_client"):
            await service.reindex_all()

    def test_cancel(self, reindex_service):
        """Тест отмены переиндексации."""
        reindex_service.cancel()

        assert reindex_service._cancelled is True

    def test_get_progress(self, reindex_service):
        """Тест получения прогресса."""
        reindex_service._stats.messages_to_reindex = 1000
        reindex_service._stats.reindexed_count = 500
        reindex_service._stats.failed_count = 10

        progress = reindex_service.get_progress()

        assert progress["total_messages"] == 1000
        assert progress["reindexed_count"] == 500
        assert progress["failed_count"] == 10
        assert "progress_percent" in progress


class TestEmbeddingModelStats:
    """Тесты для модели статистики моделей."""

    def test_creation(self):
        """Тест создания модели."""
        stats = EmbeddingModelStats(
            model_name="ollama/nomic-embed-text",
            message_count=500,
            first_message=datetime(2024, 1, 1),
            last_message=datetime(2024, 3, 1),
        )

        assert stats.model_name == "ollama/nomic-embed-text"
        assert stats.message_count == 500
        assert stats.first_message == datetime(2024, 1, 1)
        assert stats.last_message == datetime(2024, 3, 1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
