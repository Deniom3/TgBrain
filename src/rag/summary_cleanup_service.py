"""
Сервис автоматической очистки summary задач.

Фоновые задачи:
- _cleanup_loop() — удаление старых pending/failed/completed
- _timeout_loop() — перевод processing в failed
"""

import asyncio
import logging
from typing import List, Optional

from src.database import get_pool
from src.settings.repositories.summary_cleanup_settings import SummaryCleanupSettings, SummaryCleanupSettingsRepository

logger = logging.getLogger(__name__)


def calculate_check_interval(settings: SummaryCleanupSettings) -> int:
    """
    Вычислить интервал проверки для очистки pending/failed на основе минимального таймаута.

    Логика:
    1. Собираем все активные таймауты (> 0) кроме processing
    2. Берём минимальный
    3. Делим на 2 для более частой проверки

    Returns:
        Интервал проверки в секундах (минимум 60 секунд)
    """
    active_timeouts: List[int] = []

    if settings.pending_timeout_minutes > 0:
        active_timeouts.append(settings.pending_timeout_minutes)

    if settings.failed_retention_minutes > 0:
        active_timeouts.append(settings.failed_retention_minutes)

    if not active_timeouts:
        return 3600

    check_interval_minutes = min(active_timeouts) / 2
    check_interval_seconds = max(int(check_interval_minutes * 60), 60)

    return check_interval_seconds


