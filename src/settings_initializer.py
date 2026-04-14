"""
Сервис инициализации и синхронизации настроек приложения.

При запуске приложения:
1. Загружает настройки из .env через Settings
2. Сохраняет их в БД (telegram_auth, llm_providers, app_settings, chat_settings)
3. При последующих запусках обновляет БД из .env

Это позволяет:
- Хранить настройки в БД для доступа через веб-интерфейс
- Использовать .env как первоисточник при запуске
- Изменять настройки через API во время работы
"""

import logging
from typing import Any, cast

from .config import Settings, SettingsWithProviders, get_settings
from .settings import (
    TelegramAuthRepository,
    LLMProvidersRepository,
    EmbeddingProvidersRepository,
    AppSettingsRepository,
    ChatSettingsRepository,
)
from .settings.repositories.pending_cleanup_repository import (
    PENDING_TTL_DESCRIPTION,
    PENDING_INTERVAL_DESCRIPTION,
)
from .utils.session_utils import session_name_to_str

logger = logging.getLogger(__name__)


class SettingsInitializer:
    """
    Сервис инициализации настроек приложения.

    Синхронизирует настройки из .env в БД при старте приложения.
    """

    @staticmethod
    async def initialize(
        telegram_auth_repo: TelegramAuthRepository | None = None,
        llm_providers_repo: LLMProvidersRepository | None = None,
        embedding_providers_repo: EmbeddingProvidersRepository | None = None,
        app_settings_repo: AppSettingsRepository | None = None,
    ) -> bool:
        """
        Инициализировать все настройки из .env в БД.

        Args:
            telegram_auth_repo: Репозиторий для Telegram auth (опционально)
            llm_providers_repo: Репозиторий для LLM провайдеров (опционально)
            embedding_providers_repo: Репозиторий для embedding провайдеров (опционально)
            app_settings_repo: Репозиторий для app settings (опционально)

        Returns:
            True если успешно.
        """
        logger.info("Инициализация настроек из .env в БД...")

        try:
            # Получаем настройки из .env
            settings = get_settings()

            # Инициализируем каждую категорию
            await SettingsInitializer._init_telegram_auth(settings, telegram_auth_repo)
            await SettingsInitializer._init_llm_providers(settings, llm_providers_repo)
            await SettingsInitializer._init_embedding_providers(settings, embedding_providers_repo)
            await SettingsInitializer._init_app_settings(settings, app_settings_repo)
            await SettingsInitializer._init_chat_settings(settings)

            logger.info("Настройки успешно инициализированы в БД")
            return True

        except Exception as e:
            # Допустимо на границе инициализации: метод вызывается один раз
            # при старте приложения и не должен приводить к аварийному завершению.
            # Все внутренние ошибки логгируются, а возврат False позволяет
            # приложению продолжить работу с частично инициализированными настройками.
            logger.error("Ошибка инициализации настроек: %s", type(e).__name__)
            return False

    @staticmethod
    async def _init_telegram_auth(settings: Settings, telegram_auth_repo: TelegramAuthRepository | None = None) -> None:
        """Инициализировать настройки Telegram авторизации.

        TG_API_ID и TG_API_HASH берутся из .env и сохраняются в БД.
        TG_SESSION_NAME НЕ используется из .env - генерируется только через QR.
        TG_PHONE_NUMBER - необязательный параметр, обновляется только если указан в .env.
        """
        logger.info("Синхронизация настроек Telegram...")

        # Определяем какие значения использовать
        api_id = settings.tg_api_id
        api_hash = settings.tg_api_hash

        # Получаем текущие настройки из БД
        if telegram_auth_repo:
            existing = await telegram_auth_repo.get()
        else:
            # Fallback: создаём временный экземпляр
            from src.database import get_pool
            pool = await get_pool()
            temp_repo = TelegramAuthRepository(pool)
            existing = await temp_repo.get()

        # Session name берем ТОЛЬКО из БД (если есть)
        # При первом запуске оставляем пустым - будет заполнен при QR авторизации
        session_name = None
        if existing and existing.session_name:
            # Конвертируем SessionName VO в строку
            session_name = session_name_to_str(existing.session_name)

        # Phone number обновляем только если указан в .env
        if settings.tg_phone_number:
            phone_number = settings.tg_phone_number
        elif existing and existing.phone_number:
            # Конвертируем PhoneNumber VO в строку
            phone_number = existing.phone_number.value
        else:
            phone_number = None

        if existing and existing.api_id and existing.api_hash:
            # Если в БД уже есть настройки, проверяем, изменились ли они в .env
            if (api_id and api_id != existing.api_id) or \
               (api_hash and api_hash != existing.api_hash):
                logger.info(
                    "  Обновление настроек Telegram из .env (API ID: %s)",
                    api_id,
                )
            else:
                logger.info(
                    "  Telegram настройки уже присутствуют в БД (API ID: %s)",
                    existing.api_id,
                )
        else:
            logger.info(
                "  Инициализация настроек Telegram из .env (API ID: %s)",
                api_id,
            )

        # Сохраняем в БД
        repo_to_use = telegram_auth_repo
        if not repo_to_use:
            from src.database import get_pool
            pool = await get_pool()
            repo_to_use = TelegramAuthRepository(pool)
        
        await repo_to_use.upsert(
            api_id=api_id,
            api_hash=api_hash,
            phone_number=phone_number,
            session_name=session_name,
        )

        logger.info("  Session: %s", session_name if session_name else "не установлена (будет при QR)")
        if phone_number:
            logger.info("  Phone: %s", phone_number)
        else:
            logger.info("  Phone: не указан (необязательный)")

    @staticmethod
    async def _init_llm_providers(settings: Settings, llm_providers_repo: LLMProvidersRepository | None = None) -> None:
        """Инициализировать настройки LLM провайдеров.

        Настройки из .env используются только для первичной инициализации.
        Если провайдер уже существует в БД (api_key не null или model не пуст),
        то настройки НЕ переопределяются из .env.
        
        Args:
            settings: Настройки приложения
            llm_providers_repo: Репозиторий для LLM провайдеров (опционально)
        """
        logger.info("Синхронизация настроек LLM провайдеров...")

        # Создаём временный репозиторий если не передан
        if not llm_providers_repo:
            from src.database import get_pool
            from src.settings.repositories.llm_providers import LLMProvidersRepository
            pool = await get_pool()
            llm_providers_repo = LLMProvidersRepository(pool)

        providers_config = [
            {
                "name": "gemini",
                "is_active": settings.llm_active_provider.lower() == "gemini",
                "api_key": settings.gemini_api_key,
                "base_url": settings.gemini_base_url,
                "model": settings.gemini_model,
                "is_enabled": True,
                "priority": 1,
                "description": "Google Gemini API",
            },
            {
                "name": "openrouter",
                "is_active": settings.llm_active_provider.lower() == "openrouter",
                "api_key": settings.openrouter_api_key,
                "base_url": settings.openrouter_base_url,
                "model": settings.openrouter_model,
                "is_enabled": True,
                "priority": 2,
                "description": "OpenRouter API (300+ моделей)",
            },
            {
                "name": "ollama",
                "is_active": settings.llm_active_provider.lower() == "ollama",
                "api_key": None,
                "base_url": settings.ollama_llm_base_url,
                "model": settings.ollama_llm_model,
                "is_enabled": settings.ollama_llm_enabled,
                "priority": 3,
                "description": "Локальный Ollama сервер",
            },
            {
                "name": "lm-studio",
                "is_active": settings.llm_active_provider.lower() in ["lm-studio", "lm_studio"],
                "api_key": None,
                "base_url": settings.lm_studio_base_url,
                "model": settings.lm_studio_model,
                "is_enabled": settings.lm_studio_enabled,
                "priority": 4,
                "description": "Локальный LM Studio",
            },
        ]

        for provider_cfg in providers_config:
            # Проверяем существует ли уже провайдер в БД
            existing = await llm_providers_repo.get(provider_cfg['name'])  # type: ignore[arg-type]
            
            if existing and (existing.api_key or existing.model):
                # Провайдер уже настроен в БД — НЕ переопределяем из .env
                logger.info(
                    "  %s: пропущено (уже настроен в БД)",
                    provider_cfg['name'],
                )
            else:
                # Провайдер не настроен — инициализируем из .env
                await llm_providers_repo.upsert(**provider_cfg)  # type: ignore[arg-type]
                logger.info(
                    "  %s: active=%s, enabled=%s, model=%s (из .env)",
                    provider_cfg['name'],
                    provider_cfg['is_active'],
                    provider_cfg['is_enabled'],
                    provider_cfg['model'],
                )

    @staticmethod
    async def _init_embedding_providers(
        settings: Settings,
        embedding_providers_repo: EmbeddingProvidersRepository | None = None,
    ) -> None:
        """Инициализировать настройки провайдеров эмбеддингов."""
        logger.info("Синхронизация настроек провайдеров эмбеддингов...")

        # Создаём временный репозиторий если не передан
        if not embedding_providers_repo:
            from src.database import get_pool
            from src.settings.repositories.embedding_providers import EmbeddingProvidersRepository
            pool = await get_pool()
            embedding_providers_repo = EmbeddingProvidersRepository(pool)
        
        # Получаем текущую модель из БД для сравнения
        ollama_provider = await embedding_providers_repo.get("ollama")
        db_model = ollama_provider.model if ollama_provider else None
        db_dim = ollama_provider.embedding_dim if ollama_provider else None
        
        # Используем nested config для получения начальных настроек
        emb_cfg_initial = settings.embedding_config
        
        # Определяем размерность для Ollama
        # Если модель изменилась или размерность не установлена - запрашиваем у сервера
        ollama_dim = emb_cfg_initial.ollama.dim
        
        if not ollama_dim or (db_model and db_model != emb_cfg_initial.ollama.model):
            if db_model and db_model != emb_cfg_initial.ollama.model:
                logger.info(
                    "Модель Ollama изменилась: %s → %s. "
                    "Запрос размерности...",
                    db_model,
                    emb_cfg_initial.ollama.model,
                )
            
            # Запрашиваем размерность у сервера
            try:
                from src.embeddings.providers import OllamaEmbeddingProvider
                
                temp_provider = OllamaEmbeddingProvider(
                    base_url=emb_cfg_initial.ollama.url,
                    model=emb_cfg_initial.ollama.model,
                    dimension=768
                )
                
                ollama_dim = await temp_provider.get_embedding_dimension(force=True)
                await temp_provider.close()
                
                if ollama_dim and ollama_dim > 0:
                    logger.info(
                        "Получена размерность для %s: %s",
                        emb_cfg_initial.ollama.model,
                        ollama_dim,
                    )
                    new_settings = settings.model_copy(update={"ollama_embedding_dim": ollama_dim})
                    settings = cast(SettingsWithProviders, new_settings)
                    import src.config as config_module
                    config_module.settings = settings
                    logger.debug("Settings updated: ollama_embedding_dim set to %s via model_copy", ollama_dim)
                else:
                    logger.warning(
                        "Не удалось получить размерность, используем 768"
                    )
                    ollama_dim = 768

            except Exception as e:
                # Fallback-поведение на границе инициализации: если Ollama
                # недоступен при старте, используем размерность по умолчанию (768).
                # Приложение продолжит работу, а размерность будет скорректирована
                # при первом успешном запросе к Ollama.
                logger.warning(
                    "Ошибка получения размерности: %s, используем 768",
                    type(e).__name__,
                )
                ollama_dim = 768
        else:
            logger.info(
                "Используем размерность из БД: %s для модели %s",
                db_dim,
                db_model,
            )
            ollama_dim = db_dim or ollama_dim or 768

        # Перечитываем nested config после мутации flat-поля,
        # чтобы snapshot содержал актуальные данные
        emb_cfg = settings.embedding_config
        ollama = emb_cfg.ollama
        gemini = emb_cfg.gemini
        openrouter = emb_cfg.openrouter
        lm_studio = emb_cfg.lm_studio

        embedding_providers_config = [
            {
                "name": "ollama",
                "is_active": settings.ollama_embedding_provider.lower() == "ollama",
                "api_key": None,
                "base_url": ollama.url,
                "model": ollama.model,
                "is_enabled": True,
                "priority": 1,
                "description": "Локальный Ollama сервер для эмбеддингов",
                "embedding_dim": ollama_dim,
                "max_retries": ollama.max_retries,
                "timeout": ollama.timeout,
                "normalize": ollama.normalize,
            },
            {
                "name": "gemini",
                "is_active": settings.ollama_embedding_provider.lower() == "gemini",
                "api_key": settings.gemini_api_key,
                "base_url": settings.gemini_base_url,
                "model": gemini.model,
                "is_enabled": True,
                "priority": 2,
                "description": "Google Gemini Embeddings API",
                "embedding_dim": gemini.dim,
                "max_retries": gemini.max_retries,
                "timeout": gemini.timeout,
                "normalize": gemini.normalize,
            },
            {
                "name": "openrouter",
                "is_active": settings.ollama_embedding_provider.lower() == "openrouter",
                "api_key": settings.openrouter_api_key,
                "base_url": settings.openrouter_base_url,
                "model": openrouter.model,
                "is_enabled": True,
                "priority": 3,
                "description": "OpenRouter Embeddings API",
                "embedding_dim": openrouter.dim,
                "max_retries": openrouter.max_retries,
                "timeout": openrouter.timeout,
                "normalize": openrouter.normalize,
            },
            {
                "name": "lm-studio",
                "is_active": settings.ollama_embedding_provider.lower() == "lm-studio",
                "api_key": lm_studio.api_key,
                "base_url": lm_studio.url,
                "model": lm_studio.model,
                "is_enabled": True,
                "priority": 4,
                "description": "Локальный LM Studio для эмбеддингов",
                "embedding_dim": lm_studio.dim,
                "max_retries": lm_studio.max_retries,
                "timeout": lm_studio.timeout,
                "normalize": lm_studio.normalize,
            },
        ]

        for provider_cfg in embedding_providers_config:
            await embedding_providers_repo.upsert(**provider_cfg)  # type: ignore[arg-type]
            logger.info(
                "  %s: active=%s, enabled=%s, model=%s, dim=%s",
                provider_cfg['name'],
                provider_cfg['is_active'],
                provider_cfg['is_enabled'],
                provider_cfg['model'],
                provider_cfg['embedding_dim'],
            )

    @staticmethod
    async def _init_app_settings(
        settings: Settings,
        app_settings_repo: AppSettingsRepository | None = None,
    ) -> None:
        """Инициализировать общие настройки приложения."""
        logger.info("Синхронизация общих настроек...")

        # Создаём временный репозиторий если не передан
        if not app_settings_repo:
            from src.database import get_pool
            from src.settings.repositories.app_settings import AppSettingsRepository
            pool = await get_pool()
            app_settings_repo = AppSettingsRepository(pool)

        app_settings_config = [
            {
                "key": "app.timezone",
                "value": settings.timezone,
                "value_type": "string",
                "description": "Timezone приложения для конвертации локального времени в UTC",
                "is_sensitive": False,
            },
            {
                "key": "llm_fallback_providers",
                "value": settings.llm_fallback_providers,
                "value_type": "string",
                "description": "Список fallback провайдеров",
                "is_sensitive": False,
            },
            {
                "key": "llm_auto_fallback",
                "value": str(settings.llm_auto_fallback).lower(),
                "value_type": "bool",
                "description": "Автоматический fallback",
                "is_sensitive": False,
            },
            {
                "key": "llm_fallback_timeout",
                "value": str(settings.llm_fallback_timeout),
                "value_type": "int",
                "description": "Таймаут проверки провайдера (сек)",
                "is_sensitive": False,
            },
            {
                "key": "log_level",
                "value": settings.log_level,
                "value_type": "string",
                "description": "Уровень логирования",
                "is_sensitive": False,
            },
            {
                "key": "summary_default_hours",
                "value": str(settings.summary_default_hours),
                "value_type": "int",
                "description": "Период сводки по умолчанию (часы)",
                "is_sensitive": False,
            },
            {
                "key": "summary_max_messages",
                "value": str(settings.summary_max_messages),
                "value_type": "int",
                "description": "Максимум сообщений для сводки",
                "is_sensitive": False,
            },
            {
                "key": "rag_top_k",
                "value": str(settings.rag_top_k),
                "value_type": "int",
                "description": "Количество результатов для RAG",
                "is_sensitive": False,
            },
            {
                "key": "rag_score_threshold",
                "value": str(settings.rag_score_threshold),
                "value_type": "float",
                "description": "Порог схожести для RAG",
                "is_sensitive": False,
            },
            {
                "key": "summary.cleanup.pending_timeout_minutes",
                "value": "60",
                "value_type": "integer",
                "description": "Через сколько минут удалять застрявшие pending задачи (1 час)",
                "is_sensitive": False,
            },
            {
                "key": "summary.cleanup.processing_timeout_minutes",
                "value": "5",
                "value_type": "integer",
                "description": "Через сколько минут переводить processing в failed",
                "is_sensitive": False,
            },
            {
                "key": "summary.cleanup.failed_retention_minutes",
                "value": "120",
                "value_type": "integer",
                "description": "Через сколько минут удалять failed задачи (2 часа)",
                "is_sensitive": False,
            },
            {
                "key": "summary.cleanup.completed_retention_minutes",
                "value": None,
                "value_type": "integer",
                "description": "Через сколько минут удалять completed (None = не удалять)",
                "is_sensitive": False,
            },
            {
                "key": "summary.cleanup.auto_enabled",
                "value": "true",
                "value_type": "boolean",
                "description": "Включить/отключить автоматическую очистку",
                "is_sensitive": False,
            },
            {
                "key": "pending.ttl_minutes",
                "value": "240",
                "value_type": "integer",
                "description": PENDING_TTL_DESCRIPTION,
                "is_sensitive": False,
            },
            {
                "key": "pending.cleanup_interval_minutes",
                "value": "60",
                "value_type": "integer",
                "description": PENDING_INTERVAL_DESCRIPTION,
                "is_sensitive": False,
            },
        ]

        for setting_cfg in app_settings_config:
            # Используем upsert_if_not_exists чтобы не перезаписывать
            # изменённые пользователем настройки при перезапуске
            await app_settings_repo.upsert_if_not_exists(**setting_cfg)  # type: ignore[arg-type]

        logger.info("  Синхронизировано %s настроек", len(app_settings_config))

    @staticmethod
    async def _init_chat_settings(settings: Settings) -> None:
        """Инициализировать настройки чатов."""
        logger.info("Синхронизация настроек чатов...")

        from src.database import get_pool
        from src.settings import ChatSettingsRepository

        # Используем новые поля tg_chat_enable и tg_chat_disable
        enable_list = settings.tg_chat_enable_list
        disable_list = settings.tg_chat_disable_list

        if not enable_list and not disable_list:
            logger.info("  Чаты для мониторинга не указаны (TG_CHAT_ENABLE / TG_CHAT_DISABLE)")
            return

        pool = await get_pool()
        repo = ChatSettingsRepository(pool)

        # Включаем чаты из enable_list
        for chat_id in enable_list:
            await repo.upsert(
                chat_id=chat_id,
                title=f"Chat {chat_id}",
                is_monitored=True,
                summary_enabled=True,
            )
            logger.info("  Чат %s: добавлен и включён", chat_id)

        # Отключаем чаты из disable_list
        for chat_id in disable_list:
            await repo.upsert(
                chat_id=chat_id,
                title=f"Chat {chat_id}",
                is_monitored=False,
                summary_enabled=False,
            )
            logger.info("  Чат %s: добавлен и отключён", chat_id)

    @staticmethod
    async def get_current_config(
        telegram_auth_repo: TelegramAuthRepository | None = None,
        llm_providers_repo: LLMProvidersRepository | None = None,
        embedding_providers_repo: EmbeddingProvidersRepository | None = None,
        app_settings_repo: AppSettingsRepository | None = None,
        chat_settings_repo: ChatSettingsRepository | None = None,
    ) -> dict[str, Any]:
        """
        Получить текущую конфигурацию из БД.

        Args:
            telegram_auth_repo: Репозиторий для Telegram auth (опционально)
            llm_providers_repo: Репозиторий для LLM провайдеров (опционально)
            embedding_providers_repo: Репозиторий для embedding провайдеров (опционально)
            app_settings_repo: Репозиторий для app settings (опционально)
            chat_settings_repo: Репозиторий для chat settings (опционально)

        Returns:
            Словарь с текущими настройками.
        """
        from src.database import get_pool
        
        # Создаём временные репозитории если не переданы
        pool = None
        if not telegram_auth_repo or not llm_providers_repo or not embedding_providers_repo or not app_settings_repo or not chat_settings_repo:
            pool = await get_pool()
            if not pool:
                raise RuntimeError("Database pool not available")
        
        if not telegram_auth_repo:
            telegram_auth_repo = TelegramAuthRepository(pool)
        if not llm_providers_repo:
            llm_providers_repo = LLMProvidersRepository(pool)
        if not embedding_providers_repo:
            embedding_providers_repo = EmbeddingProvidersRepository(pool)
        if not app_settings_repo:
            app_settings_repo = AppSettingsRepository(pool)
        if not chat_settings_repo:
            chat_settings_repo = ChatSettingsRepository(pool)
        
        telegram_auth = await telegram_auth_repo.get()
        llm_providers = await llm_providers_repo.get_all()
        embedding_providers = await embedding_providers_repo.get_all()
        app_settings = await app_settings_repo.get_all()
        chat_settings = await chat_settings_repo.get_all()

        active_provider = next((p for p in llm_providers if p.is_active), None)
        active_embedding_provider = next((p for p in embedding_providers if p.is_active), None)

        return {
            "telegram": {
                "configured": bool(telegram_auth and telegram_auth.api_id),
                "api_id": telegram_auth.api_id if telegram_auth else None,
                "session_name": telegram_auth.session_name if telegram_auth else None,
            },
            "llm": {
                "active_provider": active_provider.name if active_provider else None,
                "providers_count": len(llm_providers),
                "providers": [p.name for p in llm_providers],
            },
            "embedding": {
                "active_provider": active_embedding_provider.name if active_embedding_provider else None,
                "providers_count": len(embedding_providers),
                "providers": [p.name for p in embedding_providers],
            },
            "app": {
                "settings_count": len(app_settings),
            },
            "chats": {
                "monitored_count": len([c for c in chat_settings if c.is_monitored]),
                "total_count": len(chat_settings),
            },
        }
