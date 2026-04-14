"""UseCase для оркестрации генерации summary.

Переносит оркестрационную логику из SummaryTaskService.get_or_create_task()
и эндпоинта chat_summary_generate._compute_period().
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from src.application.exceptions import (
    DatabaseError,
)
from src.application.usecases.protocols import (
    ChatSettingsPort,
    ConnectionProviderPort,
    EmbeddingDispatcherPort,
    MessageFetcherPort,
    SummaryGenerationPort,
    SummaryRepositoryPort,
    WebhookDispatcherPort,
)
from src.application.usecases.result import Failure, Result, Success
from src.rag.summary_cache_helpers import calculate_cache_ttl, generate_params_hash

logger = logging.getLogger(__name__)

MAX_CONCURRENT_TASKS: int = 10
MIN_PERIOD_HOURS: int = 1
MAX_PERIOD_HOURS: int = 2160
TASK_TIMEOUT_SECONDS: int = 300
BULK_TASK_DELAY_SECONDS: int = 4
DEFAULT_PERIOD_MINUTES: int = 1440
MAX_MESSAGES_CLAMP: int = 2160 * 60
OLD_TASK_CLEANUP_HOURS: int = 24


@dataclass(frozen=True, slots=True)
class SummaryRequest:
    """Входные данные для GenerateSummaryUseCase."""

    chat_id: int
    period_start: datetime | None
    period_end: datetime | None
    period_minutes: int | None
    custom_prompt: str | None = None
    max_messages: int = 100


@dataclass(frozen=True, slots=True)
class SummaryTaskResult:
    """Результат выполнения GenerateSummaryUseCase."""

    task_id: int
    status: str
    from_cache: bool
    is_new: bool
    chat_id: int


class GenerateSummaryUseCase:
    """Оркестрация генерации summary: кэш → создание задачи → фоновая обработка."""

    def __init__(
        self,
        summary_repo: SummaryRepositoryPort,
        message_fetcher: MessageFetcherPort,
        summary_generator: SummaryGenerationPort,
        embedding_dispatcher: EmbeddingDispatcherPort,
        webhook_dispatcher: WebhookDispatcherPort,
        chat_settings: ChatSettingsPort,
        db_pool: ConnectionProviderPort,
        task_timeout_seconds: int = TASK_TIMEOUT_SECONDS,
    ) -> None:
        self._summary_repo = summary_repo
        self._message_fetcher = message_fetcher
        self._summary_generator = summary_generator
        self._embedding_dispatcher = embedding_dispatcher
        self._webhook_dispatcher = webhook_dispatcher
        self._chat_settings = chat_settings
        self._db_pool = db_pool
        self._active_tasks: dict[int, asyncio.Task[None]] = {}
        self._task_timeout_seconds = task_timeout_seconds
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

    async def get_or_create_task(
        self,
        request: SummaryRequest,
        creation_delay_seconds: int = 0,
    ) -> Result[SummaryTaskResult, Exception]:
        """Получить или создать задачу генерации summary."""
        safe_chat_id = request.chat_id
        logger.info(
            "GenerateSummaryUseCase: chat_id=%d, period_start=%s, period_end=%s",
            safe_chat_id,
            request.period_start,
            request.period_end,
        )

        chat_cfg = await self._chat_settings.get_summary_settings(request.chat_id)
        fallback_minutes = DEFAULT_PERIOD_MINUTES
        if chat_cfg and chat_cfg.period_minutes is not None:
            fallback_minutes = chat_cfg.period_minutes

        period_start, period_end = self._compute_period(
            request.period_start,
            request.period_end,
            request.period_minutes,
            fallback_minutes,
        )

        model_name = self._summary_generator.model
        prompt_version = "custom" if request.custom_prompt else "default"
        params_hash = generate_params_hash(
            request.chat_id,
            period_start,
            period_end,
            prompt_version=prompt_version,
            model_name=model_name,
        )

        cache_ttl = calculate_cache_ttl(period_start, period_end)

        # Граница application слоя: очистка старых failed-задач
        try:
            async with self._db_pool.acquire() as conn:
                await self._summary_repo.cleanup_old_failed_tasks(
                    conn, request.chat_id, older_than_hours=OLD_TASK_CLEANUP_HOURS,
                )
        except Exception as exc:
            # Boundary: convert infrastructure error to domain error
            logger.warning("Ошибка очистки старых задач для чата %d: %s", request.chat_id, type(exc).__name__)

        # Граница application слоя: проверка кэша
        try:
            async with self._db_pool.acquire() as conn:
                cached = await self._summary_repo.get_cached_summary_by_hash(
                    conn, params_hash, cache_ttl,
                )
        except Exception as exc:
            # Boundary: convert infrastructure error to domain error
            logger.error("Ошибка проверки кэша: %s", type(exc).__name__)
            return Failure(DatabaseError("Database operation failed"))

        if cached:
            cached_id = cached.get("id", 0) if isinstance(cached, dict) else getattr(cached, "id", 0)
            cached_status = cached.get("status", "completed") if isinstance(cached, dict) else "completed"
            return Success(SummaryTaskResult(
                task_id=int(cached_id),
                status=cached_status,
                from_cache=True,
                is_new=False,
                chat_id=request.chat_id,
            ))

        # Граница application слоя: проверка pending
        try:
            async with self._db_pool.acquire() as conn:
                pending = await self._summary_repo.get_pending_task_by_hash(
                    conn, params_hash,
                )
        except Exception as exc:
            # Boundary: convert infrastructure error to domain error
            logger.error("Ошибка проверки pending задачи: %s", type(exc).__name__)
            return Failure(DatabaseError("Database operation failed"))

        if pending:
            pending_id = pending.get("id", 0) if isinstance(pending, dict) else getattr(pending, "id", 0)
            pending_status = pending.get("status", "pending") if isinstance(pending, dict) else "pending"
            return Success(SummaryTaskResult(
                task_id=int(pending_id),
                status=pending_status,
                from_cache=False,
                is_new=False,
                chat_id=request.chat_id,
            ))

        # Граница application слоя: создание новой задачи
        try:
            async with self._db_pool.acquire() as conn:
                metadata: dict[str, Any] = {
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    "custom_prompt": request.custom_prompt is not None,
                    "max_messages": request.max_messages,
                    "model_name": model_name,
                }

                task_data = await self._summary_repo.create_summary_task(
                    conn,
                    request.chat_id,
                    period_start.isoformat(),
                    period_end.isoformat(),
                    params_hash,
                    metadata,
                )

            if not task_data:
                return Failure(DatabaseError("Не удалось создать задачу в БД"))

            task_id = task_data[0]
            task_status = task_data[2] if len(task_data) > 2 else "pending"

            background_task = asyncio.create_task(
                self._run_task_with_semaphore(
                    task_id,
                    request.chat_id,
                    period_start,
                    period_end,
                    request.custom_prompt,
                    request.max_messages,
                    params_hash,
                    creation_delay_seconds,
                ),
            )
            self._active_tasks[task_id] = background_task
            background_task.add_done_callback(self._on_task_done)

            return Success(SummaryTaskResult(
                task_id=task_id,
                status=task_status,
                from_cache=False,
                is_new=True,
                chat_id=request.chat_id,
            ))

        # Граница application слоя: ошибка БД при создании задачи
        except Exception as exc:
            # Boundary: convert infrastructure error to domain error
            logger.error("Ошибка создания задачи summary: %s", type(exc).__name__)
            return Failure(DatabaseError("Database operation failed"))

    def _on_task_done(self, task: asyncio.Task[None]) -> None:
        """Callback для удаления завершённой задачи из трекинга."""
        for task_id, tracked_task in list(self._active_tasks.items()):
            if tracked_task is task:
                self._active_tasks.pop(task_id, None)
                break

    async def _run_task_with_semaphore(
        self,
        task_id: int,
        chat_id: int,
        period_start: datetime,
        period_end: datetime,
        custom_prompt: str | None,
        max_messages: int,
        params_hash: str,
        creation_delay_seconds: int,
    ) -> None:
        """Запуск фоновой задачи с ограничением через semaphore."""
        async with self._semaphore:
            await self._process_summary(
                task_id,
                chat_id,
                period_start,
                period_end,
                custom_prompt,
                max_messages,
                params_hash,
                creation_delay_seconds,
            )

    def _compute_period(
        self,
        period_start: datetime | None,
        period_end: datetime | None,
        period_minutes: int | None,
        fallback_minutes: int,
    ) -> tuple[datetime, datetime]:
        """Вычисляет период сбора сообщений."""
        end = period_end or datetime.now(timezone.utc)

        if period_start is not None and period_end is not None:
            return period_start, period_end

        if period_minutes is not None:
            return end - timedelta(minutes=period_minutes), end

        return end - timedelta(minutes=fallback_minutes), end

    async def _process_summary(
        self,
        task_id: int,
        chat_id: int,
        period_start: datetime,
        period_end: datetime,
        custom_prompt: str | None,
        max_messages: int,
        params_hash: str,
        creation_delay_seconds: int,
    ) -> None:
        """Фоновая обработка задачи генерации summary."""
        if creation_delay_seconds > 0:
            await asyncio.sleep(creation_delay_seconds)

        start_time = time.time()
        clamped_max = max(1, min(max_messages, MAX_MESSAGES_CLAMP))
        period_hours = max(
            MIN_PERIOD_HOURS,
            min(int((period_end - period_start).total_seconds() / 3600), MAX_PERIOD_HOURS),
        )

        try:
            async with self._db_pool.acquire() as conn:
                await self._summary_repo.update_status(
                    conn, task_id, "processing", None, None,
                )

            messages = await self._message_fetcher.get_messages_by_period(
                chat_id=chat_id,
                period_hours=period_hours,
                max_messages=clamped_max,
            )

            if not messages:
                logger.warning(
                    "Задача %d: нет сообщений за период %dч",
                    task_id,
                    period_hours,
                )
                execution_time = time.time() - start_time
                metadata: dict[str, Any] = {
                    "execution_time_sec": round(execution_time, 2),
                    "messages_processed": 0,
                    "model_name": self._summary_generator.model,
                    "params_hash": params_hash,
                    "no_data": True,
                }
                async with self._db_pool.acquire() as conn:
                    await self._summary_repo.update_status(
                        conn, task_id, "completed",
                        "Нет сообщений за указанный период",
                        metadata,
                        0,
                    )
                return

            async with asyncio.timeout(self._task_timeout_seconds):
                digest = await self._summary_generator.summary(
                    period_hours=period_hours,
                    max_messages=clamped_max,
                    chat_id=chat_id,
                    custom_prompt=custom_prompt,
                    use_cache=False,
                    save_to_db=False,
                )

            execution_time = time.time() - start_time
            metadata = {
                "execution_time_sec": round(execution_time, 2),
                "messages_processed": len(messages),
                "model_name": self._summary_generator.model,
                "params_hash": params_hash,
            }

            async with self._db_pool.acquire() as conn:
                await self._summary_repo.update_status(
                    conn, task_id, "completed", digest, metadata, len(messages),
                )

            await self._embedding_dispatcher.dispatch_embedding(
                task_id,
                digest,
                self._summary_generator.model,
            )

            await self._webhook_dispatcher.dispatch_webhook_on_completion(
                task_id, chat_id,
            )

            logger.info("Задача %d: завершена успешно за %.2fс", task_id, execution_time)

        except asyncio.TimeoutError:
            # Boundary: convert infrastructure timeout to domain tracking
            execution_time = time.time() - start_time
            metadata = {
                "execution_time_sec": round(execution_time, 2),
                "error_type": "TimeoutError",
                "params_hash": params_hash,
            }
            async with self._db_pool.acquire() as conn:
                await self._summary_repo.update_status(
                    conn, task_id, "failed",
                    f"Timeout after {TASK_TIMEOUT_SECONDS}s",
                    metadata,
                )
            logger.error("Задача %d превысила timeout %d сек", task_id, TASK_TIMEOUT_SECONDS)

        except Exception as exc:
            # Boundary: convert infrastructure error to domain error
            execution_time = time.time() - start_time
            metadata = {
                "execution_time_sec": round(execution_time, 2),
                "error_type": type(exc).__name__,
                "params_hash": params_hash,
            }
            async with self._db_pool.acquire() as conn:
                await self._summary_repo.update_status(
                    conn, task_id, "failed",
                    f"Task failed: {type(exc).__name__}",
                    metadata,
                )
            logger.error("Задача %d: ошибка — %s", task_id, type(exc).__name__)
            logger.debug("Детали ошибки задачи: %s", type(exc).__name__)

    def cancel_task(self, task_id: int) -> bool:
        """Отменить активную задачу по ID."""
        task = self._active_tasks.get(task_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    def get_active_count(self) -> int:
        """Количество активно выполняющихся задач."""
        return len([t for t in self._active_tasks.values() if not t.done()])

    async def get_task_status(self, task_id: int) -> SummaryTaskResult | None:
        """Получить статус задачи по ID из БД."""
        async with self._db_pool.acquire() as conn:
            task = await self._summary_repo.get_summary_task(conn, task_id)
        if task is None:
            return None
        return SummaryTaskResult(
            task_id=task.id or 0,
            status=task.status.value if task.status else "unknown",
            from_cache=False,
            is_new=False,
            chat_id=task.chat_id,
        )

    async def cleanup_old_tasks(self, older_than_hours: int = 24) -> int:
        """Очистить старые failed/expired задачи."""
        async with self._db_pool.acquire() as conn:
            return await self._summary_repo.cleanup_old_tasks(conn, older_than_hours)

    async def get_enabled_chat_ids(self) -> list[int]:
        """Получить ID чатов с включённой генерацией summary."""
        return await self._chat_settings.get_enabled_summary_chat_ids()
