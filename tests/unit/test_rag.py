"""
Модульные тесты RAG сервиса.

Все тесты изолированы от БД — используют моки вместо реальных подключений.
"""

import pytest
from unittest.mock import AsyncMock

from src.rag import RAGService


@pytest.fixture
def mock_pool():
    """Мок pool для БД."""
    pool = AsyncMock()
    pool.acquire = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=pool)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    return pool


@pytest.fixture
def mock_embeddings():
    """Мок embeddings клиента."""
    embeddings = AsyncMock()
    embeddings.embed_text = AsyncMock(return_value=[0.1] * 768)
    embeddings.embed_text_batch = AsyncMock(return_value=[[0.1] * 768])
    return embeddings


@pytest.fixture
def mock_llm():
    """Мок LLM клиента."""
    llm = AsyncMock()
    llm.generate = AsyncMock(return_value="Test response")
    llm.generate_batch = AsyncMock(return_value=["Test response"])
    return llm


@pytest.mark.asyncio
async def test_rag_service_creation(settings, mock_pool, mock_embeddings, mock_llm):
    """Проверка создания RAG сервиса (с моками)."""
    rag = RAGService(settings, mock_pool, mock_embeddings, mock_llm)
    assert rag is not None

    await rag.close()


@pytest.mark.asyncio
async def test_rag_summary_method_exists(settings, mock_pool, mock_embeddings, mock_llm):
    """Проверка наличия метода summary (с моками)."""
    rag = RAGService(settings, mock_pool, mock_embeddings, mock_llm)

    assert hasattr(rag, 'summary')
    assert callable(getattr(rag, 'summary'))

    await rag.close()


@pytest.mark.asyncio
async def test_rag_close_method_exists(settings, mock_pool, mock_embeddings, mock_llm):
    """Проверка наличия метода close (с моками)."""
    rag = RAGService(settings, mock_pool, mock_embeddings, mock_llm)

    assert hasattr(rag, 'close')
    assert callable(getattr(rag, 'close'))

    await rag.close()
