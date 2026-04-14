"""
Integration tests for ScheduleService.

Требует реальную БД (PostgreSQL).
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

from src.schedule.schedule_service import ScheduleService
from src.settings.repositories.chat_settings import ChatSettingsRepository
from src.application.usecases.generate_summary import SummaryTaskResult
from src.application.usecases.result import Success

pytestmark = pytest.mark.integration


@pytest.fixture
async def chat_settings_repo(real_db_pool):
    """Real ChatSettingsRepository."""
    return ChatSettingsRepository(real_db_pool)


@pytest.fixture
async def mock_summary_usecase():
    """Mock GenerateSummaryUseCase."""
    return AsyncMock()


@pytest.fixture
async def schedule_service(chat_settings_repo, mock_summary_usecase):
    """Create ScheduleService with real dependencies."""
    from unittest.mock import MagicMock
    from src.infrastructure.services.summary_webhook_service import SummaryWebhookService
    webhook_service = MagicMock(spec=SummaryWebhookService)
    service = ScheduleService(
        chat_settings_repo=chat_settings_repo,
        summary_usecase=mock_summary_usecase,
        webhook_service=webhook_service,
        check_interval=1,
    )
    yield service

    if service._task is not None:
        await service.stop()


@pytest.mark.integration
class TestScheduleServiceFullCycle:
    """Интеграционные тесты полного цикла."""

    @pytest.mark.asyncio
    async def test_schedule_service_full_cycle(
        self, schedule_service, chat_settings_repo, real_db_pool
    ):
        """Полный цикл: чат → генерация → webhook."""
        now = datetime.now(timezone.utc)

        async with real_db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO chat_settings (chat_id, title, is_monitored, summary_enabled,
                                          summary_schedule, summary_period_minutes, next_schedule_run)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (chat_id) DO UPDATE SET
                    summary_enabled = EXCLUDED.summary_enabled,
                    summary_schedule = EXCLUDED.summary_schedule,
                    next_schedule_run = EXCLUDED.next_schedule_run
                """,
                123,
                "Test Chat",
                True,
                True,
                "09:00",
                1440,
                now - timedelta(minutes=1),
            )

        try:
            mock_result = SummaryTaskResult(
                task_id=1,
                status="pending",
                from_cache=False,
                is_new=True,
                chat_id=123,
            )
            schedule_service._summary_usecase.get_or_create_task.return_value = Success(mock_result)

            await schedule_service._process_scheduled_summaries()

            schedule_service._summary_usecase.get_or_create_task.assert_awaited_once()

            async with real_db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT next_schedule_run FROM chat_settings WHERE chat_id = $1",
                    123,
                )
                assert row is not None
                assert row["next_schedule_run"] > now

        finally:
            async with real_db_pool.acquire() as conn:
                await conn.execute("DELETE FROM chat_settings WHERE chat_id = $1", 123)

    @pytest.mark.asyncio
    async def test_schedule_service_multiple_chats(
        self, schedule_service, chat_settings_repo, real_db_pool
    ):
        """Несколько чатов одновременно."""
        now = datetime.now(timezone.utc)

        async with real_db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO chat_settings (chat_id, title, is_monitored, summary_enabled,
                                          summary_schedule, summary_period_minutes, next_schedule_run)
                VALUES
                    ($1, $2, $3, $4, $5, $6, $7),
                    ($8, $9, $10, $11, $12, $13, $14)
                ON CONFLICT (chat_id) DO UPDATE SET
                    summary_enabled = EXCLUDED.summary_enabled,
                    summary_schedule = EXCLUDED.summary_schedule,
                    next_schedule_run = EXCLUDED.next_schedule_run
                """,
                123,
                "Chat 1",
                True,
                True,
                "09:00",
                1440,
                now - timedelta(minutes=1),
                456,
                "Chat 2",
                True,
                True,
                "*/30",
                60,
                now - timedelta(minutes=1),
            )

        try:
            mock_result = SummaryTaskResult(
                task_id=1,
                status="pending",
                from_cache=False,
                is_new=True,
                chat_id=123,
            )
            schedule_service._summary_usecase.get_or_create_task.return_value = Success(mock_result)

            await schedule_service._process_scheduled_summaries()

            assert schedule_service._summary_usecase.get_or_create_task.await_count == 2

        finally:
            async with real_db_pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM chat_settings WHERE chat_id IN ($1, $2)", 123, 456
                )

    @pytest.mark.asyncio
    async def test_schedule_service_cron_schedule(
        self, schedule_service, chat_settings_repo, real_db_pool
    ):
        """Cron расписание."""
        now = datetime.now(timezone.utc)

        async with real_db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO chat_settings (chat_id, title, is_monitored, summary_enabled,
                                          summary_schedule, summary_period_minutes, next_schedule_run)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (chat_id) DO UPDATE SET
                    summary_enabled = EXCLUDED.summary_enabled,
                    summary_schedule = EXCLUDED.summary_schedule,
                    next_schedule_run = EXCLUDED.next_schedule_run
                """,
                789,
                "Cron Chat",
                True,
                True,
                "0 */2 * * *",
                120,
                now - timedelta(minutes=1),
            )

        try:
            mock_result = SummaryTaskResult(
                task_id=1,
                status="pending",
                from_cache=False,
                is_new=True,
                chat_id=789,
            )
            schedule_service._summary_usecase.get_or_create_task.return_value = Success(mock_result)

            await schedule_service._process_scheduled_summaries()

            schedule_service._summary_usecase.get_or_create_task.assert_awaited_once()

        finally:
            async with real_db_pool.acquire() as conn:
                await conn.execute("DELETE FROM chat_settings WHERE chat_id = $1", 789)

    @pytest.mark.asyncio
    async def test_schedule_service_simple_schedule(
        self, schedule_service, chat_settings_repo, real_db_pool
    ):
        """Простое расписание HH:MM."""
        now = datetime.now(timezone.utc)

        async with real_db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO chat_settings (chat_id, title, is_monitored, summary_enabled,
                                          summary_schedule, summary_period_minutes, next_schedule_run)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (chat_id) DO UPDATE SET
                    summary_enabled = EXCLUDED.summary_enabled,
                    summary_schedule = EXCLUDED.summary_schedule,
                    next_schedule_run = EXCLUDED.next_schedule_run
                """,
                111,
                "Simple Chat",
                True,
                True,
                "14:30",
                1440,
                now - timedelta(minutes=1),
            )

        try:
            mock_result = SummaryTaskResult(
                task_id=1,
                status="pending",
                from_cache=False,
                is_new=True,
                chat_id=111,
            )
            schedule_service._summary_usecase.get_or_create_task.return_value = Success(mock_result)

            await schedule_service._process_scheduled_summaries()

            schedule_service._summary_usecase.get_or_create_task.assert_awaited_once()

        finally:
            async with real_db_pool.acquire() as conn:
                await conn.execute("DELETE FROM chat_settings WHERE chat_id = $1", 111)

    @pytest.mark.asyncio
    async def test_schedule_service_error_recovery(
        self, schedule_service, chat_settings_repo, real_db_pool
    ):
        """Восстановление после ошибки."""
        now = datetime.now(timezone.utc)

        async with real_db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO chat_settings (chat_id, title, is_monitored, summary_enabled,
                                          summary_schedule, summary_period_minutes, next_schedule_run)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (chat_id) DO UPDATE SET
                    summary_enabled = EXCLUDED.summary_enabled,
                    summary_schedule = EXCLUDED.summary_schedule,
                    next_schedule_run = EXCLUDED.next_schedule_run
                """,
                222,
                "Error Chat",
                True,
                True,
                "09:00",
                1440,
                now - timedelta(minutes=1),
            )

        try:
            from src.application.usecases.result import Failure
            schedule_service._summary_usecase.get_or_create_task.return_value = Failure(Exception("Test error"))

            await schedule_service._process_scheduled_summaries()

            schedule_service._summary_usecase.get_or_create_task.assert_awaited_once()

        finally:
            async with real_db_pool.acquire() as conn:
                await conn.execute("DELETE FROM chat_settings WHERE chat_id = $1", 222)

    @pytest.mark.asyncio
    async def test_schedule_service_graceful_shutdown(self, schedule_service):
        """Корректная остановка."""
        await schedule_service.start()

        assert schedule_service._task is not None
        assert schedule_service._stop_event is not None

        await schedule_service.stop()

        assert schedule_service._task is None
        assert schedule_service._stop_event is None
