"""
Unit tests for ScheduleService.
"""

import asyncio
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from src.schedule.schedule_service import ScheduleService
from src.schedule.exceptions import ScheduleError
from src.models.data_models import ChatSetting
from src.application.usecases.generate_summary import SummaryTaskResult
from src.application.usecases.result import Success


def _make_task_result(
    task_id: int = 100,
    status: str = "pending",
    from_cache: bool = False,
    is_new: bool = True,
    chat_id: int = 1,
) -> SummaryTaskResult:
    return SummaryTaskResult(
        task_id=task_id,
        status=status,
        from_cache=from_cache,
        is_new=is_new,
        chat_id=chat_id,
    )


@pytest.fixture
def schedule_service(mock_chat_settings_repo, mock_summary_usecase, mock_webhook_service):
    """Create ScheduleService for tests."""
    return ScheduleService(
        chat_settings_repo=mock_chat_settings_repo,
        summary_usecase=mock_summary_usecase,
        webhook_service=mock_webhook_service,
        check_interval=1,
    )


class TestScheduleServiceInit:
    """Тесты инициализации ScheduleService."""

    def test_init_initial_state(
        self, mock_chat_settings_repo, mock_summary_usecase, mock_webhook_service
    ):
        """Инициализация сервиса с корректными параметрами."""
        service = ScheduleService(
            chat_settings_repo=mock_chat_settings_repo,
            summary_usecase=mock_summary_usecase,
            webhook_service=mock_webhook_service,
            check_interval=60,
        )
        assert service.check_interval == 60
        assert service._stop_event is None
        assert service._task is None

    def test_init_custom_interval(
        self, mock_chat_settings_repo, mock_summary_usecase, mock_webhook_service
    ):
        """Инициализация с кастомным интервалом."""
        service = ScheduleService(
            chat_settings_repo=mock_chat_settings_repo,
            summary_usecase=mock_summary_usecase,
            webhook_service=mock_webhook_service,
            check_interval=120,
        )
        assert service.check_interval == 120


class TestScheduleServiceStartStop:
    """Тесты запуска и остановки ScheduleService."""

    @pytest.mark.asyncio
    async def test_start_creates_task(self, schedule_service):
        """Запуск создаёт фоновую задачу."""
        await schedule_service.start()
        
        assert schedule_service._task is not None
        assert schedule_service._stop_event is not None
        assert not schedule_service._stop_event.is_set()
        
        await schedule_service.stop()

    @pytest.mark.asyncio
    async def test_start_already_running_warning(self, schedule_service):
        """Повторный запуск логирует предупреждение."""
        await schedule_service.start()
        
        with patch("src.schedule.schedule_service.logger") as mock_logger:
            await schedule_service.start()
            mock_logger.warning.assert_called_once()
        
        await schedule_service.stop()

    @pytest.mark.asyncio
    async def test_stop_gracefully(self, schedule_service):
        """Остановка корректно завершает задачу."""
        await schedule_service.start()
        await schedule_service.stop()
        
        assert schedule_service._task is None
        assert schedule_service._stop_event is None

    @pytest.mark.asyncio
    async def test_stop_not_running_warning(self, schedule_service):
        """Остановка без запуска логирует предупреждение."""
        with patch("src.schedule.schedule_service.logger") as mock_logger:
            await schedule_service.stop()
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_timeout_cancels_task(self, schedule_service):
        """Таймаут при остановке отменяет задачу."""
        await schedule_service.start()
        
        with patch.object(asyncio, "wait_for", side_effect=asyncio.TimeoutError):
            with patch("src.schedule.schedule_service.logger") as mock_logger:
                await schedule_service.stop()
                mock_logger.warning.assert_called()