class SummaryCleanupService:
    """
    Сервис управления фоновой очисткой summary задач.

    Запускает два независимых цикла:
    - Очистка старых pending/failed/completed задач
    - Перевод зависших processing задач в failed

    Поддерживает корректную остановку через stop().
    """

    def __init__(self, settings_repo: SummaryCleanupSettingsRepository) -> None:
        """
        Инициализировать сервис.

        Args:
            settings_repo: Репозиторий настроек очистки.
        """
        self._settings_repo = settings_repo
        self._cleanup_task: Optional[asyncio.Task[None]] = None
        self._timeout_task: Optional[asyncio.Task[None]] = None
        self._stop_event: Optional[asyncio.Event] = None

    async def start(self) -> None:
        """Запустить оба фоновых цикла очистки."""
        if self._cleanup_task is not None:
            logger.warning("SummaryCleanupService уже запущен")
            return

        self._stop_event = asyncio.Event()
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self._timeout_task = asyncio.create_task(self._timeout_loop())
        logger.info("SummaryCleanupService запущен")

    async def stop(self) -> None:
        """Корректно остановить оба фоновых цикла."""
        if self._cleanup_task is None and self._timeout_task is None:
            logger.warning("SummaryCleanupService не запущен")
            return

        logger.info("Остановка SummaryCleanupService...")

        if self._stop_event:
            self._stop_event.set()

        await self._stop_task(self._cleanup_task, "cleanup")
        await self._stop_task(self._timeout_task, "timeout")

        self._cleanup_task = None
        self._timeout_task = None
        self._stop_event = None
        logger.info("SummaryCleanupService остановлен")

    async def _stop_task(
        self,
        task: Optional[asyncio.Task[None]],
        task_name: str,
    ) -> None:
        """
        Корректно остановить одну фоновую задачу.

        Args:
            task: Задача для остановки.
            task_name: Имя задачи для логирования.
        """
        if task is None:
            return

        try:
            await asyncio.wait_for(task, timeout=10.0)
        except asyncio.TimeoutError:
            logger.warning("Таймаут при остановке %s задачи, отменяем принудительно", task_name)
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        except Exception as e:
            logger.warning("Неожиданная ошибка при остановке %s задачи: %s", task_name, e)

    async def _cleanup_loop(self) -> None:
        """
        Основной цикл очистки старых summary задач.

        Удаляет:
        - pending задачи старше pending_timeout_minutes
        - failed задачи старше failed_retention_minutes
        - completed задачи старше completed_retention_minutes
        """
        if not self._stop_event:
            raise RuntimeError("SummaryCleanupService не инициализирован")

        pool = await get_pool()

        logger.info("Запущен цикл очистки summary задач")

        while not self._stop_event.is_set():
            try:
                settings = await self._settings_repo.get()

                if not settings.auto_cleanup_enabled:
                    await self._wait_or_stop(3600, "Автоочистка отключена, пауза 1 час")
                    continue

                check_interval = calculate_check_interval(settings)
                logger.debug("Интервал проверки очистки: %d секунд", check_interval)
                await self._wait_or_stop(check_interval)

                async with pool.acquire() as conn:
                    if settings.pending_timeout_minutes > 0:
                        result_pending = await conn.execute("""
                            DELETE FROM chat_summaries
                            WHERE status = 'pending'
                              AND created_at < NOW() - ($1::integer * INTERVAL '1 minute')
                        """, settings.pending_timeout_minutes)
                        pending_count = int(result_pending.split()[1]) if "DELETE" in result_pending else 0
                    else:
                        pending_count = 0

                    if settings.failed_retention_minutes > 0:
                        result_failed = await conn.execute("""
                            DELETE FROM chat_summaries
                            WHERE status = 'failed'
                              AND created_at < NOW() - ($1::integer * INTERVAL '1 minute')
                        """, settings.failed_retention_minutes)
                        failed_count = int(result_failed.split()[1]) if "DELETE" in result_failed else 0
                    else:
                        failed_count = 0

                    if settings.completed_retention_minutes is not None and settings.completed_retention_minutes > 0:
                        result_completed = await conn.execute("""
                            DELETE FROM chat_summaries
                            WHERE status = 'completed'
                              AND created_at < NOW() - ($1::integer * INTERVAL '1 minute')
                        """, settings.completed_retention_minutes)
                        completed_count = int(result_completed.split()[1]) if "DELETE" in result_completed else 0
                    else:
                        completed_count = 0

                    if pending_count > 0 or failed_count > 0 or completed_count > 0:
                        logger.info(
                            "Очистка summary задач: "
                            "удалено %d pending, %d failed, %d completed",
                            pending_count,
                            failed_count,
                            completed_count,
                        )

            except asyncio.CancelledError:
                logger.info("Цикл очистки summary задач остановлен")
                break
            except Exception as e:
                logger.error("Ошибка в цикле очистки summary задач: %s", e, exc_info=True)
                await self._wait_or_stop(60)

        logger.info("Цикл очистки summary задач завершён")

    async def _timeout_loop(self) -> None:
        """
        Основной цикл перевода processing задач в failed при таймауте.

        Проверяет каждые processing_timeout_minutes задачи processing,
        которые не обновлялись дольше processing_timeout_minutes.
        """
        if not self._stop_event:
            raise RuntimeError("SummaryCleanupService не инициализирован")

        pool = await get_pool()

        logger.info("Запущен цикл timeout summary задач")

        while not self._stop_event.is_set():
            try:
                settings = await self._settings_repo.get()

                if not settings.auto_cleanup_enabled:
                    await self._wait_or_stop(3600, "Автоочистка отключена, пауза 1 час")
                    continue

                check_interval = max(settings.processing_timeout_minutes * 60, 60)
                logger.debug("Интервал проверки timeout: %d секунд", check_interval)
                await self._wait_or_stop(check_interval)

                if settings.processing_timeout_minutes > 0:
                    async with pool.acquire() as conn:
                        result = await conn.execute("""
                            UPDATE chat_summaries
                            SET status = 'failed',
                                result_text = 'Превышено время ожидания',
                                updated_at = NOW()
                            WHERE status = 'processing'
                              AND updated_at < NOW() - ($1::integer * INTERVAL '1 minute')
                        """, settings.processing_timeout_minutes)

                        count = int(result.split()[1]) if "UPDATE" in result else 0

                        if count > 0:
                            logger.info(
                                "Timeout summary задач: %d задач переведено в failed",
                                count,
                            )

            except asyncio.CancelledError:
                logger.info("Цикл timeout summary задач остановлен")
                break
            except Exception as e:
                logger.error("Ошибка в цикле timeout summary задач: %s", e, exc_info=True)
                await self._wait_or_stop(60)

        logger.info("Цикл timeout summary задач завершён")

    async def _wait_or_stop(self, timeout_seconds: int, message: Optional[str] = None) -> None:
        """
        Ожидать указанное время или выйти по сигналу остановки.

        Args:
            timeout_seconds: Сколько секунд ждать.
            message: Сообщение для логирования при отключённой очистке.
        """
        if self._stop_event is None:
            return

        if message:
            logger.debug(message)

        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            pass
