"""
Модульные тесты для RAGService (Phase 4 refactoring).

Все тесты изолированы от БД — используют моки вместо реальных подключений.

Тестирование:
- check_chat_exists()
- summary()
- close()
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.rag import RAGService


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value={"id": 1})

    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__.return_value = mock_conn
    acquire_ctx.__aexit__.return_value = None
    pool.acquire = MagicMock(return_value=acquire_ctx)
    return pool


@pytest.fixture
def mock_embeddings():
    embeddings = AsyncMock()
    embeddings.close = AsyncMock()
    return embeddings


@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.close = AsyncMock()
    return llm


@pytest.fixture
async def rag_service(settings, mock_pool, mock_embeddings, mock_llm):
    service = RAGService(settings, mock_pool, mock_embeddings, mock_llm)
    yield service
    await service.close()


# =============================================================================
# Тесты check_chat_exists()
# =============================================================================


@pytest.mark.asyncio
async def test_check_chat_exists_returns_true_when_exists(rag_service, mock_pool):
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value={"id": 1})
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    result = await rag_service.check_chat_exists(123)

    assert result is True
    mock_conn.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_check_chat_exists_returns_false_when_not_exists(rag_service, mock_pool):
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    result = await rag_service.check_chat_exists(999)

    assert result is False


@pytest.mark.asyncio
async def test_check_chat_exists_caches_result(rag_service, mock_pool):
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value={"id": 1})
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    await rag_service.check_chat_exists(123)
    await rag_service.check_chat_exists(123)

    assert mock_conn.fetchrow.call_count == 1


@pytest.mark.asyncio
async def test_clear_chat_cache(rag_service):
    await rag_service.check_chat_exists.cache_clear if hasattr(rag_service.check_chat_exists, 'cache_clear') else None

    rag_service._chat_cache[123] = (0, True)
    await rag_service.clear_chat_cache()

    assert rag_service._chat_cache == {}


# =============================================================================
# Тесты close()
# =============================================================================


@pytest.mark.asyncio
async def test_close_closes_embeddings(mock_embeddings, mock_llm, settings, mock_pool):
    service = RAGService(settings, mock_pool, mock_embeddings, mock_llm)
    await service.close()

    mock_embeddings.close.assert_called_once()


@pytest.mark.asyncio
async def test_close_closes_llm(mock_embeddings, mock_llm, settings, mock_pool):
    service = RAGService(settings, mock_pool, mock_embeddings, mock_llm)
    await service.close()

    mock_llm.close.assert_called_once()


@pytest.mark.asyncio
async def test_context_manager(mock_embeddings, mock_llm, settings, mock_pool):
    service = RAGService(settings, mock_pool, mock_embeddings, mock_llm)

    async with service as s:
        assert s is service

    mock_embeddings.close.assert_called_once()
    mock_llm.close.assert_called_once()
