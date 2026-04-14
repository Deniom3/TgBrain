"""
Загрузчик настроек из базы данных.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from .exceptions import ConfigurationError
from .masking import mask_api_key

if TYPE_CHECKING:
    from .settings import Settings, SettingsWithProviders
    from src.settings.repositories.telegram_auth import TelegramAuthRepository
    from src.settings.repositories.llm_providers import LLMProvidersRepository
    from src.settings.repositories.embedding_providers import EmbeddingProvidersRepository
    from src.settings.repositories.app_settings import AppSettingsRepository

logger = logging.getLogger(__name__)

_reload_lock: asyncio.Lock | None = None


def _get_reload_lock() -> asyncio.Lock:
    """Lazy инициализация lock для тестовой совместимости."""
    global _reload_lock
    if _reload_lock is None:
        _reload_lock = asyncio.Lock()
    return _reload_lock


async def load_settings_from_db(
    telegram_auth_repo: TelegramAuthRepository | None = None,
    llm_providers_repo: LLMProvidersRepository | None = None,
    embedding_providers_repo: EmbeddingProvidersRepository | None = None,
    app_settings_repo: AppSettingsRepository | None = None,
) -> SettingsWithProviders:
    """
    Загрузить настройки из БД и обновить глобальный settings.

    Args:
        telegram_auth_repo: Репозиторий для загрузки Telegram auth (опционально)
        llm_providers_repo: Репозиторий для загрузки LLM провайдеров (опционально)
        embedding_providers_repo: Репозиторий для загрузки embedding провайдеров (опционально)
        app_settings_repo: Репозиторий для загрузки app settings (опционально)

    Returns:
        Обновлённый экземпляр SettingsWithProviders.
    """
    from .settings import get_settings
    from ..models.data_models import EmbeddingProvider
    from ..settings import (
        TelegramAuthRepository,
        LLMProvidersRepository,
        EmbeddingProvidersRepository,
        AppSettingsRepository,
    )
    from src.database import get_pool

    # Получаем кэшированный экземпляр (он уже типа SettingsWithProviders)
    current_settings = get_settings()

    # Создаём временные репозитории если не переданы
    if not telegram_auth_repo or not llm_providers_repo or not embedding_providers_repo or not app_settings_repo:
        from src.database import get_pool
        pool = await get_pool()
        
        if not telegram_auth_repo:
            from src.settings.repositories.telegram_auth import TelegramAuthRepository
            telegram_auth_repo = TelegramAuthRepository(pool)
        if not llm_providers_repo:
            from src.settings.repositories.llm_providers import LLMProvidersRepository
            llm_providers_repo = LLMProvidersRepository(pool)
        if not embedding_providers_repo:
            from src.settings.repositories.embedding_providers import EmbeddingProvidersRepository
            embedding_providers_repo = EmbeddingProvidersRepository(pool)
        if not app_settings_repo:
            from src.settings.repositories.app_settings import AppSettingsRepository
            app_settings_repo = AppSettingsRepository(pool)

    # Загружаем настройки из БД
    telegram_auth = await telegram_auth_repo.get()
    llm_providers = await llm_providers_repo.get_all()
    embedding_providers: list[EmbeddingProvider] = await embedding_providers_repo.get_all()
    app_settings_dict = await app_settings_repo.get_dict()

    # Собираем все значения из БД в dict для атомарного model_copy
    update_fields: dict[str, object] = {}

    # Telegram auth поля
    if telegram_auth:
        if telegram_auth.api_id:
            update_fields["tg_api_id"] = telegram_auth.api_id.value
        if telegram_auth.api_hash:
            update_fields["tg_api_hash"] = telegram_auth.api_hash.value
        if telegram_auth.phone_number:
            update_fields["tg_phone_number"] = telegram_auth.phone_number.value
        # session_name и session_data хранятся только в БД, не обновляем settings

    # LLM провайдеры из БД
    active_provider = None
    for provider in llm_providers:
        if provider.name == "gemini":
            if provider.api_key:
                update_fields["gemini_api_key"] = provider.api_key
            update_fields["gemini_base_url"] = provider.base_url
            update_fields["gemini_model"] = provider.model
            if provider.is_active:
                active_provider = "gemini"
        elif provider.name == "openrouter":
            if provider.api_key:
                update_fields["openrouter_api_key"] = provider.api_key
            update_fields["openrouter_base_url"] = provider.base_url
            update_fields["openrouter_model"] = provider.model
            if provider.is_active:
                active_provider = "openrouter"
        elif provider.name == "ollama":
            update_fields["ollama_llm_base_url"] = provider.base_url
            update_fields["ollama_llm_model"] = provider.model
            update_fields["ollama_llm_enabled"] = provider.is_enabled
            if provider.is_active:
                active_provider = "ollama"
        elif provider.name == "lm-studio":
            update_fields["lm_studio_base_url"] = provider.base_url
            update_fields["lm_studio_model"] = provider.model
            update_fields["lm_studio_enabled"] = provider.is_enabled
            if provider.is_active:
                active_provider = "lm-studio"

    if active_provider:
        update_fields["llm_active_provider"] = active_provider

    # Провайдеры эмбеддинга из БД
    active_embedding_provider = None
    for emb_provider in embedding_providers:  # type: EmbeddingProvider
        if emb_provider.name == "ollama":
            update_fields["ollama_embedding_url"] = emb_provider.base_url
            update_fields["ollama_embedding_model"] = emb_provider.model
            if emb_provider.embedding_dim:
                update_fields["ollama_embedding_dim"] = emb_provider.embedding_dim
            update_fields["ollama_embedding_max_retries"] = emb_provider.max_retries
            update_fields["ollama_embedding_timeout"] = emb_provider.timeout
            update_fields["ollama_embedding_normalize"] = emb_provider.normalize
            if emb_provider.is_active:
                active_embedding_provider = "ollama"
        elif emb_provider.name == "gemini":
            if emb_provider.api_key:
                update_fields["gemini_api_key"] = emb_provider.api_key
            update_fields["gemini_embedding_model"] = emb_provider.model
            update_fields["gemini_embedding_dim"] = emb_provider.embedding_dim
            update_fields["gemini_embedding_max_retries"] = emb_provider.max_retries
            update_fields["gemini_embedding_timeout"] = emb_provider.timeout
            update_fields["gemini_embedding_normalize"] = emb_provider.normalize
            if emb_provider.is_active:
                active_embedding_provider = "gemini"
        elif emb_provider.name == "openrouter":
            if emb_provider.api_key:
                update_fields["openrouter_api_key"] = emb_provider.api_key
            update_fields["openrouter_embedding_model"] = emb_provider.model
            update_fields["openrouter_embedding_dim"] = emb_provider.embedding_dim
            update_fields["openrouter_embedding_max_retries"] = emb_provider.max_retries
            update_fields["openrouter_embedding_timeout"] = emb_provider.timeout
            update_fields["openrouter_embedding_normalize"] = emb_provider.normalize
            if emb_provider.is_active:
                active_embedding_provider = "openrouter"
        elif emb_provider.name == "lm-studio":
            if emb_provider.api_key:
                update_fields["lm_studio_embedding_api_key"] = emb_provider.api_key
            update_fields["lm_studio_embedding_url"] = emb_provider.base_url
            update_fields["lm_studio_embedding_model"] = emb_provider.model
            update_fields["lm_studio_embedding_dim"] = emb_provider.embedding_dim
            update_fields["lm_studio_embedding_max_retries"] = emb_provider.max_retries
            update_fields["lm_studio_embedding_timeout"] = emb_provider.timeout
            update_fields["lm_studio_embedding_normalize"] = emb_provider.normalize
            if emb_provider.is_active:
                active_embedding_provider = "lm-studio"

    if active_embedding_provider:
        update_fields["ollama_embedding_provider"] = active_embedding_provider

    # Timezone из БД
    app_timezone = app_settings_dict.get("app.timezone")
    if app_timezone:
        update_fields["timezone"] = app_timezone
        logger.info("Timezone загружен из БД: %s", app_timezone)

    # Атомарно создаём новый экземпляр через model_copy
    new_settings = current_settings.model_copy(update=update_fields)

    changed_fields = list(update_fields.keys())
    logger.debug(
        "Settings loaded from DB: %d fields updated: %s",
        len(changed_fields),
        ", ".join(changed_fields),
    )
    logger.info("Настройки загружены из БД")

    return new_settings


async def reload_settings() -> "SettingsWithProviders":
    """
    Перезагрузить настройки из БД (для использования в runtime).

    Защищено asyncio.Lock от concurrent вызовов.
    Порядок операций: загрузка → cache_clear → обновление ссылки → обновление сервисов.
    Это предотвращает потерю настроек при падении БД.

    Returns:
        Обновлённый экземпляр SettingsWithProviders.
    """
    from .settings import get_settings

    logger.debug("Waiting for settings lock...")
    async with _get_reload_lock():
        logger.debug("Settings lock acquired")

        # Сначала загружаем из БД (до очистки кэша)
        new_settings = await load_settings_from_db()

        # Только после успешной загрузки очищаем кэш
        get_settings.cache_clear()

        # Обновляем глобальную переменную в модуле config
        import src.config as config_module
        config_module.settings = new_settings

        # Обновляем ссылку в долгоживущих сервисах
        try:
            _refresh_services(new_settings)
        except Exception as e:
            logger.error("Ошибка обновления сервисов: %s", type(e).__name__)
            # config.settings уже обновлён, сервисы будут обновлены при следующем reload

        logger.info("Settings reloaded from DB: new instance created via model_copy")

        return new_settings


def _refresh_services(new_settings: "SettingsWithProviders") -> None:
    """Обновить ссылку на Settings во всех долгоживущих сервисах.

    Args:
        new_settings: Новый экземпляр Settings.
    """
    from src.common.application_state import AppStateStore

    if not AppStateStore.is_initialized():
        logger.debug("AppStateStore не инициализирован, обновление сервисов пропущено")
        return

    app = AppStateStore.get_app()
    state = app.state

    if hasattr(state, "llm") and state.llm is not None:
        state.llm.refresh_config(new_settings)

    if hasattr(state, "embeddings") and state.embeddings is not None:
        state.embeddings.refresh_config(new_settings)

    if hasattr(state, "rag") and state.rag is not None:
        state.rag.refresh_config(new_settings)

    if hasattr(state, "reindex") and state.reindex is not None:
        state.reindex.refresh_config(new_settings)

    if hasattr(state, "ingester") and state.ingester is not None:
        state.ingester.refresh_config(new_settings)

    if hasattr(state, "summary_webhook_service") and state.summary_webhook_service is not None:
        state.summary_webhook_service.refresh_config(new_settings)

    logger.info("Долгоживущие сервисы обновлены новыми Settings")


async def validate_settings(settings: "SettingsWithProviders") -> None:
    """
    Проверка обязательных полей. Бросает ConfigurationError при первой найденной ошибке.

    Args:
        settings: Экземпляр настроек.

    Raises:
        ConfigurationError: При отсутствии обязательных настроек.
            CONF-003 — DB_PASSWORD не указан.
            CONF-004 — API ключ для облачного провайдера не указан.
            CONF-005 — Telegram auth не настроен.
    """
    if not settings.db_password:
        raise ConfigurationError(
            "CONF-003",
            "DB_PASSWORD не указан",
            context={"missing": "DB_PASSWORD"},
        )

    try:
        provider_config = settings.get_provider_config()
        if provider_config.api_key is None and provider_config.name not in ("ollama", "lm-studio"):
            raise ConfigurationError(
                "CONF-004",
                f"API ключ для {provider_config.name} не указан",
                context={"provider": provider_config.name},
            )
    except ValueError as e:
        raise ConfigurationError("CONF-004", str(e)) from e


async def validate_telegram_auth(settings: "SettingsWithProviders") -> None:
    """
    Проверка наличия Telegram авторизации. Бросает ConfigurationError при ошибках.

    Args:
        settings: Экземпляр настроек.

    Raises:
        ConfigurationError: При отсутствии Telegram credentials.
            CONF-005 — TG_API_ID или TG_API_HASH не настроены.
    """
    missing: list[str] = []
    if not settings.tg_api_id:
        missing.append("TG_API_ID")
    if not settings.tg_api_hash:
        missing.append("TG_API_HASH")

    if missing:
        raise ConfigurationError(
            "CONF-005",
            f"Telegram auth не настроен: отсутствуют {', '.join(missing)}",
            context={"missing_fields": missing},
        )


def print_settings(settings: "Settings") -> None:
    """
    Вывод конфигурации в лог (без чувствительных данных).

    Args:
        settings: Экземпляр настроек.
    """
    import logging
    
    logger = logging.getLogger(__name__)
    embedding_cfg = settings.embedding_config
    
    logger.info("=" * 50)
    logger.info("Конфигурация приложения")
    logger.info("=" * 50)
    logger.info(f"Telegram API ID: {settings.tg_api_id}")
    logger.info("Telegram сессия: (хранится в БД)")
    logger.info("Чаты для мониторинга: (из БД через ChatSettingsRepository)")
    logger.info(f"БД: {settings.db_host}:{settings.db_port}/{settings.db_name}")
    logger.info(f"Активный LLM провайдер: {settings.llm_active_provider}")

    # Информация о провайдере
    try:
        provider_config = settings.get_provider_config()
        api_key_masked = mask_api_key(provider_config.api_key) if provider_config.api_key else "N/A"
        logger.info(f"  API Key: {api_key_masked}")
        logger.info(f"  Base URL: {provider_config.base_url}")
        logger.info(f"  Model: {provider_config.model}")
    except ValueError:
        pass

    ollama = embedding_cfg.ollama
    logger.info(f"Ollama Embedding: {ollama.url} ({ollama.model})")
    logger.info(f"Embedding провайдер: {settings.ollama_embedding_provider}")
    logger.info(f"Log Level: {settings.log_level}")
    logger.info("=" * 50)
