"""
Тесты degraded-mode запуска приложения.

Проверяется:
- Приложение запускается без Telegram credentials
- state["telegram_configured"] = False
- Ingester = None
- Health endpoint показывает "not_configured" для telegram
"""

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config.exceptions import ConfigurationError
from src.config.providers import ProviderConfig


def _make_settings(
    db_password: str = "secret123",
    tg_api_id: int | None = None,
    tg_api_hash: str | None = None,
):
    """Создать mock settings с заданными параметрами."""
    settings = MagicMock()
    settings.db_password = db_password
    settings.tg_api_id = tg_api_id
    settings.tg_api_hash = tg_api_hash
    settings.get_provider_config.return_value = ProviderConfig(
        name="gemini",
        api_key="sk-valid-api-key-12345",
        base_url="https://example.com",
        model="test-model",
    )
    return settings


def _enter_all_patches(stack: ExitStack, patches: list) -> None:
    """Активировать список патчей через ExitStack."""
    for p in patches:
        stack.enter_context(p)


def _create_lifecycle_patches(
    settings_obj,
    telegram_auth_raises: Exception | None = None,
    validate_settings_raises: Exception | None = None,
    db_pool_mock=None,
    embeddings_mock=None,
    reindex_mock=None,
    limiter_mock=None,
    cleanup_mock=None,
):
    """Создать список патчей для lifecycle инициализации."""
    if db_pool_mock is None:
        db_pool_mock = MagicMock()

    telegram_validate_side_effect = telegram_auth_raises

    mock_telegram_auth_repo = MagicMock()
    mock_telegram_auth_repo.get = AsyncMock(return_value=None)

    validate_settings_mock = AsyncMock()
    if validate_settings_raises is not None:
        validate_settings_mock.side_effect = validate_settings_raises

    patches = [
        patch("src.database.get_pool", return_value=db_pool_mock),
        patch("src.database.init_extensions_direct", new=AsyncMock()),
        patch("src.database.init_db_tables", new=AsyncMock()),
        patch("src.database.migrate_chat_ids", new=AsyncMock()),
        patch("src.database.migrate_chat_types", new=AsyncMock()),
        patch("src.settings_initializer.SettingsInitializer.initialize", new=AsyncMock()),
        patch("src.settings.TelegramAuthRepository", return_value=mock_telegram_auth_repo),
        patch("src.settings.repositories.app_settings.AppSettingsRepository"),
        patch("src.settings.repositories.llm_providers.LLMProvidersRepository"),
        patch("src.settings.repositories.embedding_providers.EmbeddingProvidersRepository"),
        patch("src.settings.repositories.summary_cleanup_settings.SummaryCleanupSettingsRepository"),
        patch("src.settings.repositories.pending_cleanup_repository.PendingCleanupSettingsRepository"),
        patch("src.rate_limiter.repositories.RequestStatisticsRepository"),
        patch("src.rate_limiter.repositories.FloodWaitIncidentRepository"),
        patch("src.reindex.repository.ReindexSettingsRepository"),
        patch("src.reindex.repository.ReindexTaskRepository"),
        patch("src.settings_api.set_reindex_service"),
        patch("src.config.loader.load_settings_from_db", return_value=settings_obj),
        patch("src.config.validate_settings", validate_settings_mock),
        patch("src.config.validate_telegram_auth", side_effect=telegram_validate_side_effect),
        patch("src.embeddings.EmbeddingsClient", return_value=embeddings_mock),
        patch("src.llm_client.LLMClient"),
        patch("src.rag.RAGService"),
        patch("src.reindex.ReindexService", return_value=reindex_mock),
        patch("src.rate_limiter.TelegramRateLimiter", return_value=limiter_mock),
        patch("src.ingestion.MessageSaver"),
        patch("src.services.chat_access_validator.ChatAccessValidator"),
        patch("src.auth.QRAuthService"),
        patch("src.rag.summary_cleanup_service.SummaryCleanupService", return_value=cleanup_mock),
    ]
    return patches


@pytest.mark.asyncio
async def test_degraded_startup_without_telegram_credentials(caplog) -> None:
    """Приложение запускается без Telegram credentials в degraded mode."""
    # Arrange
    from src.services.application_lifecycle_service import ApplicationLifecycleService

    settings = _make_settings(tg_api_id=None, tg_api_hash=None)
    lifecycle_service = ApplicationLifecycleService(settings)

    mock_db_pool = MagicMock()
    mock_embeddings = MagicMock()
    mock_embeddings.initialize_provider = AsyncMock()
    mock_reindex = MagicMock()
    mock_reindex.start_background_service = AsyncMock()
    mock_limiter = MagicMock()
    mock_limiter.start = AsyncMock()
    mock_limiter.set_flood_wait_callback = MagicMock()
    mock_cleanup = MagicMock()
    mock_cleanup.start = AsyncMock()

    patches = _create_lifecycle_patches(
        settings_obj=settings,
        telegram_auth_raises=ConfigurationError("CONF-005", "Telegram credentials not configured"),
        db_pool_mock=mock_db_pool,
        embeddings_mock=mock_embeddings,
        reindex_mock=mock_reindex,
        limiter_mock=mock_limiter,
        cleanup_mock=mock_cleanup,
    )

    # Act
    with ExitStack() as stack:
        _enter_all_patches(stack, patches)
        state = await lifecycle_service.initialize()

    # Assert — degraded mode state
    assert state["telegram_configured"] is False

    # Assert — interaction: set_flood_wait_callback вызван
    mock_limiter.set_flood_wait_callback.assert_called_once()

    # Assert — interaction: логирование degraded mode
    assert any(
        "degraded mode" in record.message.lower()
        for record in caplog.records
        if record.levelname == "WARNING"
    )


