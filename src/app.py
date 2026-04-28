"""
FastAPI приложение — создание и инициализация.

Функции:
- create_lifespan: Создание lifespan контекста
- init_app_state: Инициализация app.state
"""

import logging
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import (
    AsyncGenerator,
    Callable,
)

from fastapi import FastAPI

from src.common.application_state import AppStateStore
from src.config.loader import load_settings_from_db
from src.protocols.i_application_state import IApplicationState
from src.rag.summary_task_service import SummaryTaskService
from src.schedule import ScheduleService
from src.services import ApplicationLifecycleService
from src.webhook import WebhookService

logger = logging.getLogger("tgbrain")


def create_lifespan() -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    """
    Создать lifespan контекст для FastAPI приложения.

    Returns:
        Lifespan контекст для инициализации и очистки.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Инициализация при старте и очистка при остановке."""

        logger.info("Инициализация TgBrain API...")

        # Загрузка настроек из БД для сервиса
        settings = await load_settings_from_db()
        
        # Инициализация через сервис
        lifecycle_service = ApplicationLifecycleService(settings)
        state = await lifecycle_service.initialize()
        
        # Копируем состояние в app.state
        for key, value in state.items():
            setattr(app.state, key, value)

        # Чтение timezone из БД (с ENV fallback)
        app_settings_repo = state["app_settings_repo"]
        db_timezone = await app_settings_repo.get_value(key="app.timezone", default=None)
        
        if db_timezone:
            timezone_value = db_timezone
            logger.info("Timezone из БД: %s", timezone_value)
        else:
            timezone_value = settings.timezone
            logger.info("Timezone из ENV (fallback): %s", timezone_value)
        app.state.timezone = timezone_value

        # Создание WebhookService
        webhook_service = WebhookService()
        app.state.webhook_service = webhook_service
        logger.info("WebhookService создан")

        # Создание ChatSettingsRepository перед SummaryTaskService
        from src.settings.repositories.chat_settings import ChatSettingsRepository
        chat_settings_repo = ChatSettingsRepository(state["db_pool"])

        # Создание ChatSummaryRepository для webhook delivery
        from src.settings.repositories.chat_summary.repository import ChatSummaryRepository
        summary_repo = ChatSummaryRepository(state["db_pool"])

        # Создание SummaryWebhookService с полной DI
        from src.infrastructure.services.summary_webhook_service import (
            SummaryWebhookService,
        )
        summary_webhook_service = SummaryWebhookService(
            config=settings,
            rag_search=state["rag"],
            llm_client=state["llm"],
            embeddings_client=state["embeddings"],
            db_pool=state["db_pool"],
            webhook_service=webhook_service,
            chat_settings_repo=chat_settings_repo,
            summary_usecase=None,  # будет установлено после создания GenerateSummaryUseCase
            summary_repo=summary_repo,
        )

        # Создание адаптеров для делегирования
        from src.infrastructure.services.summary_embedding_generator import (
            SummaryEmbeddingGenerator,
        )
        from src.infrastructure.services.summary_webhook_dispatcher import (
            SummaryWebhookDispatcher,
        )
        from src.rag.summary_embeddings_service import SummaryEmbeddingsService

        embedding_generator = SummaryEmbeddingGenerator(
            embeddings_service=SummaryEmbeddingsService(state["embeddings"], state["db_pool"]),
            logger=logging.getLogger(__name__ + ".embedding_generator"),
        )

        webhook_dispatcher = SummaryWebhookDispatcher(
            webhook_service=summary_webhook_service,
            chat_settings_repo=chat_settings_repo,
            logger=logging.getLogger(__name__ + ".webhook_dispatcher"),
        )

        # Создание SummaryTaskService с адаптерами для делегирования
        summary_task_service = SummaryTaskService(
            config=settings,
            search=state["rag"],
            llm_client=state["llm"],
            embeddings_client=state["embeddings"],
            db_pool=state["db_pool"],
            embedding_generator=embedding_generator,
            webhook_dispatcher=webhook_dispatcher,
        )
        app.state.summary_task_service = summary_task_service
        logger.info("SummaryTaskService создан")

        app.state.summary_webhook_service = summary_webhook_service
        logger.info("SummaryWebhookService создан (ожидает SummaryUseCase)")

        # ==================== Wiring UseCase-классов ====================

        # AskQuestionUseCase — адаптеры портов
        from src.application.usecases.adapters import (
            ChatSummarySearchServiceAsSummarySearchPort,
            EmbeddingsClientAsEmbeddingGeneratorPort,
            LLMClientAsLLMGenerationPort,
            RAGSearchAsVectorSearchPort,
        )
        from src.application.usecases.ask_question import AskQuestionUseCase

        ask_question_usecase = AskQuestionUseCase(
            embedding_generator=EmbeddingsClientAsEmbeddingGeneratorPort(state["embeddings"]),
            vector_search=RAGSearchAsVectorSearchPort(state["rag"].search),
            summary_search=ChatSummarySearchServiceAsSummarySearchPort(state["rag"].summary_search),
            llm_generator=LLMClientAsLLMGenerationPort(state["llm"]),
            chat_checker=state["rag"],
        )
        app.state.ask_usecase = ask_question_usecase
        logger.info("AskQuestionUseCase создан")

        # GenerateSummaryUseCase — адаптеры портов
        from src.application.usecases.adapters import (
            ChatSettingsRepoAsChatSettingsPort,
            ChatSummaryRepositoryAsSummaryRepositoryPort,
            DbPoolAsConnectionProviderPort,
            RAGSearchAsMessageFetcherPort,
            RAGSummaryAsSummaryGenerationPort,
        )
        from src.application.usecases.generate_summary import GenerateSummaryUseCase

        generate_summary_usecase = GenerateSummaryUseCase(
            summary_repo=ChatSummaryRepositoryAsSummaryRepositoryPort(summary_repo),
            message_fetcher=RAGSearchAsMessageFetcherPort(state["rag"].search),
            summary_generator=RAGSummaryAsSummaryGenerationPort(summary_task_service.rag_summary),
            embedding_dispatcher=embedding_generator,
            webhook_dispatcher=webhook_dispatcher,
            chat_settings=ChatSettingsRepoAsChatSettingsPort(chat_settings_repo),
            db_pool=DbPoolAsConnectionProviderPort(state["db_pool"]),
        )
        app.state.summary_usecase = generate_summary_usecase
        logger.info("GenerateSummaryUseCase создан")

        # Разрешение зависимостей: устанавливаем UseCase в SummaryWebhookService
        summary_webhook_service.summary_usecase = generate_summary_usecase

        # Создание и запуск ScheduleService (после GenerateSummaryUseCase)
        schedule_service = ScheduleService(
            chat_settings_repo=chat_settings_repo,
            summary_usecase=generate_summary_usecase,
            webhook_service=summary_webhook_service,
        )
        app.state.schedule_service = schedule_service
        await schedule_service.start()
        logger.info("ScheduleService запущен")

        # ImportMessagesUseCase — адаптеры портов
        from src.application.usecases.adapters import (
            BatchImportFileServiceAsFileValidationPort,
            ChatAccessValidatorAsChatAccessValidationPort,
            ExternalMessageSaverAsMessageIngestionPort,
            StreamingChunkGeneratorAsChunkGeneratorPort,
            TempFileStorage,
        )
        from src.application.usecases.import_messages import ImportMessagesUseCase
        from src.batch_import.file_service import BatchImportFileService
        from src.importers.chunk_generator import StreamingChunkGenerator
        from src.ingestion.external_saver import ExternalMessageSaver

        external_saver = ExternalMessageSaver(state["db_pool"], state["message_saver"])
        import_usecase = ImportMessagesUseCase(
            file_storage=TempFileStorage(),
            file_validation=BatchImportFileServiceAsFileValidationPort(BatchImportFileService()),
            chat_access=ChatAccessValidatorAsChatAccessValidationPort(state["chat_access_validator"]),
            message_ingestion=ExternalMessageSaverAsMessageIngestionPort(external_saver),
            chunk_generator=StreamingChunkGeneratorAsChunkGeneratorPort(StreamingChunkGenerator),
        )
        app.state.import_usecase = import_usecase
        logger.info("ImportMessagesUseCase создан")

        # Устанавливаем state в QRAuthService если он есть
        if hasattr(app.state, 'qr_auth_service') and app.state.qr_auth_service is not None:
            app.state.qr_auth_service.set_state(app.state)
            logger.info("QRAuthService.state обновлён")
        
        # Проверяем авторизацию сессии перед запуском
        from src.services import IngesterRestartService

        telegram_auth_repo = app.state.telegram_auth_repo
        auth = await telegram_auth_repo.get()

        session_authorized = False
        if auth and auth.session_name:
            # session_data хранится только в infrastructure модели,
            # проверяем наличие через репозиторий
            has_session_data = await telegram_auth_repo.has_session_data()

            if has_session_data:
                # Сессия найдена в БД (session_name + session_data)
                # TelegramIngester сам загрузит session_data из БД и создаст временный файл
                session_name_masked = (
                    f"{auth.session_name.value[:4]}..."
                    if len(auth.session_name.value) > 4
                    else "***"
                )
                logger.info("Найдена активная сессия в БД: %s", session_name_masked)
                logger.info("Запуск Ingester с активной сессией...")

                try:
                    # Запускаем Ingester через сервис — он загрузит session_data из БД
                    success = await IngesterRestartService.start_ingester(app.state)
                    session_authorized = success
                    # Broad exception acceptable for lifespan startup — we want to ensure
                    # startup continues even if Ingester fails, fallback to QR auth
                except Exception as e:
                    logger.error("Ошибка запуска Ingester: %s", e)
                    session_authorized = False
            else:
                session_name_masked = (
                    f"{auth.session_name.value[:4]}..."
                    if len(auth.session_name.value) > 4
                    else "***"
                )
                logger.warning("Сессия найдена в БД, но session_data отсутствует: %s", session_name_masked)
                logger.warning("Возможно, авторизация не была завершена")
        else:
            logger.warning("Настройки Telegram не найдены в БД")

        if not session_authorized:
            logger.info("Ingester не запущен - ожидается QR авторизация")

        # Запуск фоновой задачи очистки pending сообщений
        # Вызывается внутри ingester.start() после инициализации _pending_cleanup
        logger.info("API готово к работе")

        # Сохраняем app в AppStateStore для безопасного доступа
        await AppStateStore.set(app)

        yield

        # Очистка при остановке
        logger.info("Остановка API...")

        # Остановка ScheduleService
        if hasattr(app.state, 'schedule_service') and app.state.schedule_service is not None:
            await app.state.schedule_service.stop()
            logger.info("ScheduleService остановлен")

        # Закрытие WebhookService
        if hasattr(app.state, 'webhook_service') and app.state.webhook_service is not None:
            await app.state.webhook_service.close()
            logger.info("WebhookService закрыт")

        # Используем сервис для очистки (он остановит Ingester который сам остановит cleanup_task)
        await lifecycle_service.cleanup(state)

    return lifespan


def init_app_state(app: FastAPI) -> None:
    """
    Инициализировать app.state значениями по умолчанию.

    Args:
        app: FastAPI приложение.
    """
    app.state.db_pool = None
    app.state.embeddings = None
    app.state.llm = None
    app.state.rag = None
    app.state.reindex = None
    app.state.rate_limiter = None
    app.state.message_saver = None
    app.state.ingester = None
    app.state.ingestion_task = None
    app.state.cleanup_task = None
    app.state.ask_usecase = None
    app.state.summary_usecase = None
    app.state.import_usecase = None
    app.state.telegram_client_factory = None


def get_app_state() -> IApplicationState | None:
    """
    Получить доступ к app.state из любого места.

    Returns:
        app.state объект или None если не инициализирован.
    """
    if AppStateStore.is_initialized():
        return AppStateStore.get_app().state
    return None


__all__ = ["create_lifespan", "init_app_state", "get_app_state"]
