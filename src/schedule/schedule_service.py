"""
Фоновый сервис проверки расписаний генерации summary.

Проверяет расписания чатов каждую минуту и запускает генерацию summary
при наступлении времени.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from ..application.usecases.generate_summary import GenerateSummaryUseCase, SummaryRequest
from ..application.usecases.result import Success
from ..settings.repositories.chat_settings import ChatSettingsRepository
from ..infrastructure.services.summary_webhook_service import SummaryWebhookService
from .helpers import calculate_next_run
from .exceptions import ScheduleError

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 60
"""
Интервал проверки расписаний в секундах (1 минута).

Баланс между точностью выполнения расписаний и нагрузкой на БД:
- 60 секунд достаточно для расписаний формата HH:MM
- Не создаёт избыточной нагрузки на базу данных
- Позволяет своевременно запускать генерацию summary
"""

ERROR_SLEEP_SECONDS = 60
"""
Время ожидания после ошибки перед повторной попыткой (1 минута).

Защита от cascade failure при проблемах с БД или сервисами:
- 60 секунд дают время на восстановление сервисов
- Предотвращает избыточное давление на БД при временных проблемах
- Снижает риск усугубления ситуации при системных сбоях
"""

DEFAULT_MAX_MESSAGES = 100
"""
Максимальное количество сообщений для генерации summary по умолчанию.

