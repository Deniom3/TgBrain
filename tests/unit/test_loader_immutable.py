"""
Тесты неизменяемости загрузчика настроек из БД.

Эти тесты документируют ожидаемое поведение load_settings_from_db():
- Возвращает новый экземпляр, не мутирует кэшированный
- Копирует все поля провайдеров
- Сохраняет .env defaults для отсутствующих в БД полей

AAA: Arrange / Act / Assert
Одна проверка на тест.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.config import get_settings


def _make_domain_auth(
    api_id: int = 12345,
    api_hash: str = "a" * 32,
    phone_number: str = "+79991234567",
) -> MagicMock:
    """Создать мок Domain TelegramAuth с заданными полями."""
    auth = MagicMock()
    auth.api_id = MagicMock()
    auth.api_id.value = api_id
    auth.api_hash = MagicMock()
    auth.api_hash.value = api_hash
    auth.phone_number = MagicMock()
    auth.phone_number.value = phone_number
    auth.session_name = None
    auth.session_data = None
    return auth


def _make_llm_provider(
    name: str,
    is_active: bool = False,
    api_key: str | None = None,
    base_url: str = "",
    model: str = "",
    is_enabled: bool = True,
) -> MagicMock:
    """Создать мок LLMProvider с заданными полями."""
    provider = MagicMock()
    provider.name = name
    provider.is_active = is_active
    provider.api_key = api_key
    provider.base_url = base_url
    provider.model = model
    provider.is_enabled = is_enabled
    provider.priority = 0
    provider.description = None
    provider.embedding_dim = 768
    provider.max_retries = 3
    provider.timeout = 30
    provider.normalize = False
    provider.created_at = None
    provider.updated_at = None
    return provider


def _make_embedding_provider(
    name: str,
    is_active: bool = False,
    api_key: str | None = None,
    base_url: str = "",
    model: str = "",
    is_enabled: bool = True,
    embedding_dim: int = 768,
    max_retries: int = 3,
    timeout: int = 30,
    normalize: bool = False,
) -> MagicMock:
    """Создать мок EmbeddingProvider с заданными полями."""
    provider = MagicMock()
    provider.name = name
    provider.is_active = is_active
    provider.api_key = api_key
    provider.base_url = base_url
    provider.model = model
    provider.is_enabled = is_enabled
    provider.priority = 0
    provider.description = None
    provider.embedding_dim = embedding_dim
    provider.max_retries = max_retries
    provider.timeout = timeout
    provider.normalize = normalize
    provider.created_at = None
    provider.updated_at = None
    return provider


def _make_app_settings_dict(data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Создать словарь app settings с заданными значениями."""
    defaults = {
        "app.timezone": "America/New_York",
        "summary.default_hours": 12,
        "summary.max_messages": 100,
    }
    if data:
        defaults.update(data)
    return defaults


def _make_mock_auth_db(
    api_id: int = 12345,
    api_hash: str = "a" * 32,
    phone_number: str = "+79991234567",
) -> AsyncMock:
    """Мок TelegramAuthRepository с заданными полями."""
    repo = AsyncMock()
    repo.get = AsyncMock(return_value=_make_domain_auth(
        api_id=api_id,
        api_hash=api_hash,
        phone_number=phone_number,
    ))
    return repo


def _make_mock_llm_providers(
    providers: list[MagicMock] | None = None,
) -> AsyncMock:
    """Мок LLMProvidersRepository с заданными провайдерами."""
    if providers is None:
        providers = [
            _make_llm_provider("gemini", is_active=True, api_key="gemini-key-123", model="gemini-2.5-flash"),
            _make_llm_provider("openrouter", is_active=False, api_key="or-key-456", model="anthropic/claude-3"),
            _make_llm_provider("ollama", is_active=False, is_enabled=True, model="llama3"),
            _make_llm_provider("lm-studio", is_active=False, is_enabled=False, model="qwen2.5"),
        ]
    repo = AsyncMock()
    repo.get_all = AsyncMock(return_value=providers)
    return repo


