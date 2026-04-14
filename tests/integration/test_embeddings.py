"""
Модульные тесты Embeddings клиента.
"""

import pytest

from src.embeddings import EmbeddingsClient

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_embedding_dimension(settings):
    """Проверка размерности эмбеддинга."""
    client = EmbeddingsClient(settings)
    await client.initialize_provider()
    embedding = await client.get_embedding("Тестовый текст")
    assert len(embedding) == client.embedding_dim


@pytest.mark.asyncio
async def test_embedding_consistency(settings):
    """Проверка консистентности эмбеддингов."""
    client = EmbeddingsClient(settings)
    await client.initialize_provider()
    emb1 = await client.get_embedding("Одинаковый текст")
    emb2 = await client.get_embedding("Одинаковый текст")
    assert emb1 == emb2


@pytest.mark.asyncio
async def test_embedding_health(settings):
    """Проверка здоровья Embeddings клиента."""
    client = EmbeddingsClient(settings)
    await client.initialize_provider()
    health = await client.check_health()
    assert health is True


@pytest.mark.asyncio
async def test_embedding_different_texts(settings):
    """Проверка, что разные тексты дают разные эмбеддинги."""
    client = EmbeddingsClient(settings)
    await client.initialize_provider()

    emb1 = await client.get_embedding("Привет, как дела?")
    emb2 = await client.get_embedding("До свидания, увидимся позже")

    # Эмбеддинги должны отличаться
    assert emb1 != emb2


@pytest.mark.asyncio
async def test_embedding_russian_text(settings):
    """Проверка работы с русским текстом."""
    client = EmbeddingsClient(settings)
    await client.initialize_provider()
    embedding = await client.get_embedding("Привет, это тест на русском языке")
    assert len(embedding) == client.embedding_dim
    assert all(isinstance(x, float) for x in embedding)


@pytest.mark.asyncio
async def test_embedding_english_text(settings):
    """Проверка работы с английским текстом."""
    client = EmbeddingsClient(settings)
    await client.initialize_provider()
    embedding = await client.get_embedding("Hello, this is an English test")
    assert len(embedding) == client.embedding_dim
    assert all(isinstance(x, float) for x in embedding)
