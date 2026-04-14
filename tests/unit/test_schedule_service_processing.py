"""
Тесты для ScheduleService.

Проверка расписания генерации summary.
"""

import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.schedule.schedule_service import ScheduleService, CHECK_INTERVAL_SECONDS


class TestScheduleServiceInit:
    """Тесты инициализации ScheduleService."""

    def test_init_default_interval(self):
        """Инициализация с интервалом по умолчанию."""
        mock_repo = MagicMock()
        mock_usecase = MagicMock()
        mock_webhook_service = MagicMock()

        service = ScheduleService(
            chat_settings_repo=mock_repo,
            summary_usecase=mock_usecase,
            webhook_service=mock_webhook_service,
        )

        assert service.check_interval == CHECK_INTERVAL_SECONDS
        assert service._task is None
        assert service._stop_event is None

    def test_init_custom_interval(self):
        """Инициализация с кастомным интервалом."""
        mock_repo = MagicMock()
        mock_usecase = MagicMock()
        mock_webhook_service = MagicMock()

        service = ScheduleService(
            chat_settings_repo=mock_repo,
            summary_usecase=mock_usecase,
            webhook_service=mock_webhook_service,
            check_interval=30,
        )

        assert service.check_interval == 30


class TestScheduleServiceStartStop:
    """Тесты запуска и остановки."""

    @pytest.mark.asyncio
    async def test_start_creates_task(self):
        """Запуск создаёт asyncio задачу."""
        mock_repo = MagicMock()
        mock_usecase = MagicMock()
        mock_webhook_service = MagicMock()

        service = ScheduleService(
            chat_settings_repo=mock_repo,
            summary_usecase=mock_usecase,
            webhook_service=mock_webhook_service,
        )

        async def noop_run() -> None:
            pass

        with patch.object(service, "_run", noop_run):
            await service.start()

            assert service._task is not None
            assert service._stop_event is not None
            await service.stop()

    @pytest.mark.asyncio
    async def test_start_already_running(self):
        """Повторный запуск когда сервис уже запущен."""
        mock_repo = MagicMock()
        mock_usecase = MagicMock()
        mock_webhook_service = MagicMock()

        service = ScheduleService(
            chat_settings_repo=mock_repo,
            summary_usecase=mock_usecase,
            webhook_service=mock_webhook_service,
        )

        service._task = MagicMock()

        with patch('asyncio.create_task') as mock_create:
            await service.start()

            mock_create.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_stop_success(self):
        """Успешная остановка сервиса."""
        mock_repo = MagicMock()
        mock_usecase = MagicMock()
        mock_webhook_service = MagicMock()

        service = ScheduleService(
            chat_settings_repo=mock_repo,
            summary_usecase=mock_usecase,
            webhook_service=mock_webhook_service,
        )

        # Инициализируем stop_event перед тестом
        service._stop_event = asyncio.Event()
        
        # Создаём реальную задачу, которая будет ждать stop_event
        async def dummy_task():
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                raise

        service._task = asyncio.create_task(dummy_task())

        # Даем задаче запуститься
        await asyncio.sleep(0.01)

        # Запускаем остановку
        await service.stop()
        
        # Даём время на завершение остановки
        await asyncio.sleep(0.1)

        assert service._task is None
        assert service._stop_event is None

    @pytest.mark.asyncio
    async def test_stop_not_running(self):
        """Остановка когда сервис не запущен."""
        mock_repo = MagicMock()
        mock_usecase = MagicMock()
        mock_webhook_service = MagicMock()

        service = ScheduleService(
            chat_settings_repo=mock_repo,
            summary_usecase=mock_usecase,
            webhook_service=mock_webhook_service,
        )

        await service.stop()

        assert service._task is None
        assert service._stop_event is None


class TestProcessScheduledSummaries:
    """Тесты обработки расписаний."""

    @pytest.mark.asyncio
    async def test_no_chats_with_schedule(self):
        """Нет чатов с расписанием."""
        mock_repo = AsyncMock()
        mock_repo.get_chats_with_schedule = AsyncMock(return_value=[])
        
        mock_usecase = MagicMock()
        mock_webhook_service = MagicMock()

        service = ScheduleService(
            chat_settings_repo=mock_repo,
            summary_usecase=mock_usecase,
            webhook_service=mock_webhook_service,
        )

        await service._process_scheduled_summaries()

        mock_repo.get_chats_with_schedule.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_without_schedule(self):
        """Чат без расписания пропускается."""
        mock_chat = MagicMock()
        mock_chat.chat_id = -1001234567890
        mock_chat.summary_schedule = None
        mock_chat.next_schedule_run = None

        mock_repo = AsyncMock()
        mock_repo.get_chats_with_schedule = AsyncMock(return_value=[mock_chat])

        mock_usecase = MagicMock()
        mock_webhook_service = MagicMock()

        service = ScheduleService(
            chat_settings_repo=mock_repo,
            summary_usecase=mock_usecase,
            webhook_service=mock_webhook_service,
        )

        with patch('logging.Logger.warning') as mock_log:
            await service._process_scheduled_summaries()

            mock_log.assert_called()

    @pytest.mark.asyncio
    async def test_future_schedule_not_triggered(self):
        """Расписание в будущем не запускается."""
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        
        mock_chat = MagicMock()
        mock_chat.chat_id = -1001234567890
        mock_chat.summary_schedule = "09:00"
        mock_chat.next_schedule_run = future_time

        mock_repo = AsyncMock()
        mock_repo.get_chats_with_schedule = AsyncMock(return_value=[mock_chat])

        mock_usecase = MagicMock()
        mock_webhook_service = MagicMock()

        service = ScheduleService(
            chat_settings_repo=mock_repo,
            summary_usecase=mock_usecase,
            webhook_service=mock_webhook_service,
        )

        await service._process_scheduled_summaries()

        mock_usecase.get_or_create_task.assert_not_called()