def _make_mock_embedding_providers(
    providers: list[MagicMock] | None = None,
) -> AsyncMock:
    """Мок EmbeddingProvidersRepository с заданными провайдерами."""
    if providers is None:
        providers = [
            _make_embedding_provider("ollama", is_active=True, model="bge-small", embedding_dim=384, max_retries=5),
            _make_embedding_provider("gemini", is_active=False, model="embedding-001", api_key="gem-emb-key"),
            _make_embedding_provider("openrouter", is_active=False, model="openai/text-embedding-3-small", embedding_dim=1536),
            _make_embedding_provider("lm-studio", is_active=False, is_enabled=True, model="embed", api_key="lm-key"),
        ]
    repo = AsyncMock()
    repo.get_all = AsyncMock(return_value=providers)
    return repo


def _make_mock_app_settings(
    data: dict[str, Any] | None = None,
) -> AsyncMock:
    """Мок AppSettingsRepository с заданным dict."""
    repo = AsyncMock()
    repo.get_dict = AsyncMock(return_value=_make_app_settings_dict(data))
    return repo


def _reset_settings_cache() -> None:
    """Сбросить кэш get_settings для чистоты теста."""
    get_settings.cache_clear()


# ==================== Loader immutable tests ====================


@pytest.mark.asyncio
async def test_loader_returns_new_instance_not_mutation() -> None:
    """load_settings_from_db() возвращает новый экземпляр, не мутирует кэшированный."""
    from src.config.loader import load_settings_from_db

    _reset_settings_cache()
    original_settings = get_settings()
    original_id = id(original_settings)

    auth_repo = _make_mock_auth_db()
    llm_repo = _make_mock_llm_providers()
    emb_repo = _make_mock_embedding_providers()
    app_repo = _make_mock_app_settings({"app.timezone": "America/Chicago"})

    new_settings = await load_settings_from_db(
        telegram_auth_repo=auth_repo,
        llm_providers_repo=llm_repo,
        embedding_providers_repo=emb_repo,
        app_settings_repo=app_repo,
    )

    assert id(new_settings) != original_id


@pytest.mark.asyncio
async def test_loader_does_not_mutate_cached_settings() -> None:
    """Кэшированный settings после load_settings_from_db() остаётся без изменений."""
    from src.config.loader import load_settings_from_db

    _reset_settings_cache()
    cached_settings = get_settings()
    captured_timezone = cached_settings.timezone
    captured_llm_provider = cached_settings.llm_active_provider
    captured_db_host = cached_settings.db_host

    auth_repo = _make_mock_auth_db()
    llm_repo = _make_mock_llm_providers()
    emb_repo = _make_mock_embedding_providers()
    app_repo = _make_mock_app_settings({"app.timezone": "America/Chicago"})

    await load_settings_from_db(
        telegram_auth_repo=auth_repo,
        llm_providers_repo=llm_repo,
        embedding_providers_repo=emb_repo,
        app_settings_repo=app_repo,
    )

    assert cached_settings.timezone == captured_timezone
    assert cached_settings.llm_active_provider == captured_llm_provider
    assert cached_settings.db_host == captured_db_host


@pytest.mark.asyncio
async def test_loader_copies_all_provider_fields() -> None:
    """Все поля провайдеров скопированы в новый экземпляр."""
    from src.config.loader import load_settings_from_db

    _reset_settings_cache()

    auth_repo = _make_mock_auth_db()
    llm_repo = _make_mock_llm_providers()
    emb_repo = _make_mock_embedding_providers()
    app_repo = _make_mock_app_settings()

    result = await load_settings_from_db(
        telegram_auth_repo=auth_repo,
        llm_providers_repo=llm_repo,
        embedding_providers_repo=emb_repo,
        app_settings_repo=app_repo,
    )

    assert result.llm_active_provider == "gemini"
    assert result.ollama_embedding_provider == "ollama"