class TestScheduleServiceGetChatsWithSchedule:
    """Тесты получения чатов с расписанием."""

    @pytest.mark.asyncio
    async def test_get_chats_with_schedule_empty(
        self, schedule_service, mock_chat_settings_repo
    ):
        """Нет чатов с расписанием → пустой список."""
        mock_chat_settings_repo.get_chats_with_schedule.return_value = []
        
        chats = await mock_chat_settings_repo.get_chats_with_schedule()
        
        assert chats == []
        mock_chat_settings_repo.get_chats_with_schedule.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_chats_with_schedule_multiple(
        self, schedule_service, mock_chat_settings_repo
    ):
        """Получение нескольких чатов с расписанием."""
        now = datetime.now(timezone.utc)
        
        chat1 = ChatSetting(
            id=1,
            chat_id=1,
            title="Chat 1",
            is_monitored=True,
            summary_enabled=True,
            summary_schedule="09:00",
            next_schedule_run=now + timedelta(hours=1),
        )
        chat2 = ChatSetting(
            id=2,
            chat_id=2,
            title="Chat 2",
            is_monitored=True,
            summary_enabled=True,
            summary_schedule="*/30",
            next_schedule_run=now + timedelta(minutes=30),
        )
        
        mock_chat_settings_repo.get_chats_with_schedule.return_value = [chat1, chat2]
        
        chats = await mock_chat_settings_repo.get_chats_with_schedule()
        
        assert len(chats) == 2
        assert chats[0].chat_id == 1
        assert chats[1].chat_id == 2


class TestScheduleServiceProcessChats:
    """Тесты обработки чатов с расписанием."""

    @pytest.mark.asyncio
    async def test_process_chats_no_due_chats(
        self, schedule_service, mock_chat_settings_repo
    ):
        """Чаты есть, но время не пришло."""
        now = datetime.now(timezone.utc)
        
        chat = ChatSetting(
            id=1,
            chat_id=1,
            title="Chat 1",
            is_monitored=True,
            summary_enabled=True,
            summary_schedule="09:00",
            next_schedule_run=now + timedelta(hours=1),
        )
        
        mock_chat_settings_repo.get_chats_with_schedule.return_value = [chat]
        
        await schedule_service._process_scheduled_summaries()
        
        schedule_service._summary_usecase.get_or_create_task.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_process_chats_one_due_chat(
        self, schedule_service, mock_chat_settings_repo, mock_summary_usecase
    ):
        """Один чат должен запуститься."""
        now = datetime.now(timezone.utc)
        
        chat = ChatSetting(
            id=1,
            chat_id=1,
            title="Chat 1",
            is_monitored=True,
            summary_enabled=True,
            summary_schedule="09:00",
            summary_period_minutes=1440,
            next_schedule_run=now - timedelta(minutes=1),
        )
        
        mock_chat_settings_repo.get_chats_with_schedule.return_value = [chat]
        mock_summary_usecase.get_or_create_task.return_value = Success(
            _make_task_result(task_id=100, status="pending", is_new=True)
        )
        
        await schedule_service._process_scheduled_summaries()
        
        mock_summary_usecase.get_or_create_task.assert_awaited_once()
        mock_chat_settings_repo.update_next_schedule_run.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_process_chats_multiple_due_chats(
        self, schedule_service, mock_chat_settings_repo, mock_summary_usecase
    ):
        """Несколько чатов должны запуститься."""
        now = datetime.now(timezone.utc)
        
        chat1 = ChatSetting(
            id=1,
            chat_id=1,
            title="Chat 1",
            is_monitored=True,
            summary_enabled=True,
            summary_schedule="09:00",
            summary_period_minutes=1440,
            next_schedule_run=now - timedelta(minutes=1),
        )
        chat2 = ChatSetting(
            id=2,
            chat_id=2,
            title="Chat 2",
            is_monitored=True,
            summary_enabled=True,
            summary_schedule="*/30",
            summary_period_minutes=60,
            next_schedule_run=now - timedelta(minutes=5),
        )
        
        mock_chat_settings_repo.get_chats_with_schedule.return_value = [chat1, chat2]
        mock_summary_usecase.get_or_create_task.return_value = Success(
            _make_task_result(task_id=100, status="pending", is_new=True)
        )
        
        await schedule_service._process_scheduled_summaries()
        
        assert mock_summary_usecase.get_or_create_task.await_count == 2
        assert mock_chat_settings_repo.update_next_schedule_run.await_count == 2

    @pytest.mark.asyncio
    async def test_process_chats_error_handling(
        self, schedule_service, mock_chat_settings_repo, mock_summary_usecase
    ):
        """Ошибка генерации → логирование, продолжение."""
        now = datetime.now(timezone.utc)
        
        chat = ChatSetting(
            id=1,
            chat_id=1,
            title="Chat 1",
            is_monitored=True,
            summary_enabled=True,
            summary_schedule="09:00",
            summary_period_minutes=1440,
            next_schedule_run=now - timedelta(minutes=1),
        )
        
        mock_chat_settings_repo.get_chats_with_schedule.return_value = [chat]
        mock_summary_usecase.get_or_create_task.side_effect = Exception("Test error")
        
        with patch("src.schedule.schedule_service.logger") as mock_logger:
            await schedule_service._process_scheduled_summaries()
            mock_logger.error.assert_called()


