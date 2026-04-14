"""Тесты для RAGService."""

from unittest.mock import AsyncMock

import pytest

from src.rag.service import RAGService


class TestRAGServiceClearChatCache:
    """Тест: clear_chat_cache очищает dict."""

    @pytest.mark.asyncio
    async def test_rag_service_clear_chat_cache(self) -> None:
        """Проверяет, что clear_chat_cache очищает внутренний кэш."""
        mock_config = AsyncMock()
        mock_config.summary_default_hours = 24
        mock_config.summary_max_messages = 100

        mock_db_pool = AsyncMock()
        mock_embeddings = AsyncMock()
        mock_llm = AsyncMock()

        service = RAGService(
            config=mock_config,
            db_pool=mock_db_pool,
            embeddings_client=mock_embeddings,
            llm_client=mock_llm,
        )

        service._chat_cache[123] = (0.0, True)
        service._chat_cache[456] = (0.0, False)

        assert len(service._chat_cache) == 2

        await service.clear_chat_cache()

        assert len(service._chat_cache) == 0


class TestRAGServiceAsyncEnter:
    """Тест: __aenter__ возвращает self."""

    @pytest.mark.asyncio
    async def test_rag_service_async_enter_returns_self(self) -> None:
        """Проверяет, что __aenter__ возвращает тот же экземпляр."""
        mock_config = AsyncMock()
        mock_config.summary_default_hours = 24
        mock_config.summary_max_messages = 100

        mock_db_pool = AsyncMock()
        mock_embeddings = AsyncMock()
        mock_llm = AsyncMock()

        service = RAGService(
            config=mock_config,
            db_pool=mock_db_pool,
            embeddings_client=mock_embeddings,
            llm_client=mock_llm,
        )

        result = await service.__aenter__()

        assert result is service


class TestRAGServiceAsyncExit:
    """Тест: __aexit__ вызывает close."""

    @pytest.mark.asyncio
    async def test_rag_service_async_exit_calls_close(self) -> None:
        """Проверяет, что __aexit__ корректно вызывает close."""
        mock_config = AsyncMock()
        mock_config.summary_default_hours = 24
        mock_config.summary_max_messages = 100

        mock_db_pool = AsyncMock()
        mock_embeddings = AsyncMock()
        mock_llm = AsyncMock()

        service = RAGService(
            config=mock_config,
            db_pool=mock_db_pool,
            embeddings_client=mock_embeddings,
            llm_client=mock_llm,
        )

        await service.__aexit__(None, None, None)

        mock_embeddings.close.assert_awaited_once()
        mock_llm.close.assert_awaited_once()
