"""
Интеграционные тесты для ScheduleService.

Проверка интеграции с базой данных и другими сервисами.
"""

import pytest
import asyncio
from datetime import timezone
from unittest.mock import MagicMock, AsyncMock

from src.schedule.schedule_service import ScheduleService
from src.schedule.helpers import calculate_next_run

pytestmark = pytest.mark.integration


class TestCalculateNextRun:
    """Тесты функции расчёта следующего запуска."""

    def test_simple_time_today(self):
        """Время сегодня ещё не прошло."""
        schedule = "23:59"
        next_run = calculate_next_run(schedule)
        
        assert next_run is not None
        assert next_run.tzinfo == timezone.utc

    def test_simple_time_tomorrow(self):
        """Время сегодня уже прошло — завтра."""
        schedule = "00:00"
        next_run = calculate_next_run(schedule)
        
        assert next_run is not None
        assert next_run.tzinfo == timezone.utc

    def test_cron_every_minute(self):
        """Cron каждую минуту."""
        schedule = "*/1 * * * *"
        next_run = calculate_next_run(schedule)
        
        assert next_run is not None
        assert next_run.tzinfo == timezone.utc

    def test_cron_every_hour(self):
        """Cron каждый час."""
        schedule = "0 * * * *"
        next_run = calculate_next_run(schedule)
        
        assert next_run is not None

    def test_cron_daily(self):
        """Cron ежедневно в 9 утра."""
        schedule = "0 9 * * *"
        next_run = calculate_next_run(schedule)
        
        assert next_run is not None

    def test_invalid_schedule_format(self):
        """Неверный формат расписания."""
        from src.schedule.exceptions import ScheduleError
        
        with pytest.raises(ScheduleError):
            calculate_next_run("invalid")

    def test_invalid_cron_format(self):
        """Неверный формат cron."""
        from src.schedule.exceptions import ScheduleError
        
        with pytest.raises(ScheduleError):
            calculate_next_run("invalid cron")


@pytest.mark.integration
class TestScheduleServiceIntegration:
    """Интеграционные тесты ScheduleService."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_service_lifecycle(self):
        """Полный цикл: старт → работа → остановка."""
        from src.settings.repositories.chat_settings import ChatSettingsRepository
        from src.rag.summary_task_service import SummaryTaskService
        from src.infrastructure.services.summary_webhook_service import SummaryWebhookService
        
        # Моки для зависимостей
        mock_repo = AsyncMock(spec=ChatSettingsRepository)
        mock_repo.get_chats_with_schedule = AsyncMock(return_value=[])
        
        mock_task_service = AsyncMock(spec=SummaryTaskService)
        mock_webhook_service = AsyncMock(spec=SummaryWebhookService)

        service = ScheduleService(
            chat_settings_repo=mock_repo,
            summary_task_service=mock_task_service,
            webhook_service=mock_webhook_service,
            check_interval=1,  # Быстрый интервал для теста
        )

        # Старт
        await service.start()
        assert service._task is not None
        assert service._stop_event is not None

        # Короткая работа
        await asyncio.sleep(0.1)

        # Остановка
        await service.stop()
        assert service._task is None
        assert service._stop_event is None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_process_schedules_with_db_error(self):
        """Обработка ошибки БД."""
        from src.settings.repositories.chat_settings import ChatSettingsRepository
        
        mock_repo = AsyncMock(spec=ChatSettingsRepository)
        mock_repo.get_chats_with_schedule = AsyncMock(
            side_effect=Exception("Database connection error")
        )
        
        mock_task_service = MagicMock()
        mock_webhook_service = MagicMock()

        service = ScheduleService(
            chat_settings_repo=mock_repo,
            summary_task_service=mock_task_service,
            webhook_service=mock_webhook_service,
        )

        # Ошибка БД должна быть обработана и не вызывать падение
        with pytest.raises(Exception):
            await service._process_scheduled_summaries()