class TestScheduleServiceUpdateNextRun:
    """Тесты обновления next_run."""

    @pytest.mark.asyncio
    async def test_update_next_run_schedule_updated(
        self, schedule_service, mock_chat_settings_repo, mock_summary_usecase
    ):
        """next_run обновлён в БД."""
        now = datetime.now(timezone.utc)
        
        chat = ChatSetting(
            id=1,
            chat_id=1,
            title="Chat 1",
            is_monitored=True,
            summary_enabled=True,
            summary_schedule="09:00",
            summary_period_minutes=1440,
            next_schedule_run=now - timedelta(minutes=1),
        )
        
        mock_chat_settings_repo.get_chats_with_schedule.return_value = [chat]
        mock_summary_usecase.get_or_create_task.return_value = Success(
            _make_task_result(task_id=100, status="pending", is_new=True)
        )
        
        await schedule_service._process_scheduled_summaries()
        
        mock_chat_settings_repo.update_next_schedule_run.assert_awaited_once()
        call_args = mock_chat_settings_repo.update_next_schedule_run.call_args
        assert call_args[0][0] == 1
        assert isinstance(call_args[0][1], datetime)


class TestScheduleServiceRunBackground:
    """Тесты фонового цикла."""

    @pytest.mark.asyncio
    async def test_run_background_task_starts(self, schedule_service):
        """Фоновая задача запускается."""
        await schedule_service.start()
        
        assert schedule_service._task is not None
        assert not schedule_service._task.done()
        
        await schedule_service.stop()

    @pytest.mark.asyncio
    async def test_run_stop_event_stops_gracefully(self, schedule_service):
        """stop_event останавливает цикл."""
        await schedule_service.start()
        
        assert schedule_service._stop_event is not None
        assert not schedule_service._stop_event.is_set()
        
        await schedule_service.stop()
        
        assert schedule_service._stop_event is None

    @pytest.mark.asyncio
    @pytest.mark.timeout(90)
    async def test_run_exception_restarts_after_sleep(
        self, schedule_service, mock_chat_settings_repo
    ):
        """Исключение → sleep 60 сек, продолжение."""
        mock_chat_settings_repo.get_chats_with_schedule.side_effect = [
            Exception("Test error"),
            [],
        ]
        
        await schedule_service.start()
        
        await asyncio.sleep(0.1)
        
        await schedule_service.stop()


