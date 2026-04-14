"""
Reindex API endpoints — управление переиндексацией эмбеддингов.

Оптимизированная структура (6 endpoint вместо 14):
- GET  /check    — проверить необходимость (messages + summaries)
- GET  /stats    — статистика по моделям (messages + summaries)
- GET  /status   — статус + прогресс (messages + summaries)
- POST /start    — запуск (messages + summaries auto)
- POST /control  — управление (pause/resume/cancel)
- GET  /history  — история задач

Удалённые/объединённые endpoint:
- /settings, /put/settings — удалены (дублируют общие настройки)
- /schedule — объединён с /start (параметр async)
- /pause, /resume, /cancel — объединены в /control
- /queue — удалён (низкий приоритет)
- /progress — объединён с /status
- /auto-check — объединён с /check
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from src.api.models import ErrorDetail, ErrorResponse

from ..reindex import ReindexService, ReindexPriority

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reindex", tags=["Settings/Reindex"])

# Глобальный сервис переиндексации (инициализируется в main.py)
_reindex_service: Optional[ReindexService] = None


def get_reindex_service() -> ReindexService:
    """Получить сервис переиндексации."""
    if _reindex_service is None:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Reindex service not initialized")
            ).model_dump(),
        )
    return _reindex_service


def set_reindex_service(service: ReindexService) -> None:
    """Установить сервис переиндексации."""
    global _reindex_service
    _reindex_service = service


# ======================================================================
# Request/Response модели
# ======================================================================

class ReindexStartRequest(BaseModel):
    """Запрос на запуск переиндексации."""
    batch_size: Optional[int] = Field(default=None, ge=10, le=1000, description="Размер пакета")
    delay_between_batches: Optional[float] = Field(default=None, ge=0.0, le=10.0, description="Задержка между пакетами")
    async_mode: Optional[bool] = Field(default=False, description="Фоновый режим с очередью")
    priority: Optional[str] = Field(default="normal", description="Приоритет (low/normal/high)")
    include_summaries: Optional[bool] = Field(default=True, description="Включить переиндексацию summary")


class ReindexControlRequest(BaseModel):
    """Запрос на управление переиндексацией."""
    action: str = Field(..., description="Действие: pause/resume/cancel")


class ReindexCheckResponse(BaseModel):
    """Ответ проверки необходимости переиндексации."""
    needs_reindex: bool = Field(..., description="Требуется ли переиндексация")
    messages_to_reindex: int = Field(..., description="Количество сообщений для переиндексации (включая NULL)")
    summaries_to_reindex: int = Field(default=0, description="Количество summary для переиндексации (включая NULL)")
    current_model: str = Field(..., description="Текущая модель эмбеддингов")
    recommendation: str = Field(..., description="Рекомендация")
    messages_without_embedding: int = Field(default=0, description="Сообщений без эмбеддинга (NULL)")
    summaries_without_embedding: int = Field(default=0, description="Summary без эмбеддинга (NULL)")


class EmbeddingModelStatsItem(BaseModel):
    """Статистика по модели."""
    model_name: str = Field(..., description="Название модели")
    message_count: int = Field(..., description="Количество сообщений")
    summary_count: int = Field(default=0, description="Количество summary")
    first_message: Optional[datetime] = Field(default=None, description="Первое сообщение")
    last_message: Optional[datetime] = Field(default=None, description="Последнее сообщение")


class EmbeddingModelStatsResponse(BaseModel):
    """Ответ со статистикой по моделям."""
    models: List[EmbeddingModelStatsItem] = Field(..., description="Список моделей")
    total_messages: int = Field(..., description="Всего сообщений")
    total_summaries: int = Field(..., description="Всего summary")
    models_count: int = Field(..., description="Количество моделей")


class ReindexServiceStatusResponse(BaseModel):
    """Ответ со статусом сервиса."""
    background_running: bool = Field(..., description="Фоновый сервис запущен")
    paused: bool = Field(..., description="Приостановлен")
    is_running: bool = Field(..., description="Переиндексация активна")
    current_task: Optional[Dict[str, Any]] = Field(default=None, description="Текущая задача")
    queued_tasks: int = Field(..., description="Задач в очереди")
    stats: Dict[str, Any] = Field(..., description="Статистика")
    progress: Optional[Dict[str, Any]] = Field(default=None, description="Прогресс (messages + summaries)")


class TaskHistoryItem(BaseModel):
    """Элемент истории задач."""
    id: str = Field(..., description="ID задачи")
    status: str = Field(..., description="Статус")
    priority: int = Field(..., description="Приоритет (0=low, 1=normal, 2=high)")
    target_model: str = Field(..., description="Целевая модель")
    total_messages: int = Field(..., description="Всего сообщений")
    total_summaries: int = Field(default=0, description="Всего summary")
    processed_count: int = Field(..., description="Обработано сообщений")
    summaries_processed_count: int = Field(default=0, description="Обработано summary")
    failed_count: int = Field(..., description="Ошибок сообщений")
    summaries_failed_count: int = Field(default=0, description="Ошибок summary")
    progress_percent: float = Field(..., description="Прогресс % (messages)")
    summaries_progress_percent: float = Field(default=100.0, description="Прогресс % (summary)")
    total_progress_percent: float = Field(default=100.0, description="Общий прогресс %")
    created_at: Optional[datetime] = Field(default=None, description="Создана")
    completed_at: Optional[datetime] = Field(default=None, description="Завершена")
    error: Optional[str] = Field(default=None, description="Ошибка")
    includes_summaries: bool = Field(default=False, description="Включает summary")


class TaskHistoryResponse(BaseModel):
    """Ответ с историей задач."""
    tasks: List[TaskHistoryItem] = Field(..., description="Список задач")
    total: int = Field(..., description="Всего задач")


# ======================================================================
# GET /check — Проверка необходимости (messages + summaries)
# ======================================================================

@router.get("/check", response_model=ReindexCheckResponse)
async def check_reindex_needed():
    """
    Проверить необходимость переиндексации.

    Проверяет и messages, и summaries.
    Возвращает рекомендацию и количество для переиндексации.
    Включает сообщения/summary без эмбеддингов (NULL) и с устаревшей моделью.
    """
    from src.database import get_pool
    service = get_reindex_service()

    try:
        if not service._embeddings_client:
            return {"needs_reindex": False, "count": 0, "message": "Embeddings client not initialized"}
        current_model = service._embeddings_client.get_model_name()
        
        # Проверка messages: без эмбеддинга ИЛИ с устаревшей моделью
        pool = await get_pool()
        
        # Сообщения без эмбеддинга
        messages_without_embedding = await pool.fetchval(
            "SELECT COUNT(*) FROM messages WHERE embedding IS NULL"
        ) or 0
        
        # Сообщения с устаревшей моделью
        messages_with_old_model = await pool.fetchval(
            "SELECT COUNT(*) FROM messages WHERE embedding_model IS NOT NULL AND embedding_model != $1",
            current_model
        ) or 0
        
        # Общее количество messages для переиндексации
        count = messages_without_embedding + messages_with_old_model
        needs_reindex = count > 0

        # Проверка summary: без эмбеддинга ИЛИ с устаревшей моделью
        # Только completed summary с непустым текстом
        summaries_without_embedding = await pool.fetchval(
            """SELECT COUNT(*) FROM chat_summaries 
               WHERE status = 'completed' 
                 AND result_text IS NOT NULL 
                 AND result_text != '' 
                 AND LENGTH(TRIM(result_text)) > 0
                 AND embedding IS NULL"""
        ) or 0
        
        summaries_with_old_model = await pool.fetchval(
            """SELECT COUNT(*) FROM chat_summaries 
               WHERE status = 'completed' 
                 AND result_text IS NOT NULL 
                 AND result_text != '' 
                 AND LENGTH(TRIM(result_text)) > 0
                 AND embedding_model IS NOT NULL 
                 AND embedding_model != $1""",
            current_model
        ) or 0
        
        # Общее количество summary для переиндексации
        summaries_count = summaries_without_embedding + summaries_with_old_model
        summaries_need_reindex = summaries_count > 0
        
    except Exception:
        logger.exception("Ошибка проверки необходимости переиндексации")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Internal server error")
            ).model_dump(),
        )

    # Формирование рекомендации
    total_messages = service.stats.total_messages
    if needs_reindex:
        percentage = (count / total_messages * 100) if total_messages > 0 else 0
        if percentage > 50:
            recommendation = "Рекомендуется переиндексация: большинство сообщений используют другие модели"
        elif percentage > 10:
            recommendation = "Переиндексация желательна: значительная часть сообщений использует другие модели"
        else:
            recommendation = "Переиндексация опциональна: небольшая часть сообщений использует другие модели"
        
        # Добавление информации о NULL эмбеддингах
        if messages_without_embedding > 0:
            recommendation += f" | Включая {messages_without_embedding} сообщений без эмбеддинга"
        if summaries_without_embedding > 0:
            recommendation += f" | Включая {summaries_without_embedding} summary без эмбеддинга"
    else:
        recommendation = "Переиндексация не требуется: все сообщения используют текущую модель"

    # Добавление информации о summary
    if summaries_need_reindex and summaries_count > 0:
        recommendation += f" | Также требуется переиндексация {summaries_count} summary"

    return ReindexCheckResponse(
        needs_reindex=needs_reindex or summaries_need_reindex,
        messages_to_reindex=count,
        summaries_to_reindex=summaries_count,
        current_model=current_model,
        recommendation=recommendation,
        messages_without_embedding=messages_without_embedding,
        summaries_without_embedding=summaries_without_embedding,
    )


# ======================================================================
# GET /stats — Статистика по моделям (messages + summaries)
# ======================================================================

@router.get("/stats", response_model=EmbeddingModelStatsResponse)
async def get_embedding_model_stats():
    """
    Получить статистику по моделям эмбеддингов.
    
    Показывает распределение messages и summary по моделям.
    """
    from src.database import get_pool
    from src.rag.summary_reindex import get_summary_model_stats

    service = get_reindex_service()

    try:
        stats_dict = await service.get_embedding_model_stats_dict()
        pool = await get_pool()
        summary_stats = await get_summary_model_stats(pool)
    except Exception:
        logger.exception("Ошибка получения статистики эмбеддингов")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Internal server error")
            ).model_dump(),
        )

    # Объединение статистик
    all_models = {}
    
    # Добавляем статистику сообщений
    for name, data in stats_dict.items():
        all_models[name] = {
            "message_count": data["message_count"],
            "summary_count": 0,
            "first_message": data.get("first_message"),
            "last_message": data.get("last_message"),
        }
    
    # Добавляем статистику summary
    for name, data in summary_stats.items():
        if name not in all_models:
            all_models[name] = {
                "message_count": 0,
                "summary_count": 0,
                "first_message": None,
                "last_message": None,
            }
        all_models[name]["summary_count"] = data.get("summary_count", 0)
        # Обновляем даты если есть
        if data.get("first_summary"):
            first_summary_str = str(data["first_summary"]) if data["first_summary"] else None
            current_first = str(all_models[name]["first_message"]) if all_models[name]["first_message"] else None
            if not current_first or (first_summary_str and first_summary_str < current_first):
                all_models[name]["first_message"] = data["first_summary"]
        if data.get("last_summary"):
            last_summary_str = str(data["last_summary"]) if data["last_summary"] else None
            current_last = str(all_models[name]["last_message"]) if all_models[name]["last_message"] else None
            if not current_last or (last_summary_str and last_summary_str > current_last):
                all_models[name]["last_message"] = data["last_summary"]

    models = [
        EmbeddingModelStatsItem(
            model_name=name,
            message_count=data["message_count"],
            summary_count=data["summary_count"],
            first_message=data["first_message"],
            last_message=data["last_message"],
        )
        for name, data in all_models.items()
    ]

    total_messages = sum(m.message_count for m in models)
    total_summaries = sum(m.summary_count for m in models)

    return EmbeddingModelStatsResponse(
        models=models,
        total_messages=total_messages,
        total_summaries=total_summaries,
        models_count=len(models),
    )


# ======================================================================
# GET /status — Статус + прогресс (messages + summaries)
# ======================================================================

@router.get("/status", response_model=ReindexServiceStatusResponse)
async def get_reindex_status():
    """
    Получить статус сервиса переиндексации.
    
    Возвращает информацию о фоновом сервисе, текущей задаче, очереди и прогрессе.
    Включает прогресс как для messages, так и для summaries.
    """
    service = get_reindex_service()
    status = service.get_status()
    
    # Получаем прогресс (включая summary)
    progress = service.get_progress()

    return ReindexServiceStatusResponse(
        background_running=status["running"],
        paused=status["paused"],
        is_running=status["is_running"],
        current_task=status["current_task"],
        queued_tasks=status["queued_tasks"],
        stats=status["stats"],
        progress=progress,
    )


# ======================================================================
# POST /start — Запуск переиндексации (messages + summaries auto)
# ======================================================================

@router.post("/start")
async def start_reindex(
    request: ReindexStartRequest,
    background_tasks: BackgroundTasks
):
    """
    Запустить переиндексацию.

    Параметры:
    - batch_size: размер пакета (по умолчанию из настроек)
    - delay_between_batches: задержка между пакетами
    - async_mode: фоновый режим с очередью (False = немедленный запуск)
    - priority: приоритет (low/normal/high) — используется только с async_mode
    - include_summaries: включить переиндексацию summary (по умолчанию True)

    Переиндексация включает:
    1. Messages (сообщения) — обрабатываются первыми
    2. Summaries (summary) — автоматически после messages (если include_summaries=True)
    
    Оба типа данных обрабатываются с одинаковыми правилами пакетной обработки:
    - Batch processing с указанным batch_size
    - Delay между пакетами
    - Retry logic при ошибках
    - Progress tracking для каждого типа
    """
    service = get_reindex_service()

    if service.is_running:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-102", message="Переиндексация уже запущена")
            ).model_dump(),
        )

    # Получаем настройки
    settings = service.settings
    batch_size = request.batch_size or settings.batch_size
    delay = request.delay_between_batches or settings.delay_between_batches

    if request.async_mode:
        # Фоновый режим с очередью
        priority_map = {
            "low": ReindexPriority.LOW,
            "normal": ReindexPriority.NORMAL,
            "high": ReindexPriority.HIGH,
        }
        priority = priority_map.get((request.priority or "normal").lower(), ReindexPriority.NORMAL)
        
        task_id = service.schedule_reindex(
            priority=priority,
            batch_size=batch_size,
            delay=delay
        )
        
        return {
            "status": "scheduled",
            "task_id": task_id,
            "message": f"Переиндексация запланирована (ID: {task_id}, приоритет: {priority.name})"
        }
    else:
        # Немедленный запуск
        async def run_reindex():
            try:
                await service.reindex_all(
                    batch_size=batch_size,
                    delay_between_batches=delay
                )
            except Exception as e:
                logger.error(f"Ошибка переиндексации: {e}", exc_info=True)

        background_tasks.add_task(run_reindex)

        return {
            "status": "started",
            "message": f"Переиндексация запущена (batch_size={batch_size}, delay={delay})"
        }


# ======================================================================
# POST /control — Управление (pause/resume/cancel)
# ======================================================================

@router.post("/control")
async def control_reindex(request: ReindexControlRequest):
    """
    Управление переиндексацией.

    Действия:
    - pause: приостановить переиндексацию (messages + summary)
    - resume: возобновить переиндексацию (messages + summary)
    - cancel: отменить текущую переиндексацию (messages + summary)

    Управление применяется ко всей переиндексации:
    - Messages (сообщения)
    - Summaries (summary) — обрабатываются после messages
    """
    service = get_reindex_service()
    
    action = request.action.lower()
    
    if action == "pause":
        if not service.is_background_running:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error=ErrorDetail(code="APP-102", message="Фоновый сервис не запущен")
                ).model_dump(),
            )
        
        await service.pause()
        return {
            "status": "paused",
            "message": "Переиндексация приостановлена"
        }
    
    elif action == "resume":
        if not service.is_background_running:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error=ErrorDetail(code="APP-102", message="Фоновый сервис не запущен")
                ).model_dump(),
            )
        
        await service.resume()
        return {
            "status": "resumed",
            "message": "Переиндексация возобновлена"
        }
    
    elif action == "cancel":
        if not service.current_task:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error=ErrorDetail(code="APP-102", message="Нет активной задачи")
                ).model_dump(),
            )
        
        success = await service.cancel_current_task()
        
        if success:
            return {
                "status": "cancelled",
                "message": "Текущая задача отменена"
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error=ErrorDetail(code="APP-102", message="Не удалось отменить задачу")
                ).model_dump(),
            )
    
    else:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-102", message="Неизвестное действие")
            ).model_dump(),
        )


# ======================================================================
# GET /history — История задач
# ======================================================================

@router.get("/history", response_model=TaskHistoryResponse)
async def get_task_history(limit: int = 10):
    """
    Получить историю задач переиндексации.

    Возвращает последние выполненные задачи с информацией о том,
    включали ли они переиндексацию summary.
    """
    service = get_reindex_service()

    try:
        history = await service.get_task_history(limit=limit)

        tasks = [
            TaskHistoryItem(
                id=t["id"],
                status=t["status"],
                priority=t["priority"],
                target_model=t["target_model"],
                total_messages=t["total_messages"],
                total_summaries=t.get("total_summaries", 0),
                processed_count=t["processed_count"],
                summaries_processed_count=t.get("summaries_processed_count", 0),
                failed_count=t["failed_count"],
                summaries_failed_count=t.get("summaries_failed_count", 0),
                progress_percent=t["progress_percent"],
                summaries_progress_percent=t.get("summaries_progress_percent", 100.0),
                total_progress_percent=t.get("total_progress_percent", 100.0),
                created_at=t.get("created_at"),
                completed_at=t.get("completed_at"),
                error=t.get("error"),
                includes_summaries=t.get("includes_summaries", False),
            )
            for t in history
        ]

        return TaskHistoryResponse(
            tasks=tasks,
            total=len(tasks)
        )

    except Exception:
        logger.exception("Ошибка получения истории переиндексации")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(code="APP-101", message="Internal server error")
            ).model_dump(),
        )


__all__ = ["router", "set_reindex_service", "get_reindex_service"]
