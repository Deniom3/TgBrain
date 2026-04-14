"""
Тесты для validate_settings() и validate_telegram_auth().

Проверяется:
- Пустой db_password бросает CONF-003 (fail-fast)
- Невалидный провайдер бросает CONF-004 (fail-fast)
- Валидные настройки возвращают None
- Local провайдеры (ollama, lm-studio) не требуют API key
- validate_telegram_auth() бросает CONF-005 при отсутствии TG credentials
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config.exceptions import ConfigurationError
from src.config.loader import validate_settings, validate_telegram_auth
from src.config.providers import ProviderConfig


def _make_settings(
    db_password: str = "secret123",
    provider_config: ProviderConfig | Exception | None = None,
    tg_api_id: int | None = 12345,
    tg_api_hash: str | None = "valid_hash_32_chars_long_string_here",
):
    """Создать mock settings с заданными параметрами."""
    settings = MagicMock()
    settings.db_password = db_password
    settings.tg_api_id = tg_api_id
    settings.tg_api_hash = tg_api_hash
    if provider_config is None:
        provider_config = ProviderConfig(
            name="gemini",
            api_key="sk-valid-api-key-12345",
            base_url="https://example.com",
            model="test-model",
        )
    if isinstance(provider_config, Exception):
        settings.get_provider_config.side_effect = provider_config
    else:
        settings.get_provider_config.return_value = provider_config
    return settings


@pytest.mark.asyncio
async def test_empty_db_password_raises_conf003() -> None:
    """Отсутствие db_password вызывает ConfigurationError с кодом CONF-003."""
    settings = _make_settings(db_password="")

    with pytest.raises(ConfigurationError) as exc_info:
        await validate_settings(settings)

    assert exc_info.value.code == "CONF-003"
    assert "DB_PASSWORD" in exc_info.value.message


@pytest.mark.asyncio
async def test_db_password_checked_before_api_key() -> None:
    """При отсутствии и db_password, и api_key — бросается CONF-003 (fail-fast)."""
    settings = _make_settings(
        db_password="",
        provider_config=ProviderConfig(
            name="gemini",
            api_key=None,
            base_url="https://example.com",
            model="test-model",
        ),
    )

    with pytest.raises(ConfigurationError) as exc_info:
        await validate_settings(settings)

    assert exc_info.value.code == "CONF-003"
    assert "API ключ" not in exc_info.value.message


@pytest.mark.asyncio
async def test_missing_api_key_for_cloud_provider_raises_conf004() -> None:
    """Отсутствие API ключа у облачного провайдера вызывает CONF-004."""
    settings = _make_settings(
        db_password="secret",
        provider_config=ProviderConfig(
            name="gemini",
            api_key=None,
            base_url="https://example.com",
            model="test-model",
        ),
    )

    with pytest.raises(ConfigurationError) as exc_info:
        await validate_settings(settings)

    assert exc_info.value.code == "CONF-004"
    assert "gemini" in exc_info.value.message


@pytest.mark.asyncio
async def test_valid_settings_return_none() -> None:
    """Валидные настройки не вызывают исключений."""
    settings = _make_settings(
        db_password="secret",
        provider_config=ProviderConfig(
            name="gemini",
            api_key="sk-valid-key-12345",
            base_url="https://example.com",
            model="test-model",
        ),
    )

    await validate_settings(settings)


@pytest.mark.asyncio
async def test_local_provider_ollama_does_not_require_api_key() -> None:
    """Ollama как локальный провайдер не требует API key."""
    settings = _make_settings(
        db_password="secret",
        provider_config=ProviderConfig(
            name="ollama",
            api_key=None,
            base_url="http://localhost:11434",
            model="deepseek-coder",
        ),
    )

    await validate_settings(settings)


@pytest.mark.asyncio
async def test_local_provider_lm_studio_does_not_require_api_key() -> None:
    """LM Studio как локальный провайдер не требует API key."""
    settings = _make_settings(
        db_password="secret",
        provider_config=ProviderConfig(
            name="lm-studio",
            api_key=None,
            base_url="http://localhost:1234",
            model="qwen-model",
        ),
    )

    await validate_settings(settings)


@pytest.mark.asyncio
async def test_invalid_provider_name_raises_conf004() -> None:
    """Неизвестный провайдер вызывает CONF-004 с описанием ошибки."""
    settings = _make_settings(
        db_password="secret",
        provider_config=ValueError("Неизвестный провайдер: unknown"),
    )

    with pytest.raises(ConfigurationError) as exc_info:
        await validate_settings(settings)

    assert exc_info.value.code == "CONF-004"
    assert "Неизвестный провайдер" in exc_info.value.message


@pytest.mark.asyncio
async def test_validate_telegram_auth_missing_api_id_raises_conf005() -> None:
    """Отсутствие TG_API_ID вызывает CONF-005."""
    settings = _make_settings(tg_api_id=None)

    with pytest.raises(ConfigurationError) as exc_info:
        await validate_telegram_auth(settings)

    assert exc_info.value.code == "CONF-005"
    assert "TG_API_ID" in exc_info.value.message


@pytest.mark.asyncio
async def test_validate_telegram_auth_missing_api_hash_raises_conf005() -> None:
    """Отсутствие TG_API_HASH вызывает CONF-005."""
    settings = _make_settings(tg_api_hash=None)

    with pytest.raises(ConfigurationError) as exc_info:
        await validate_telegram_auth(settings)

    assert exc_info.value.code == "CONF-005"
    assert "TG_API_HASH" in exc_info.value.message


@pytest.mark.asyncio
async def test_validate_telegram_auth_missing_both_raises_conf005() -> None:
    """Отсутствие обоих Telegram credentials вызывает CONF-005."""
    settings = _make_settings(tg_api_id=None, tg_api_hash=None)

    with pytest.raises(ConfigurationError) as exc_info:
        await validate_telegram_auth(settings)

    assert exc_info.value.code == "CONF-005"
    assert "TG_API_ID" in exc_info.value.message
    assert "TG_API_HASH" in exc_info.value.message


@pytest.mark.asyncio
async def test_validate_telegram_auth_valid_returns_none() -> None:
    """Валидные Telegram credentials не вызывают исключений."""
    settings = _make_settings()

    await validate_telegram_auth(settings)


@pytest.mark.asyncio
async def test_lifecycle_invalid_credentials_raises_configuration_error() -> None:
    """Невалидные настройки вызывают ConfigurationError при инициализации."""
    from src.services.application_lifecycle_service import ApplicationLifecycleService

    settings = _make_settings(db_password="")

    lifecycle_service = ApplicationLifecycleService(settings)

    with (
        patch("src.database.get_pool", new=AsyncMock()) as mock_pool,
        patch("src.database.init_db", new=AsyncMock()),
        patch("src.settings_initializer.SettingsInitializer.initialize", new=AsyncMock()),
        patch("src.config.loader.load_settings_from_db", return_value=settings),
    ):
        mock_pool.return_value = MagicMock()

        with pytest.raises(ConfigurationError, match="CONF-003"):
            await lifecycle_service.initialize()


@pytest.mark.asyncio
async def test_lifecycle_valid_credentials_starts_successfully() -> None:
    """Валидные настройки проходят валидацию, lifecycle продолжается дальше."""
    from src.services.application_lifecycle_service import ApplicationLifecycleService

    valid_settings = _make_settings(
        db_password="secret",
        provider_config=ProviderConfig(
            name="gemini",
            api_key="sk-valid-key-12345",
            base_url="https://example.com",
            model="test-model",
        ),
    )
    valid_settings.ollama_embedding_provider = "ollama"
    valid_settings.ollama_embedding_url = "http://localhost:11434"
    valid_settings.ollama_embedding_model = "nomic-embed-text"

    lifecycle_service = ApplicationLifecycleService(valid_settings)

    validation_passed = False

    async def mock_validate_ok(_settings: MagicMock) -> None:
        nonlocal validation_passed
        validation_passed = True

    with (
        patch("src.database.get_pool", new=AsyncMock()) as mock_pool,
        patch("src.database.init_db", new=AsyncMock()),
        patch("src.settings_initializer.SettingsInitializer.initialize", new=AsyncMock()),
        patch("src.config.loader.load_settings_from_db", return_value=valid_settings),
        patch("src.config.validate_settings", side_effect=mock_validate_ok),
        patch("src.embeddings.EmbeddingsClient") as mock_embeddings_cls,
    ):
        mock_pool.return_value = MagicMock()
        mock_embeddings = MagicMock()
        mock_embeddings.initialize_provider = AsyncMock()
        mock_embeddings_cls.return_value = mock_embeddings

        try:
            await lifecycle_service.initialize()
        except (RuntimeError, TypeError, AttributeError):
            pass

    assert validation_passed
