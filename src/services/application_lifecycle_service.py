"""
Сервис управления жизненным циклом приложения.

Инкапсулирует логику инициализации и очистки всех компонентов приложения.
"""

import logging
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Dict

from src.rate_limiter.models import FloodWaitIncident

if TYPE_CHECKING:
    from src.config import Settings

logger = logging.getLogger(__name__)

FloodWaitCallback = Callable[[FloodWaitIncident], Coroutine[Any, Any, None]]


class ApplicationLifecycleService:
    """
    Сервис управления жизненным циклом приложения.
    
    Отвечает за:
    - Инициализацию всех компонентов при старте
    - Очистку всех компонентов при остановке
    - Проверку конфигурации
    
    Example:
        service = ApplicationLifecycleService(settings)
        state = await service.initialize()
        # ... работа приложения ...
        await service.cleanup(state)
    """
    
    def __init__(self, settings: "Settings") -> None:
        """
        Инициализировать сервис.
        
        Args:
            settings: Настройки приложения.
        """
        self.settings = settings
    
    def refresh_config(self, new_settings: "Settings") -> None:
        """Обновить ссылку на Settings после reload.

        Args:
            new_settings: Новый экземпляр Settings.
        """
        self.settings = new_settings
        logger.debug("ApplicationLifecycleService обновлён")

    async def initialize(self) -> Dict[str, Any]:
        """
        Инициализировать все компоненты приложения.
        
        Returns:
            Словарь с инициализированными компонентами.
            
        Raises:
            ConfigurationError: Если конфигурация невалидна.
        """
        state: Dict[str, Any] = {}
        
        # 1. Инициализация БД
        logger.info("Инициализация базы данных...")
        from src.database import get_pool, init_db
        state["db_pool"] = await get_pool()
        await init_db()
        logger.info("✅ БД инициализирована")
        
        # 2. Создание репозиториев настроек
        logger.info("Создание TelegramAuthRepository...")
        from src.settings import TelegramAuthRepository
        telegram_auth_repo = TelegramAuthRepository(state["db_pool"])
        
        logger.info("Создание AppSettingsRepository...")
        from src.settings.repositories.app_settings import AppSettingsRepository
        app_settings_repo = AppSettingsRepository(state["db_pool"])
        
        logger.info("Создание LLMProvidersRepository...")
        from src.settings.repositories.llm_providers import LLMProvidersRepository
        llm_providers_repo = LLMProvidersRepository(state["db_pool"])
        
        logger.info("Создание EmbeddingProvidersRepository...")
        from src.settings.repositories.embedding_providers import EmbeddingProvidersRepository
        embedding_providers_repo = EmbeddingProvidersRepository(state["db_pool"])
        
        # 3. Инициализация настроек из .env в БД
        logger.info("Синхронизация настроек из .env в БД...")
        from src.settings_initializer import SettingsInitializer
        await SettingsInitializer.initialize(
            telegram_auth_repo=telegram_auth_repo,
            llm_providers_repo=llm_providers_repo,
            embedding_providers_repo=embedding_providers_repo,
            app_settings_repo=app_settings_repo,
        )
        
        # 4. Загрузка настроек из БД
        logger.info("Загрузка настроек из БД...")
        from src.config.loader import load_settings_from_db
        settings = await load_settings_from_db(
            telegram_auth_repo=telegram_auth_repo,
            llm_providers_repo=llm_providers_repo,
            embedding_providers_repo=embedding_providers_repo,
            app_settings_repo=app_settings_repo,
        )
        
        # 4. Проверка конфигурации
        from src.config import ConfigurationError, validate_settings, validate_telegram_auth

        await validate_settings(settings)

        # 5. Проверка Telegram авторизации
        try:
            await validate_telegram_auth(settings)
            state["telegram_configured"] = True
        except ConfigurationError as exc:
            logger.warning("Telegram not configured: %s. Application running in degraded mode.", exc.code)
            state["telegram_configured"] = False
        
        # 6. Создание клиентов
        logger.info("Инициализация Embeddings клиента...")
        from src.embeddings import EmbeddingsClient
        state["embeddings"] = EmbeddingsClient(settings)
        await state["embeddings"].initialize_provider()
        logger.info("✅ Embeddings инициализированы")
        
        logger.info("Инициализация LLM клиента...")
        from src.llm_client import LLMClient
        state["llm"] = LLMClient(settings)
        logger.info("✅ LLM инициализирован")
        
        logger.info("Инициализация RAG сервиса...")
        from src.rag import RAGService
        state["rag"] = RAGService(
            settings,
            state["db_pool"],
            state["embeddings"],
            state["llm"]
        )
        logger.info("✅ RAG инициализирован")
        
        # 7. Инициализация репозиториев переиндексации
        logger.info("Создание ReindexSettingsRepository и ReindexTaskRepository...")
        from src.reindex.repository import ReindexSettingsRepository, ReindexTaskRepository
        reindex_settings_repo = ReindexSettingsRepository(state["db_pool"])
        reindex_task_repo = ReindexTaskRepository(state["db_pool"])
        
        # 8. Инициализация сервиса переиндексации
        logger.info("Инициализация Reindex сервиса...")
        from src.reindex import ReindexService
        state["reindex"] = ReindexService(
            embeddings_client=state["embeddings"],
            reindex_settings_repo=reindex_settings_repo,
            reindex_task_repo=reindex_task_repo,
            db_pool=state["db_pool"],
        )
        from src.settings_api import set_reindex_service
        set_reindex_service(state["reindex"])
        
        # 9. Запуск фонового сервиса переиндексации
        await state["reindex"].start_background_service()
        logger.info("ReindexService фоновый сервис запущен")
        
        # 9. Добавление репозиториев в state
        state["app_settings_repo"] = app_settings_repo
        state["llm_providers_repo"] = llm_providers_repo
        state["embedding_providers_repo"] = embedding_providers_repo
        
        logger.info("Создание SummaryCleanupSettingsRepository...")
        from src.settings.repositories.summary_cleanup_settings import SummaryCleanupSettingsRepository
        summary_cleanup_repo = SummaryCleanupSettingsRepository(app_settings_repo)
        state["summary_cleanup_repo"] = summary_cleanup_repo
        
        logger.info("Создание PendingCleanupSettingsRepository...")
        from src.settings.repositories.pending_cleanup_repository import PendingCleanupSettingsRepository
        pending_cleanup_repo = PendingCleanupSettingsRepository(app_settings_repo)
        state["pending_cleanup_repo"] = pending_cleanup_repo
        
        # 10. Инициализация Rate Limiter
        logger.info("Инициализация Rate Limiter...")
        from src.rate_limiter import TelegramRateLimiter, RateLimitConfig
        from src.rate_limiter.repositories import RequestStatisticsRepository, FloodWaitIncidentRepository
        
        request_stats_repo = RequestStatisticsRepository(state["db_pool"])
        flood_wait_repo = FloodWaitIncidentRepository(state["db_pool"])

        state["request_stats_repo"] = request_stats_repo
        state["flood_wait_repo"] = flood_wait_repo

        rate_config = RateLimitConfig(
            rate_limit_per_minute=20,
            jitter_min_seconds=1.5,
            jitter_max_seconds=4.5,
            batch_size=50,
            batch_count_before_break=50,
            break_min_seconds=30.0,
            break_max_seconds=60.0,
            flood_sleep_threshold=60,
            flood_buffer_seconds=15,
            auto_slowdown_duration_minutes=30,
            auto_slowdown_factor=0.5,
        )
        state["rate_limiter"] = TelegramRateLimiter(
            rate_config,
            request_stats_repo=request_stats_repo,
            flood_wait_repo=flood_wait_repo,
        )
        
        # 11. Устанавливаем callback для логирования FloodWait в БД
        async def log_flood_wait(incident: FloodWaitIncident) -> None:
            await flood_wait_repo.save(incident)

        state["rate_limiter"].set_flood_wait_callback(log_flood_wait)
        
        # 12. Запускаем Rate Limiter
        await state["rate_limiter"].start()
        logger.info("Rate Limiter запущен")
        
        # 12. Запуск сервиса очистки summary
        logger.info("Запуск SummaryCleanupService...")
        from src.rag.summary_cleanup_service import SummaryCleanupService
        summary_cleanup_service = SummaryCleanupService(summary_cleanup_repo)
        state["summary_cleanup_service"] = summary_cleanup_service
        await summary_cleanup_service.start()
        logger.info("✅ SummaryCleanupService запущен")
        
        # 13. Инициализация MessageSaver
        logger.info("Инициализация MessageSaver...")
        from src.ingestion import MessageSaver
        state["message_saver"] = MessageSaver(settings, state["db_pool"], state["embeddings"])
        
        # 14. Инициализация ChatAccessValidator
        logger.info("Инициализация ChatAccessValidator...")
        from src.services.chat_access_validator import ChatAccessValidator
        state["chat_access_validator"] = ChatAccessValidator(state["db_pool"])
        logger.info("✅ ChatAccessValidator инициализирован")
        
        # 15. Инициализация Telegram Ingester (только если credentials настроены)
        if state["telegram_configured"]:
            logger.info("Инициализация Telegram Ingester...")
            from src.ingestion import TelegramIngester
            state["ingester"] = TelegramIngester(
                settings,
                state["embeddings"],
                telegram_auth_repo,
                app_settings_repo,
                state["rate_limiter"]
            )
            state["ingester"].start()
            logger.info("✅ Telegram Ingester инициализирован и запущен")
        else:
            logger.info("Telegram Ingester skipped — credentials not configured")
            state["ingester"] = None

        # 15. Инициализация QR AuthService
        logger.info("Инициализация QR AuthService...")
        from src.auth import QRAuthService

        auth = await telegram_auth_repo.get()
        if auth and auth.api_id and auth.api_hash:
            # Создаём QRAuthService с state=None, затем обновляем state
            qr_auth_service = QRAuthService(
                api_id=auth.api_id.value if auth.api_id else 0,
                api_hash=auth.api_hash.value if auth.api_hash else "",
                session_path="./sessions",
                on_auth_complete=None,  # Callback устанавливается в main.py
                state=None,  # Временно None
                telegram_auth_repo=telegram_auth_repo,
            )
            state["qr_auth_service"] = qr_auth_service
            state["telegram_auth_repo"] = telegram_auth_repo
            logger.info("✅ QR AuthService инициализирован")
        else:
            logger.warning("QR AuthService не инициализирован — Telegram credentials не настроены")

        return state
    
    async def cleanup(self, state: Dict[str, Any]) -> None:
        """
        Очистить все компоненты приложения.

        Args:
            state: Словарь с компонентами для очистки.
        """
        logger.info("Очистка компонентов приложения...")

        # 1. Остановка Ingester
        if "ingester" in state and state["ingester"] is not None:
            logger.info("Остановка Ingester...")
            await state["ingester"].stop()
            logger.info("✅ Ingester остановлен")

        # 2. Остановка Rate Limiter (до закрытия БД!)
        if "rate_limiter" in state and state["rate_limiter"] is not None:
            logger.info("Остановка Rate Limiter...")
            await state["rate_limiter"].stop()
            logger.info("✅ Rate Limiter остановлен")

        # 3. Остановка сервиса очистки summary
        if "summary_cleanup_service" in state and state["summary_cleanup_service"] is not None:
            logger.info("Остановка SummaryCleanupService...")
            await state["summary_cleanup_service"].stop()
            logger.info("✅ SummaryCleanupService остановлен")

        # 4. Остановка фонового сервиса переиндексации
        if "reindex" in state and state["reindex"] is not None:
            logger.info("Остановка Reindex сервиса...")
            await state["reindex"].stop_background_service()
            logger.info("✅ Reindex сервис остановлен")

        # 4. Закрытие RAG
        if "rag" in state and state["rag"] is not None:
            logger.info("Закрытие RAG сервиса...")
            await state["rag"].close()
            logger.info("✅ RAG сервис закрыт")

        # 5. Закрытие БД (после остановки всех workers)
        logger.info("Закрытие БД...")
        from src.database import close_pool
        await close_pool()
        logger.info("✅ БД закрыта")

        logger.info("Все компоненты очищены")
