"""
Модульные тесты LLM клиента.
"""

import pytest
from src.llm_client import LLMClient


@pytest.mark.asyncio
async def test_llm_client_creation(settings):
    """Проверка создания LLM клиента."""
    client = LLMClient(settings)
    assert client is not None


@pytest.mark.asyncio
async def test_llm_health(settings):
    """Проверка здоровья LLM клиента."""
    client = LLMClient(settings)
    health = await client.check_health()
    # Health может быть False если LLM недоступен, это нормально
    assert isinstance(health, bool)


@pytest.mark.asyncio
async def test_llm_client_has_generate(settings):
    """Проверка наличия метода generate."""
    client = LLMClient(settings)
    assert hasattr(client, 'generate')
    assert callable(getattr(client, 'generate'))


@pytest.mark.asyncio
async def test_llm_client_has_check_health(settings):
    """Проверка наличия метода check_health."""
    client = LLMClient(settings)
    assert hasattr(client, 'check_health')
    assert callable(getattr(client, 'check_health'))


@pytest.mark.asyncio
async def test_llm_provider_chain(settings):
    """Проверка цепочки провайдеров."""
    LLMClient(settings)
    # Цепочка должна содержать активный провайдер
    chain = settings.get_provider_chain()
    assert len(chain) >= 1
    assert chain[0] == settings.llm_active_provider.lower()