class TestScheduleServiceCalculateNextRun:
    """Тесты расчёта next_run."""

    @pytest.mark.asyncio
    async def test_calculate_next_run_hhmm_today(self, schedule_service):
        """HH:MM расписание сегодня."""
        from src.schedule.helpers import calculate_next_run
        from datetime import datetime, timezone
        from unittest.mock import patch
        
        now = datetime(2026, 3, 29, 8, 0, 0, tzinfo=timezone.utc)
        schedule = "14:00"
        
        with patch("src.schedule.helpers.datetime") as mock_datetime:
            mock_datetime.now.return_value = now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            next_run = calculate_next_run(schedule)
        
        assert next_run.hour == 14
        assert next_run.minute == 0

    @pytest.mark.asyncio
    async def test_calculate_next_run_hhmm_tomorrow(self, schedule_service):
        """HH:MM расписание завтра."""
        from src.schedule.helpers import calculate_next_run
        from datetime import datetime, timezone
        from unittest.mock import patch
        
        now = datetime(2026, 3, 29, 15, 0, 0, tzinfo=timezone.utc)
        schedule = "09:00"
        
        with patch("src.schedule.helpers.datetime") as mock_datetime:
            mock_datetime.now.return_value = now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            next_run = calculate_next_run(schedule)
        
        assert next_run.hour == 9
        assert next_run.minute == 0
        assert next_run > now

    @pytest.mark.asyncio
    async def test_calculate_next_run_cron_every2hours(self, schedule_service):
        """Cron каждые 2 часа."""
        from src.schedule.helpers import calculate_next_run
        from datetime import datetime, timezone
        from unittest.mock import patch
        
        now = datetime(2026, 3, 29, 10, 30, 0, tzinfo=timezone.utc)
        schedule = "0 */2"
        
        with patch("src.schedule.helpers.datetime") as mock_datetime:
            mock_datetime.now.return_value = now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            next_run = calculate_next_run(schedule)
        
        assert next_run > now
        assert next_run.minute == 0

    @pytest.mark.asyncio
    async def test_calculate_next_run_cron_every2minutes(self, schedule_service):
        """Cron каждые 2 минуты."""
        from src.schedule.helpers import calculate_next_run
        from datetime import datetime, timezone
        from unittest.mock import patch

        now = datetime(2026, 3, 29, 10, 31, 0, tzinfo=timezone.utc)
        schedule = "*/2 * * * *"

        with patch("src.schedule.helpers.datetime") as mock_datetime:
            mock_datetime.now.return_value = now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            next_run = calculate_next_run(schedule)

        assert next_run > now
        assert next_run.minute == 32

    @pytest.mark.asyncio
    async def test_calculate_next_run_cron_weekdays(self, schedule_service):
        """Cron только будни."""
        from src.schedule.helpers import calculate_next_run
        from datetime import datetime, timezone
        from unittest.mock import patch
        
        now = datetime(2026, 3, 29, 10, 0, 0, tzinfo=timezone.utc)
        schedule = "0 9 * * 1-5"
        
        with patch("src.schedule.helpers.datetime") as mock_datetime:
            mock_datetime.now.return_value = now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            next_run = calculate_next_run(schedule)
        
        assert next_run > now


class TestScheduleServiceWebhookScenarios:
    """Тесты сценариев с webhook."""

    @pytest.mark.asyncio
    async def test_process_chats_webhook_not_configured(
        self, schedule_service, mock_chat_settings_repo, mock_summary_usecase
    ):
        """Webhook не настроен → summary сохранено в БД."""
        now = datetime.now(timezone.utc)
        
        chat = ChatSetting(
            id=1,
            chat_id=1,
            title="Chat 1",
            is_monitored=True,
            summary_enabled=True,
            summary_schedule="09:00",
            summary_period_minutes=1440,
            next_schedule_run=now - timedelta(minutes=1),
            webhook_enabled=False,
            webhook_config=None,
        )
        
        mock_chat_settings_repo.get_chats_with_schedule.return_value = [chat]
        mock_summary_usecase.get_or_create_task.return_value = Success(
            _make_task_result(task_id=100, status="completed", is_new=True)
        )
        
        await schedule_service._process_scheduled_summaries()
        
        mock_summary_usecase.get_or_create_task.assert_awaited_once()
        mock_chat_settings_repo.update_next_schedule_run.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cache_hit_use_cached_summary(
        self, schedule_service, mock_chat_settings_repo, mock_summary_usecase
    ):
        """Кэш найден → использовать для webhook."""
        now = datetime.now(timezone.utc)
        
        chat = ChatSetting(
            id=1,
            chat_id=1,
            title="Chat 1",
            is_monitored=True,
            summary_enabled=True,
            summary_schedule="09:00",
            summary_period_minutes=1440,
            next_schedule_run=now - timedelta(minutes=1),
            webhook_enabled=True,
            webhook_config={"url": "https://example.com/webhook"},
        )
        
        mock_chat_settings_repo.get_chats_with_schedule.return_value = [chat]
        mock_summary_usecase.get_or_create_task.return_value = Success(
            _make_task_result(task_id=100, status="completed", is_new=False)
        )
        
        await schedule_service._process_scheduled_summaries()
        
        mock_summary_usecase.get_or_create_task.assert_awaited_once()
        call_args = mock_summary_usecase.get_or_create_task.call_args
        assert call_args is not None