@pytest.mark.asyncio
async def test_loader_preserves_env_defaults_for_missing_db() -> None:
    """Поля, отсутствующие в БД, сохраняют .env defaults."""
    from src.config.loader import load_settings_from_db

    _reset_settings_cache()
    original_settings = get_settings()
    original_summary_hours = original_settings.summary_default_hours

    auth_repo = _make_mock_auth_db()
    llm_repo = _make_mock_llm_providers()
    emb_repo = _make_mock_embedding_providers()
    app_repo = _make_mock_app_settings({})

    result = await load_settings_from_db(
        telegram_auth_repo=auth_repo,
        llm_providers_repo=llm_repo,
        embedding_providers_repo=emb_repo,
        app_settings_repo=app_repo,
    )

    assert result.summary_default_hours == original_summary_hours


@pytest.mark.asyncio
async def test_loader_telegram_auth_fields_copied() -> None:
    """Telegram auth поля корректно скопированы."""
    from src.config.loader import load_settings_from_db

    _reset_settings_cache()

    auth_repo = _make_mock_auth_db(api_id=99999, api_hash="b" * 32, phone_number="+71112223344")
    llm_repo = _make_mock_llm_providers()
    emb_repo = _make_mock_embedding_providers()
    app_repo = _make_mock_app_settings()

    result = await load_settings_from_db(
        telegram_auth_repo=auth_repo,
        llm_providers_repo=llm_repo,
        embedding_providers_repo=emb_repo,
        app_settings_repo=app_repo,
    )

    assert result.tg_api_id == 99999
    assert result.tg_api_hash == "b" * 32
    assert result.tg_phone_number == "+71112223344"


@pytest.mark.asyncio
async def test_loader_llm_provider_fields_copied() -> None:
    """LLM provider поля корректно скопированы."""
    from src.config.loader import load_settings_from_db

    _reset_settings_cache()

    llm_providers = [
        _make_llm_provider("openrouter", is_active=True, api_key="new-or-key", model="meta/llama-3"),
        _make_llm_provider("gemini", is_active=False, api_key="gem-key", model="gemini-2.0-flash"),
    ]

    auth_repo = _make_mock_auth_db()
    llm_repo = _make_mock_llm_providers(providers=llm_providers)
    emb_repo = _make_mock_embedding_providers()
    app_repo = _make_mock_app_settings()

    result = await load_settings_from_db(
        telegram_auth_repo=auth_repo,
        llm_providers_repo=llm_repo,
        embedding_providers_repo=emb_repo,
        app_settings_repo=app_repo,
    )

    assert result.llm_active_provider == "openrouter"
    assert result.openrouter_api_key == "new-or-key"
    assert result.openrouter_model == "meta/llama-3"
    assert result.openrouter_base_url == ""


@pytest.mark.asyncio
async def test_loader_embedding_fields_copied() -> None:
    """Embedding provider поля корректно скопированы."""
    from src.config.loader import load_settings_from_db

    _reset_settings_cache()

    emb_providers = [
        _make_embedding_provider("gemini", is_active=True, model="embedding-002", embedding_dim=256, max_retries=10),
        _make_embedding_provider("ollama", is_active=False, model="nomic-embed-text", embedding_dim=768),
    ]

    auth_repo = _make_mock_auth_db()
    llm_repo = _make_mock_llm_providers()
    emb_repo = _make_mock_embedding_providers(providers=emb_providers)
    app_repo = _make_mock_app_settings()

    result = await load_settings_from_db(
        telegram_auth_repo=auth_repo,
        llm_providers_repo=llm_repo,
        embedding_providers_repo=emb_repo,
        app_settings_repo=app_repo,
    )

    assert result.gemini_embedding_model == "embedding-002"
    assert result.gemini_embedding_dim == 256
    assert result.gemini_embedding_max_retries == 10