@pytest.mark.asyncio
async def test_degraded_startup_ingester_is_none(caplog) -> None:
    """При degraded mode Ingester равен None."""
    # Arrange
    from src.services.application_lifecycle_service import ApplicationLifecycleService

    settings = _make_settings(tg_api_id=None, tg_api_hash=None)
    lifecycle_service = ApplicationLifecycleService(settings)

    mock_db_pool = MagicMock()
    mock_embeddings = MagicMock()
    mock_embeddings.initialize_provider = AsyncMock()
    mock_reindex = MagicMock()
    mock_reindex.start_background_service = AsyncMock()
    mock_limiter = MagicMock()
    mock_limiter.start = AsyncMock()
    mock_limiter.set_flood_wait_callback = MagicMock()
    mock_cleanup = MagicMock()
    mock_cleanup.start = AsyncMock()

    patches = _create_lifecycle_patches(
        settings_obj=settings,
        telegram_auth_raises=ConfigurationError("CONF-005", "Telegram credentials not configured"),
        db_pool_mock=mock_db_pool,
        embeddings_mock=mock_embeddings,
        reindex_mock=mock_reindex,
        limiter_mock=mock_limiter,
        cleanup_mock=mock_cleanup,
    )

    # Act
    with ExitStack() as stack:
        _enter_all_patches(stack, patches)
        state = await lifecycle_service.initialize()

    # Assert — ingester is None in degraded mode
    assert state["ingester"] is None

    # Assert — interaction: set_flood_wait_callback вызван
    mock_limiter.set_flood_wait_callback.assert_called_once()

    # Assert — interaction: логирование degraded mode
    assert any(
        "degraded mode" in record.message.lower()
        for record in caplog.records
        if record.levelname == "WARNING"
    )


@pytest.mark.asyncio
async def test_health_endpoint_shows_not_configured_for_telegram() -> None:
    """Health endpoint возвращает 'not_configured' для telegram в degraded mode."""
    # Arrange
    import time
    from src.api.endpoints import health as health_module
    from src.api.endpoints.health import health_check

    original_cache = dict(health_module._health_cache)
    try:
        health_module._health_cache["emb_time"] = int(time.time())
        health_module._health_cache["emb_status"] = True
        health_module._health_cache["llm_time"] = int(time.time())
        health_module._health_cache["llm_status"] = True

        app = MagicMock()
        app.state.telegram_configured = False
        app.state.embeddings = AsyncMock()
        app.state.embeddings.check_health = AsyncMock(return_value=True)
        app.state.llm = AsyncMock()
        app.state.llm.check_health = AsyncMock(return_value=True)

        request = MagicMock()
        request.app = app

        # Act
        with patch.object(health_module, "check_db_health", AsyncMock(return_value=True)):
            response = await health_check(request)

        # Assert
        assert response.components["telegram"] == "not_configured"
    finally:
        health_module._health_cache.clear()
        health_module._health_cache.update(original_cache)


@pytest.mark.asyncio
async def test_degraded_startup_configuration_error_preserves_code() -> None:
    """ConfigurationError при запуске сохраняет код ошибки."""
    # Arrange
    from src.services.application_lifecycle_service import ApplicationLifecycleService

    settings = _make_settings(db_password="")
    lifecycle_service = ApplicationLifecycleService(settings)

    mock_db_pool = MagicMock()

    patches = _create_lifecycle_patches(
        settings_obj=settings,
        db_pool_mock=mock_db_pool,
        validate_settings_raises=ConfigurationError("CONF-003", "DB_PASSWORD не указан"),
    )

    # Act & Assert
    with ExitStack() as stack:
        _enter_all_patches(stack, patches)
        with pytest.raises(ConfigurationError) as exc_info:
            await lifecycle_service.initialize()

    assert exc_info.value.code == "CONF-003"
    assert exc_info.value.message is not None


@pytest.mark.asyncio
async def test_health_endpoint_overall_status_when_not_configured() -> None:
    """При telegram_configured=False и здоровых компонентах overall_status равен 'ok'."""
    # Arrange
    import time
    from src.api.endpoints import health as health_module
    from src.api.endpoints.health import health_check

    original_cache = dict(health_module._health_cache)
    try:
        health_module._health_cache["emb_time"] = int(time.time())
        health_module._health_cache["emb_status"] = True
        health_module._health_cache["llm_time"] = int(time.time())
        health_module._health_cache["llm_status"] = True

        app = MagicMock()
        app.state.telegram_configured = False
        app.state.embeddings = AsyncMock()
        app.state.embeddings.check_health = AsyncMock(return_value=True)
        app.state.llm = AsyncMock()
        app.state.llm.check_health = AsyncMock(return_value=True)

        request = MagicMock()
        request.app = app

        # Act
        with patch.object(health_module, "check_db_health", AsyncMock(return_value=True)):
            response = await health_check(request)

        # Assert
        assert response.components["telegram"] == "not_configured"
        assert response.status == "ok"
    finally:
        health_module._health_cache.clear()
        health_module._health_cache.update(original_cache)