Баланс между полнотой summary и производительностью:
- 100 сообщений достаточно для содержательного summary
- Ограничивает потребление ресурсов LLM
- Защищает от resource exhaustion при генерации
"""


class ScheduleService:
    """
    Сервис управления расписанием генерации summary.

    Проверяет расписания чатов и запускает генерацию summary
    при наступлении времени.
    """

    def __init__(
        self,
        chat_settings_repo: ChatSettingsRepository,
        summary_usecase: GenerateSummaryUseCase,
        webhook_service: SummaryWebhookService,
        check_interval: int = CHECK_INTERVAL_SECONDS,
    ) -> None:
        """
        Инициализировать сервис расписания.

        Args:
            chat_settings_repo: Репозиторий настроек чатов.
            summary_usecase: UseCase для генерации summary.
            webhook_service: Сервис отправки webhook.
            check_interval: Интервал проверки расписаний в секундах (по умолчанию 60).
        """
        self._chat_settings_repo = chat_settings_repo
        self._summary_usecase = summary_usecase
        self._webhook_service = webhook_service
        self.check_interval = check_interval
        self._stop_event: Optional[asyncio.Event] = None
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Запустить фоновую проверку расписаний."""
        if self._task is not None:
            logger.warning("ScheduleService уже запущен")
            return

        self._stop_event = asyncio.Event()

        self._task = asyncio.create_task(self._run())
        logger.info(
            f"ScheduleService запущен с интервалом проверки "
            f"{self.check_interval} секунд"
        )

    async def stop(self) -> None:
        """Остановить фоновую проверку расписаний."""
        if self._task is None:
            logger.warning("ScheduleService не запущен")
            return

        logger.info("Остановка ScheduleService...")

        if self._stop_event:
            self._stop_event.set()

        try:
            await asyncio.wait_for(self._task, timeout=10.0)
        except asyncio.TimeoutError:
            logger.warning("Таймаут при остановке ScheduleService, отменяем задачу")
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        self._task = None
        self._stop_event = None
        logger.info("ScheduleService остановлен")

    async def _run(self) -> None:
        """
        Основной цикл проверки расписаний.

        Работает в цикле while True с asyncio.sleep(check_interval).
        Проверяет все чаты с расписанием и запускает генерацию summary.
        """
        if not self._stop_event:
            raise RuntimeError("ScheduleService не инициализирован")

        logger.info("Запуск цикла проверки расписаний")

        while not self._stop_event.is_set():
            try:
                await self._process_scheduled_summaries()
            except asyncio.CancelledError:
                logger.info("ScheduleService остановлен по сигналу отмены")
                break
            except Exception as e:
                logger.error(
                    "Ошибка в цикле проверки расписаний: %s",
                    type(e).__name__,
                    exc_info=True,
                    extra={
                        "error_type": type(e).__name__,
                    }
                )
                await asyncio.sleep(ERROR_SLEEP_SECONDS)

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.check_interval
                )
            except asyncio.TimeoutError:
                pass

        logger.info("Цикл проверки расписаний завершён")

    async def _process_scheduled_summaries(self) -> None:
        """
        Обработать чаты с активным расписанием.

        Получает все чаты с summary_schedule и next_schedule_run <= now,
        запускает генерацию summary и обновляет next_schedule_run.
        """
        now_utc = datetime.now(timezone.utc)
        logger.debug("Проверка расписаний на %s", now_utc)

        try:
            chats_with_schedule = await self._chat_settings_repo.get_chats_with_schedule()
        except Exception as error:
            logger.error(
                "SCH-006: Ошибка получения чатов с расписанием: %s",
                error,
                exc_info=True,
                extra={
                    "error_type": type(error).__name__,
                    "error_code": "SCH-006",
                }
            )
            raise ScheduleError("Ошибка получения чатов с расписанием", code="SCH-006") from error

        if not chats_with_schedule:
            logger.debug("Нет чатов с активным расписанием")
            return

        processed_count = 0
        triggered_count = 0

        for chat_setting in chats_with_schedule:
            processed_count += 1

            next_schedule_run = chat_setting.next_schedule_run
            if next_schedule_run is not None and next_schedule_run.tzinfo is None:
                next_schedule_run = next_schedule_run.replace(tzinfo=timezone.utc)

            if next_schedule_run is None:
                if chat_setting.summary_schedule is None:
                    logger.warning(
                        "Чат %s имеет null расписание, next_schedule_run не установлен",
                        chat_setting.chat_id,
                    )
                    continue

                try:
                    next_schedule_run = calculate_next_run(chat_setting.summary_schedule)
                    await self._chat_settings_repo.update_next_schedule_run(
                        chat_setting.chat_id,
                        next_schedule_run,
                    )
                    logger.info(
                        "Восстановлен next_schedule_run для чата %s: %s",
                        chat_setting.chat_id,
                        next_schedule_run,
                    )
                except ScheduleError as error:
                    logger.error(
                        "Ошибка расчёта next_schedule_run для чата %s: %s - %s",
                        chat_setting.chat_id,
                        error.code,
                        error.message,
                        exc_info=True,
                    )
                    continue

            if next_schedule_run is None:
                continue

            if next_schedule_run.tzinfo is None:
                next_schedule_run = next_schedule_run.replace(tzinfo=timezone.utc)

            if next_schedule_run > now_utc:
                continue

            logger.info(
                "Запуск генерации summary по расписанию для чата %s: "
                "расписание=%s, next_run=%s",
                chat_setting.chat_id,
                chat_setting.summary_schedule,
                chat_setting.next_schedule_run,
            )

            try:
                period_end = now_utc
                period_minutes = chat_setting.summary_period_minutes or 1440
                period_start = period_end - timedelta(minutes=period_minutes)

                request = SummaryRequest(
                    chat_id=chat_setting.chat_id,
                    period_start=period_start,
                    period_end=period_end,
                    period_minutes=None,
                    custom_prompt=chat_setting.custom_prompt,
                    max_messages=DEFAULT_MAX_MESSAGES,
                )

                result = await self._summary_usecase.get_or_create_task(request)

                if not isinstance(result, Success):
                    logger.warning(
                        "Не удалось создать задачу summary для чата %s",
                        chat_setting.chat_id,
                    )
                    continue

                task_result = result.value
                is_new = task_result.is_new

                if is_new:
                    triggered_count += 1
                    logger.info(
                        "Создана задача summary для чата %s: task_id=%s, период=%sмин",
                        chat_setting.chat_id,
                        task_result.task_id,
                        period_minutes,
                    )
                else:
                    logger.info(
                        "Задача summary для чата %s уже существует: task_id=%s, статус=%s",
                        chat_setting.chat_id,
                        task_result.task_id,
                        task_result.status,
                    )

                # Отправка webhook
                if chat_setting.webhook_enabled and task_result.task_id is not None:
                    webhook_config = await self._chat_settings_repo.get_webhook_config_raw(
                        chat_setting.chat_id
                    )
                    if webhook_config:
                        try:
                            if task_result.from_cache:
                                # Кэш готов — отправить webhook немедленно
                                await self._webhook_service.send_webhook_after_generation(
                                    task_id=task_result.task_id,
                                    chat_id=chat_setting.chat_id,
                                    config=webhook_config,
                                )
                                logger.info(
                                    "Webhook отправлен для чата %s (cached summary, task_id=%s)",
                                    chat_setting.chat_id,
                                    task_result.task_id,
                                )
                            else:
                                # Новая или pending задача — запланировать через dispatcher
                                await self._webhook_service.send_webhook_after_generation(
                                    task_id=task_result.task_id,
                                    chat_id=chat_setting.chat_id,
                                    config=webhook_config,
                                )
                                logger.info(
                                    "Webhook запланирован для чата %s (task_id=%s, from_cache=%s)",
                                    chat_setting.chat_id,
                                    task_result.task_id,
                                    task_result.from_cache,
                                )
                        except Exception as webhook_error:
                            logger.error(
                                "Ошибка отправки webhook для чата %s: %s",
                                chat_setting.chat_id,
                                webhook_error,
                                exc_info=True,
                            )

                if chat_setting.summary_schedule is None:
                    logger.warning(
                        "Чат %s имеет null расписание, пропускаем",
                        chat_setting.chat_id,
                    )
                    continue

                next_run = calculate_next_run(chat_setting.summary_schedule)

                try:
                    updated_setting = await self._chat_settings_repo.update_next_schedule_run(
                        chat_setting.chat_id,
                        next_run,
                    )
                except Exception as error:
                    logger.error(
                        "SCH-003: Ошибка обновления next_schedule_run для чата %s: %s",
                        chat_setting.chat_id,
                        error,
                        exc_info=True,
                        extra={
                            "error_type": type(error).__name__,
                            "error_code": "SCH-003",
                            "chat_id": chat_setting.chat_id,
                        }
                    )
                    raise ScheduleError(
                        "Не удалось обновить next_schedule_run",
                        code="SCH-003",
                    ) from error

                if updated_setting is None:
                    logger.warning(
                        "Чат %s уже обновлён (race condition), пропускаем",
                        chat_setting.chat_id,
                    )
                    continue

                logger.info(
                    "Обновлено next_schedule_run для чата %s: %s",
                    chat_setting.chat_id,
                    next_run,
                )

            except ScheduleError as error:
                logger.error(
                    "Ошибка расписания для чата %s: %s - %s",
                    chat_setting.chat_id,
                    error.code,
                    error.message,
                    exc_info=True,
                    extra={
                        "chat_id": chat_setting.chat_id,
                        "error_code": error.code,
                    }
                )
            except Exception as error:
                logger.error(
                    "Ошибка обработки расписания для чата %s: %s",
                    chat_setting.chat_id,
                    error,
                    exc_info=True,
                    extra={
                        "chat_id": chat_setting.chat_id,
                        "error_type": type(error).__name__,
                    }
                )

        if triggered_count > 0:
            logger.info(
                "Проверка расписаний завершена: обработано %s чатов, "
                "запущено %s генераций",
                processed_count,
                triggered_count,
            )
        else:
            logger.debug(
                "Проверка расписаний завершена: обработано %s чатов, "
                "запущено %s генераций",
                processed_count,
                triggered_count,
            )