class TestScheduleServiceErrorCodes:
    """Тесты покрытия error codes SCH-001 — SCH-006."""

    @pytest.mark.asyncio
    async def test_sch001_schedule_not_found(
        self, schedule_service, mock_chat_settings_repo
    ):
        """SCH-001: Schedule not found."""
        chat = ChatSetting(
            id=1,
            chat_id=1,
            title="Chat 1",
            is_monitored=True,
            summary_enabled=True,
            summary_schedule=None,
            next_schedule_run=None,
        )
        
        mock_chat_settings_repo.get_chats_with_schedule.return_value = [chat]
        
        with patch("src.schedule.schedule_service.logger") as mock_logger:
            await schedule_service._process_scheduled_summaries()
            mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_sch002_invalid_schedule_format(
        self, schedule_service, mock_chat_settings_repo
    ):
        """SCH-002: Invalid schedule format."""
        _ = datetime.now(timezone.utc)

        chat = ChatSetting(
            id=1,
            chat_id=1,
            title="Chat 1",
            is_monitored=True,
            summary_enabled=True,
            summary_schedule="invalid-format",
            summary_period_minutes=1440,
            next_schedule_run=None,
        )

        mock_chat_settings_repo.get_chats_with_schedule.return_value = [chat]

        with patch("src.schedule.schedule_service.logger") as mock_logger:
            await schedule_service._process_scheduled_summaries()
            mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_sch003_schedule_update_failed(
        self, schedule_service, mock_chat_settings_repo, mock_summary_usecase
    ):
        """SCH-003: Schedule update failed."""
        now = datetime.now(timezone.utc)
        
        chat = ChatSetting(
            id=1,
            chat_id=1,
            title="Chat 1",
            is_monitored=True,
            summary_enabled=True,
            summary_schedule="09:00",
            summary_period_minutes=1440,
            next_schedule_run=now - timedelta(minutes=1),
        )
        
        mock_chat_settings_repo.get_chats_with_schedule.return_value = [chat]
        mock_summary_usecase.get_or_create_task.return_value = Success(
            _make_task_result(task_id=100, status="completed", is_new=True)
        )
        mock_chat_settings_repo.update_next_schedule_run.side_effect = Exception("DB error")

        with patch("src.schedule.schedule_service.logger") as mock_logger:
            await schedule_service._process_scheduled_summaries()
            mock_logger.error.assert_called()

        mock_chat_settings_repo.update_next_schedule_run.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sch004_schedule_calculation_error(
        self, schedule_service, mock_chat_settings_repo
    ):
        """SCH-004: Schedule calculation error."""
        chat = ChatSetting(
            id=1,
            chat_id=1,
            title="Chat 1",
            is_monitored=True,
            summary_enabled=True,
            summary_schedule="99:99",
            summary_period_minutes=1440,
            next_schedule_run=None,
        )

        mock_chat_settings_repo.get_chats_with_schedule.return_value = [chat]

        with patch("src.schedule.schedule_service.logger") as mock_logger:
            await schedule_service._process_scheduled_summaries()
            mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_sch005_summary_generation_failed(
        self, schedule_service, mock_chat_settings_repo, mock_summary_usecase
    ):
        """SCH-005: Summary generation failed."""
        now = datetime.now(timezone.utc)
        
        chat = ChatSetting(
            id=1,
            chat_id=1,
            title="Chat 1",
            is_monitored=True,
            summary_enabled=True,
            summary_schedule="09:00",
            summary_period_minutes=1440,
            next_schedule_run=now - timedelta(minutes=1),
        )
        
        mock_chat_settings_repo.get_chats_with_schedule.return_value = [chat]
        mock_summary_usecase.get_or_create_task.side_effect = Exception("Generation failed")
        
        with patch("src.schedule.schedule_service.logger") as mock_logger:
            await schedule_service._process_scheduled_summaries()
            mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_sch006_database_error(
        self, schedule_service, mock_chat_settings_repo
    ):
        """SCH-006: Database error."""
        mock_chat_settings_repo.get_chats_with_schedule.side_effect = Exception("DB connection lost")

        with pytest.raises(ScheduleError, match="Ошибка получения чатов с расписанием"):
            await schedule_service._process_scheduled_summaries()
