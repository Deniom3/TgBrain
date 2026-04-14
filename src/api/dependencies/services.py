"""
Dependency functions для внедрения сервисов через FastAPI Depends().

Назначение:
- Централизованное создание сервисов с зависимостями
- Упрощение тестирования через подмену зависимостей
- Следование принципу Dependency Injection
"""

import logging

import asyncpg
from fastapi import Depends, HTTPException, status

from src.api.models import ErrorDetail, ErrorResponse

from ...app import get_app_state
from ...settings.repositories.chat_settings import ChatSettingsRepository
from ...settings.repositories.chat_summary.repository import ChatSummaryRepository
from ...webhook.webhook_service import WebhookService
from ...application.services.webhook_settings_service import WebhookSettingsService
from ...application.usecases.generate_summary import GenerateSummaryUseCase
from ...application.usecases.import_messages import ImportMessagesUseCase
from ...protocols.isummary_task_service import ISummaryTaskService
from ...protocols.isummary_webhook_service import ISummaryWebhookService
from ..protocols import SummaryRepoProtocol

logger = logging.getLogger(__name__)


def get_summary_usecase() -> GenerateSummaryUseCase:
    """
    Получить GenerateSummaryUseCase для генерации summary.

    UseCase создаётся в lifespan (app.py) и берётся из app.state.

    Returns:
        GenerateSummaryUseCase instance.

    Raises:
        HTTPException: Если UseCase не инициализирован.
    """
    state = get_app_state()
    if not state or not getattr(state, "summary_usecase", None):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-106", message="GenerateSummaryUseCase не инициализирован")
            ).model_dump(),
        )

    return state.summary_usecase


def get_import_usecase() -> ImportMessagesUseCase:
    """
    Получить ImportMessagesUseCase для импорта сообщений.

    UseCase создаётся в lifespan (app.py) и берётся из app.state.

    Returns:
        ImportMessagesUseCase instance.

    Raises:
        HTTPException: Если UseCase не инициализирован.
    """
    state = get_app_state()
    if not state or not getattr(state, "import_usecase", None):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-106", message="ImportMessagesUseCase не инициализирован")
            ).model_dump(),
        )

    return state.import_usecase


def get_db_pool() -> asyncpg.Pool:
    """
    Получить пул соединений к БД.
    
    Returns:
        asyncpg.Pool или None если не инициализирован.
        
    Raises:
        HTTPException: Если пул не инициализирован.
    """
    state = get_app_state()
    if not state or not state.db_pool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-106", message="Database pool not initialized")
            ).model_dump(),
        )
    return state.db_pool


# ==================== Chat Summary DI ====================
# Используются в: chat_summary_generate.py, chat_summary_retrieval.py


def get_chat_settings_repo(db_pool: asyncpg.Pool = Depends(get_db_pool)) -> ChatSettingsRepository:
    """
    Создать репозиторий настроек чата.
    
    Args:
        db_pool: Пул соединений к БД.
        
    Returns:
        ChatSettingsRepository instance.
    """
    state = get_app_state()
    if state and getattr(state, "chat_settings_repo", None):
        return state.chat_settings_repo
    return ChatSettingsRepository(db_pool)


def get_webhook_service() -> WebhookService:
    """
    Создать сервис отправки webhook.
    
    Returns:
        WebhookService instance.
    """
    return WebhookService()


# ==================== Repository DI ====================


def get_summary_repo(db_pool: asyncpg.Pool = Depends(get_db_pool)) -> SummaryRepoProtocol:
    """
    Получить репозиторий summary чата.
    
    Кэширует экземпляр в app state для повторного использования.
    
    Args:
        db_pool: Пул соединений к БД.
    
    Returns:
        ChatSummaryRepository instance.
    """
    state = get_app_state()
    if state and getattr(state, "summary_repo", None):
        return state.summary_repo
    repo = ChatSummaryRepository(db_pool)
    if state:
        state.summary_repo = repo  # type: ignore[misc]
    return repo


def get_summary_task_service() -> ISummaryTaskService:
    """
    Получить SummaryTaskService для управления задачами summary.
    
    Сервис создаётся в lifespan (app.py) и берётся из app.state.
    db_pool не требуется — зависимость убрана из сигнатуры.
    
    Returns:
        ISummaryTaskService instance.
    """
    state = get_app_state()
    if not state or not getattr(state, "summary_task_service", None):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-106", message="SummaryTaskService не инициализирован")
            ).model_dump(),
        )

    return state.summary_task_service  # type: ignore[return-value]


def get_summary_webhook_service(
    db_pool: asyncpg.Pool = Depends(get_db_pool),
    webhook_service: WebhookService = Depends(get_webhook_service),
    chat_settings_repo: ChatSettingsRepository = Depends(get_chat_settings_repo),
    summary_task_service: ISummaryTaskService = Depends(get_summary_task_service),
) -> ISummaryWebhookService:
    """
    Получить SummaryWebhookService для отправки summary на webhook.
    
    Использует цепочку Depends() для внедрения зависимостей.
    
    Args:
        db_pool: Пул соединений к БД.
        webhook_service: Сервис отправки webhook.
        chat_settings_repo: Репозиторий настроек чата.
        summary_task_service: Сервис управления задачами summary.
        
    Returns:
        SummaryWebhookService instance.
    """
    state = get_app_state()
    if not state or not getattr(state, "summary_webhook_service", None):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-106", message="SummaryWebhookService не инициализирован")
            ).model_dump(),
        )

    return state.summary_webhook_service


def get_webhook_settings_service(
    chat_settings_repo: ChatSettingsRepository = Depends(get_chat_settings_repo),
    webhook_service: WebhookService = Depends(get_webhook_service),
) -> WebhookSettingsService:
    """
    Создать WebhookSettingsService для управления настройками webhook.
    
    Использует цепочку Depends() для внедрения зависимостей.
    
    Args:
        chat_settings_repo: Репозиторий настроек чата.
        webhook_service: Сервис отправки webhook.
        
    Returns:
        WebhookSettingsService instance.
    """
    return WebhookSettingsService(
        chat_settings_repo=chat_settings_repo,
        webhook_service=webhook_service,
    )


__all__ = [
    "get_db_pool",
    "get_chat_settings_repo",
    "get_webhook_service",
    "get_summary_repo",
    "get_summary_task_service",
    "get_summary_usecase",
    "get_import_usecase",
    "get_summary_webhook_service",
    "get_webhook_settings_service",
]
