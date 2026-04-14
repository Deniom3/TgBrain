"""
Тесты замороженного (immutable) поведения Settings.

Эти тесты документируют ожидаемое поведение Settings с frozen=True.
На текущий момент они ОЖИДАЕМО ПАДАЮТ, так как frozen ещё не включён.
После включения frozen=True в model_config все тесты должны пройти.

AAA: Arrange / Act / Assert
Одна проверка на тест.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from src.config import Settings, get_settings


def _make_settings() -> Settings:
    """Создать Settings с известными значениями для тестов."""
    return Settings(
        db_host="localhost",
        db_port=5432,
        db_name="test_db",
        db_user="test_user",
        db_password="test_password",
        timezone="Etc/UTC",
        log_level="DEBUG",
        summary_default_hours=12,
        summary_max_messages=25,
        rag_top_k=3,
        rag_score_threshold=0.5,
    )


# ==================== Frozen direct assignment ====================


def test_settings_frozen_direct_assignment_raises() -> None:
    """Прямое присваивание поля settings.timezone выбрасывает ValidationError."""
    settings = _make_settings()

    with pytest.raises(ValidationError):
        settings.timezone = "America/New_York"


@pytest.mark.parametrize(
    "field_name,new_value",
    [
        ("db_host", "remote-host"),
        ("db_port", 9999),
        ("db_name", "other_db"),
        ("db_user", "other_user"),
        ("db_password", "other_pass"),
        ("log_level", "WARNING"),
        ("timezone", "America/New_York"),
        ("summary_default_hours", 48),
        ("summary_max_messages", 100),
        ("rag_top_k", 10),
        ("rag_score_threshold", 0.7),
        ("tg_chat_enable", "123,456"),
        ("tg_chat_disable", "789"),
        ("llm_active_provider", "openrouter"),
        ("llm_fallback_providers", "gemini,ollama"),
        ("llm_auto_fallback", False),
        ("llm_fallback_timeout", 20),
        ("gemini_model", "gemini-2.0-flash"),
        ("openrouter_model", "anthropic/claude-3.5-sonnet"),
        ("ollama_llm_enabled", False),
        ("ollama_llm_base_url", "http://other:11434"),
        ("ollama_llm_model", "llama3"),
        ("lm_studio_enabled", True),
        ("lm_studio_base_url", "http://other:1234"),
        ("lm_studio_model", "qwen2.5"),
        ("ollama_embedding_url", "http://other:11434"),
        ("ollama_embedding_model", "bge-small"),
        ("ollama_embedding_max_retries", 5),
        ("ollama_embedding_timeout", 60),
        ("ollama_embedding_normalize", True),
        ("gemini_embedding_url", "http://other/gemini"),
        ("gemini_embedding_model", "embedding-001"),
        ("gemini_embedding_dim", 256),
        ("openrouter_embedding_url", "http://other/openrouter"),
        ("openrouter_embedding_model", "embed-small"),
        ("openrouter_embedding_dim", 1024),
        ("openrouter_embedding_batch_size", 50),
        ("lm_studio_embedding_url", "http://other/lm"),
        ("lm_studio_embedding_model", "embed"),
        ("lm_studio_embedding_dim", 512),
    ],
)
def test_settings_frozen_all_fields_immutable(field_name: str, new_value: Any) -> None:
    """Все поля Settings нельзя изменить напрямую."""
    settings = _make_settings()

    with pytest.raises(ValidationError):
        setattr(settings, field_name, new_value)


# ==================== model_copy ====================


def test_settings_model_copy_creates_new_instance() -> None:
    """model_copy(update={...}) возвращает новый объект с другим id."""
    settings = _make_settings()

    new_settings = settings.model_copy(update={"timezone": "America/New_York"})

    assert id(new_settings) != id(settings)


def test_settings_model_copy_preserves_unchanged_fields() -> None:
    """Неизменённые поля сохраняют исходные значения."""
    settings = _make_settings()

    new_settings = settings.model_copy(update={"timezone": "America/New_York"})

    assert new_settings.db_host == settings.db_host
    assert new_settings.db_port == settings.db_port
    assert new_settings.db_name == settings.db_name
    assert new_settings.log_level == settings.log_level
    assert new_settings.rag_top_k == settings.rag_top_k


def test_settings_model_copy_updates_specified_fields() -> None:
    """Указанные поля получают новые значения."""
    settings = _make_settings()

    new_settings = settings.model_copy(update={"timezone": "America/New_York", "log_level": "WARNING"})

    assert new_settings.timezone == "America/New_York"
    assert new_settings.log_level == "WARNING"


def test_settings_model_copy_deep_preserves_nested() -> None:
    """model_copy(deep=True) корректно копирует nested models (embedding_config)."""
    settings = _make_settings()

    new_settings = settings.model_copy(deep=True)

    original_config = settings.embedding_config
    new_config = new_settings.embedding_config

    assert id(original_config) != id(new_config)
    assert original_config.ollama.model == new_config.ollama.model
    assert original_config.gemini.dim == new_config.gemini.dim
    assert original_config.openrouter.batch_size == new_config.openrouter.batch_size


# ==================== get_settings ====================


def test_settings_get_settings_returns_frozen() -> None:
    """get_settings() возвращает frozen экземпляр."""
    get_settings.cache_clear()

    result = get_settings()

    model_config = result.model_config
    assert model_config.get("frozen") is True


def test_settings_from_env_defaults_frozen() -> None:
    """Settings из .env defaults создаётся frozen."""
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.model_config.get("frozen") is True
    assert isinstance(settings.timezone, str)
    assert settings.db_url is not None


# ==================== model_validator ====================


def test_settings_model_validator_db_url_no_mutation() -> None:
    """model_validator generate_db_url не мутирует self (проверка через frozen)."""
    test_password = "secret"
    settings = Settings(
        db_host="test-host",
        db_port=5433,
        db_name="test_db",
        db_user="test_user",
        db_password=test_password,
    )

    db_url = settings.db_url

    assert db_url is not None
    assert f"test_user:{test_password}@test-host:5433/test_db" in db_url


# ==================== Equality ====================


def test_settings_equality_after_model_copy() -> None:
    """Два Settings с одинаковыми полями равны."""
    settings = _make_settings()
    new_settings = settings.model_copy()

    assert settings == new_settings
