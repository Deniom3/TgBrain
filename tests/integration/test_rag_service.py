"""
Integration тесты для RAGService.

Проверяют полный цикл работы RAG с различными параметрами.
"""

import pytest
from unittest.mock import AsyncMock

from src.rag import RAGService

pytestmark = pytest.mark.integration


@pytest.fixture
def mock_pool():
    pool = AsyncMock()
    pool.acquire = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=pool)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
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


@pytest.mark.asyncio
async def test_rag_service_initialization(rag_service):
    assert rag_service is not None
    assert hasattr(rag_service, 'search')
    assert hasattr(rag_service, 'summary_search')
    assert hasattr(rag_service, 'summary_service')


@pytest.mark.asyncio
async def test_rag_service_close(mock_embeddings, mock_llm, settings, mock_pool):
    service = RAGService(settings, mock_pool, mock_embeddings, mock_llm)
    await service.close()

    mock_embeddings.close.assert_called_once()
    mock_llm.close.assert_called_once()


@pytest.mark.asyncio
async def test_rag_service_context_manager(mock_embeddings, mock_llm, settings, mock_pool):
    service = RAGService(settings, mock_pool, mock_embeddings, mock_llm)

    async with service as s:
        assert s is service

    mock_embeddings.close.assert_called_once()
    mock_llm.close.assert_called_once()
