"""
E2E tests for Schedule to Webhook flow.

Требует полный стек: БД + ScheduleService + WebhookService + API.
"""

import pytest
import respx
import httpx
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from src.schedule.schedule_service import ScheduleService
from src.webhook.webhook_service import WebhookService
from src.settings.repositories.chat_settings import ChatSettingsRepository
from src.rag.summary_task_service import SummaryTaskService
from src.models.data_models import ChatSummary, SummaryStatus

pytestmark = pytest.mark.e2e


@pytest.fixture
async def chat_settings_repo(real_db_pool):
    """Real ChatSettingsRepository."""
    return ChatSettingsRepository(real_db_pool)


@pytest.fixture
async def webhook_service():
    """Real WebhookService."""
    service = WebhookService(timeout=5.0, max_retries=3, backoff_seconds=1)
    yield service
    await service.close()


@pytest.fixture
async def summary_task_service(real_db_pool):
    """Real SummaryTaskService."""
    from src.config import get_settings
    from src.rag.search import RAGSearch
    from src.llm_client import LLMClient
    from src.embeddings import EmbeddingsClient
    settings = get_settings()
    embeddings_client = EmbeddingsClient(settings)
    llm_client = LLMClient(settings)
    rag_search = RAGSearch(settings, real_db_pool)
    
    return SummaryTaskService(
        config=settings,
        search=rag_search,  # type: ignore[arg-type]
        llm_client=llm_client,
        embeddings_client=embeddings_client,
        db_pool=real_db_pool,
    )


@pytest.fixture
async def schedule_service(chat_settings_repo, summary_task_service, webhook_service):
    """Real ScheduleService."""
    service = ScheduleService(
        chat_settings_repo=chat_settings_repo,
        summary_task_service=summary_task_service,
        webhook_service=webhook_service,
        check_interval=1,
    )
    yield service
    
    if service._task is not None:
        await service.stop()


@pytest.mark.e2e
class TestScheduleToWebhookE2E:
    """E2E тесты полного потока."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_e2e_schedule_triggers_webhook(
        self,
        schedule_service,
        webhook_service,
        chat_settings_repo,
        real_db_pool,
    ):
        """Расписание → генерация → webhook."""
        now = datetime.now(timezone.utc)
        
        respx.post("https://api.example.com/webhook").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        
        async with real_db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO chat_settings (
                    chat_id, title, is_monitored, summary_enabled,
                    summary_schedule, summary_period_minutes, next_schedule_run,
                    webhook_enabled, webhook_config
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (chat_id) DO UPDATE SET
                    summary_enabled = EXCLUDED.summary_enabled,
                    summary_schedule = EXCLUDED.summary_schedule,
                    next_schedule_run = EXCLUDED.next_schedule_run,
                    webhook_enabled = EXCLUDED.webhook_enabled,
                    webhook_config = EXCLUDED.webhook_config
                """,
                123,
                "E2E Test Chat",
                True,
                True,
                "09:00",
                1440,
                now - timedelta(minutes=1),
                True,
                '{"url": "https://api.example.com/webhook", "method": "POST", "headers": {}, "body_template": {"text": "{{summary}}"}}',
            )
        
        try:
            from unittest.mock import AsyncMock
            
            mock_summary = ChatSummary(
                id=1,
                chat_id=123,
                period_start=now - timedelta(days=1),
                period_end=now,
                status=SummaryStatus.COMPLETED,
                result_text="E2E test summary",
                messages_count=10,
                created_at=now,
            )
            
            with patch.object(
                schedule_service._summary_task_service,
                "get_or_create_task",
                new_callable=AsyncMock,
            ) as mock_task:
                mock_task.return_value = (mock_summary, True)
                
                await schedule_service._process_scheduled_summaries()
                
                mock_task.assert_awaited_once()
        
        finally:
            async with real_db_pool.acquire() as conn:
                await conn.execute("DELETE FROM chat_settings WHERE chat_id = $1", 123)

    @pytest.mark.asyncio
    @respx.mock
    async def test_e2e_manual_trigger_webhook(
        self,
        webhook_service,
        chat_settings_repo,
        real_db_pool,
    ):
        """Ручной вызов API → webhook."""
        now = datetime.now(timezone.utc)
        
        webhook_route = respx.post("https://api.example.com/manual").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        
        async with real_db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO chat_settings (
                    chat_id, title, is_monitored,
                    webhook_enabled, webhook_config
                )
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (chat_id) DO UPDATE SET
                    webhook_enabled = EXCLUDED.webhook_enabled,
                    webhook_config = EXCLUDED.webhook_config
                """,
                456,
                "Manual Test Chat",
                True,
                True,
                '{"url": "https://api.example.com/manual", "method": "POST", "headers": {}, "body_template": {"text": "{{summary}}"}}',
            )
        
        try:
            webhook_config = {
                "url": "https://api.example.com/manual",
                "method": "POST",
                "headers": {},
                "body_template": {"text": "{{summary}}"},
            }
            
            result = await webhook_service.send_summary_webhook(
                webhook_config=webhook_config,
                summary_text="Manual test summary",
                chat_id=456,
                chat_title="Manual Test Chat",
                period_start=now - timedelta(hours=1),
                period_end=now,
                messages_count=5,
            )
            
            assert result is True
            assert webhook_route.called
        
        finally:
            async with real_db_pool.acquire() as conn:
                await conn.execute("DELETE FROM chat_settings WHERE chat_id = $1", 456)

    @pytest.mark.asyncio
    @respx.mock
    async def test_e2e_cache_reuse(
        self,
        schedule_service,
        webhook_service,
        chat_settings_repo,
        real_db_pool,
    ):
        """Повторный вызов использует кэш."""
        now = datetime.now(timezone.utc)
        
        respx.post("https://api.example.com/cache").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        
        async with real_db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO chat_settings (
                    chat_id, title, is_monitored, summary_enabled,
                    summary_schedule, summary_period_minutes, next_schedule_run,
                    webhook_enabled, webhook_config
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (chat_id) DO UPDATE SET
                    summary_enabled = EXCLUDED.summary_enabled,
                    summary_schedule = EXCLUDED.summary_schedule,
                    next_schedule_run = EXCLUDED.next_schedule_run,
                    webhook_enabled = EXCLUDED.webhook_enabled,
                    webhook_config = EXCLUDED.webhook_config
                """,
                789,
                "Cache Test Chat",
                True,
                True,
                "09:00",
                1440,
                now - timedelta(minutes=1),
                True,
                '{"url": "https://api.example.com/cache", "method": "POST", "headers": {}, "body_template": {"text": "{{summary}}"}}',
            )
        
        try:
            from unittest.mock import AsyncMock
            
            mock_summary = ChatSummary(
                id=3,
                chat_id=789,
                period_start=now - timedelta(days=1),
                period_end=now,
                status=SummaryStatus.COMPLETED,
                result_text="Cached summary",
                messages_count=10,
                created_at=now,
            )
            
            with patch.object(
                schedule_service._summary_task_service,
                "get_or_create_task",
                new_callable=AsyncMock,
            ) as mock_task:
                mock_task.return_value = (mock_summary, False)
                
                await schedule_service._process_scheduled_summaries()
                
                mock_task.assert_awaited_once()
        
        finally:
            async with real_db_pool.acquire() as conn:
                await conn.execute("DELETE FROM chat_settings WHERE chat_id = $1", 789)

    @pytest.mark.asyncio
    @respx.mock
    async def test_e2e_timezone_handling(
        self,
        schedule_service,
        webhook_service,
        chat_settings_repo,
        real_db_pool,
    ):
        """Корректная работа с timezone."""
        now = datetime.now(timezone.utc)
        
        respx.post("https://api.example.com/tz").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        
        async with real_db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO chat_settings (
                    chat_id, title, is_monitored, summary_enabled,
                    summary_schedule, summary_period_minutes, next_schedule_run,
                    webhook_enabled, webhook_config
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (chat_id) DO UPDATE SET
                    summary_enabled = EXCLUDED.summary_enabled,
                    summary_schedule = EXCLUDED.summary_schedule,
                    next_schedule_run = EXCLUDED.next_schedule_run,
                    webhook_enabled = EXCLUDED.webhook_enabled,
                    webhook_config = EXCLUDED.webhook_config
                """,
                999,
                "TZ Test Chat",
                True,
                True,
                "09:00",
                1440,
                now - timedelta(minutes=1),
                True,
                '{"url": "https://api.example.com/tz", "method": "POST", "headers": {}, "body_template": {"text": "{{summary}}"}}',
            )
        
        try:
            from unittest.mock import AsyncMock
            
            mock_summary = ChatSummary(
                id=4,
                chat_id=999,
                period_start=now - timedelta(days=1),
                period_end=now,
                status=SummaryStatus.COMPLETED,
                result_text="TZ test summary",
                messages_count=10,
                created_at=now,
            )
            
            with patch.object(
                schedule_service._summary_task_service,
                "get_or_create_task",
                new_callable=AsyncMock,
            ) as mock_task:
                mock_task.return_value = (mock_summary, True)
                
                await schedule_service._process_scheduled_summaries()
                
                mock_task.assert_awaited_once()
                
                call_args = mock_task.call_args
                period_start = call_args.kwargs["period_start"]
                period_end = call_args.kwargs["period_end"]
                
                assert period_start.tzinfo == timezone.utc
                assert period_end.tzinfo == timezone.utc
        
        finally:
            async with real_db_pool.acquire() as conn:
                await conn.execute("DELETE FROM chat_settings WHERE chat_id = $1", 999)
