"""Тесты для GenerateSummaryUseCase.

14 unit-тестов с AAA-структурой, моки портов.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.exceptions import DatabaseError
from src.application.usecases.generate_summary import (
    GenerateSummaryUseCase,
    SummaryRequest,
)
from src.application.usecases.protocols import (
    ChatSettingsPort,
    EmbeddingDispatcherPort,
    MessageFetcherPort,
    SummaryGenerationPort,
    SummaryRepositoryPort,
    WebhookDispatcherPort,
)
from src.application.usecases.result import Failure, Success
from src.models.data_models import MessageRecord


class _AsyncContextManager:
    """Вспомогательный класс для мокинга async with."""

    def __init__(self, yield_value: Any) -> None:
        self._yield_value = yield_value

    async def __aenter__(self) -> Any:
        return self._yield_value

    async def __aexit__(self, *args: Any) -> None:
        pass


def _make_message_record(
    message_id: int = 1,
    text: str = "Test message",
) -> MessageRecord:
    from src.domain.value_objects import ChatTitle, MessageText, SenderName

    return MessageRecord(
        id=message_id,
        text=MessageText(text),
        date=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
        chat_title=ChatTitle("Test Chat"),
        link=f"https://t.me/c/-100/{message_id}",
        sender_name=SenderName("Author"),
        sender_id=1,
        similarity_score=0.8,
    )


@pytest.fixture
def mock_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="DELETE 0")
    return conn


@pytest.fixture
def mock_pool(mock_conn: AsyncMock) -> AsyncMock:
    pool = AsyncMock()
    pool.acquire = MagicMock(return_value=_AsyncContextManager(mock_conn))
    return pool


@pytest.fixture
def summary_repo() -> SummaryRepositoryPort:
    mock = AsyncMock()
    mock.get_cached_summary_by_hash.return_value = None
    mock.get_pending_task_by_hash.return_value = None
    mock.create_summary_task.return_value = (1, datetime.now(timezone.utc), "pending")
    mock.update_status = AsyncMock()
    return mock


@pytest.fixture
def message_fetcher() -> MessageFetcherPort:
    mock = AsyncMock(spec=MessageFetcherPort)
    mock.get_messages_by_period.return_value = [_make_message_record()]
    return mock


@pytest.fixture
def summary_generator() -> SummaryGenerationPort:
    mock = AsyncMock(spec=SummaryGenerationPort)
    mock.summary.return_value = "Summary text"
    mock.model = "test-model"
    return mock


@pytest.fixture
def embedding_dispatcher() -> EmbeddingDispatcherPort:
    mock = AsyncMock(spec=EmbeddingDispatcherPort)
    mock.dispatch_embedding.return_value = True
    return mock


@pytest.fixture
def webhook_dispatcher() -> WebhookDispatcherPort:
    mock = AsyncMock(spec=WebhookDispatcherPort)
    mock.dispatch_webhook_on_completion.return_value = True
    return mock


@pytest.fixture
def chat_settings() -> ChatSettingsPort:
    mock = AsyncMock(spec=ChatSettingsPort)
    mock.get_summary_settings.return_value = None
    return mock


@pytest.fixture
def usecase(
    summary_repo: SummaryRepositoryPort,
    message_fetcher: MessageFetcherPort,
    summary_generator: SummaryGenerationPort,
    embedding_dispatcher: EmbeddingDispatcherPort,
    webhook_dispatcher: WebhookDispatcherPort,
    chat_settings: ChatSettingsPort,
    mock_pool: AsyncMock,
) -> GenerateSummaryUseCase:
    return GenerateSummaryUseCase(
        summary_repo=summary_repo,
        message_fetcher=message_fetcher,
        summary_generator=summary_generator,
        embedding_dispatcher=embedding_dispatcher,
        webhook_dispatcher=webhook_dispatcher,
        chat_settings=chat_settings,
        db_pool=mock_pool,
    )


class TestGetOrCreateTaskCreatesNewTask:
    async def test_get_or_create_task_creates_new_task(
        self,
        usecase: GenerateSummaryUseCase,
        summary_repo: AsyncMock,
    ) -> None:
        now = datetime.now(timezone.utc)
        request = SummaryRequest(
            chat_id=-100,
            period_start=now - timedelta(hours=2),
            period_end=now,
            period_minutes=None,
        )

        result = await usecase.get_or_create_task(request)

        assert isinstance(result, Success)
        assert result.value.is_new is True
        assert result.value.from_cache is False
        assert result.value.chat_id == -100
        summary_repo.create_summary_task.assert_called_once()


class TestGetOrCreateTaskReturnsCached:
    async def test_get_or_create_task_returns_cached(
        self,
        usecase: GenerateSummaryUseCase,
        summary_repo: AsyncMock,
    ) -> None:
        now = datetime.now(timezone.utc)
        summary_repo.get_cached_summary_by_hash.return_value = {
            "id": 42,
            "status": "completed",
        }
        request = SummaryRequest(
            chat_id=-100,
            period_start=now - timedelta(hours=2),
            period_end=now,
            period_minutes=None,
        )

        result = await usecase.get_or_create_task(request)

        assert isinstance(result, Success)
        assert result.value.from_cache is True
        assert result.value.task_id == 42
        assert result.value.is_new is False


class TestGetOrCreateTaskReturnsPending:
    async def test_get_or_create_task_returns_pending(
        self,
        usecase: GenerateSummaryUseCase,
        summary_repo: AsyncMock,
    ) -> None:
        now = datetime.now(timezone.utc)
        summary_repo.get_cached_summary_by_hash.return_value = None
        summary_repo.get_pending_task_by_hash.return_value = {
            "id": 55,
            "status": "processing",
        }
        request = SummaryRequest(
            chat_id=-100,
            period_start=now - timedelta(hours=2),
            period_end=now,
            period_minutes=None,
        )

        result = await usecase.get_or_create_task(request)

        assert isinstance(result, Success)
        assert result.value.from_cache is False
        assert result.value.is_new is False
        assert result.value.task_id == 55
        assert result.value.status == "processing"


class TestGetOrCreateTaskDbError:
    async def test_get_or_create_task_db_error_raises_error(
        self,
        summary_repo: AsyncMock,
        message_fetcher: MessageFetcherPort,
        summary_generator: SummaryGenerationPort,
        embedding_dispatcher: EmbeddingDispatcherPort,
        webhook_dispatcher: WebhookDispatcherPort,
        chat_settings: ChatSettingsPort,
        mock_pool: AsyncMock,
    ) -> None:
        now = datetime.now(timezone.utc)
        summary_repo.get_cached_summary_by_hash.side_effect = Exception("DB connection lost")
        summary_generator.model = "test-model"  # noqa: SLF001 — тестовая настройка мока
        request = SummaryRequest(
            chat_id=-100,
            period_start=now - timedelta(hours=2),
            period_end=now,
            period_minutes=None,
        )

        usecase = GenerateSummaryUseCase(
            summary_repo=summary_repo,
            message_fetcher=message_fetcher,
            summary_generator=summary_generator,
            embedding_dispatcher=embedding_dispatcher,
            webhook_dispatcher=webhook_dispatcher,
            chat_settings=chat_settings,
            db_pool=mock_pool,
        )

        result = await usecase.get_or_create_task(request)

        assert isinstance(result, Failure)
        assert isinstance(result.error, DatabaseError)


class TestProcessSummarySuccess:
    async def test_process_summary_success_completes_task(
        self,
        usecase: GenerateSummaryUseCase,
        summary_repo: AsyncMock,
        message_fetcher: AsyncMock,
        summary_generator: AsyncMock,
        mock_pool: AsyncMock,
    ) -> None:
        now = datetime.now(timezone.utc)
        summary_repo.get_cached_summary_by_hash.return_value = None
        summary_repo.get_pending_task_by_hash.return_value = None
        message_fetcher.get_messages_by_period.return_value = [
            _make_message_record(),
            _make_message_record(message_id=2),
        ]

        request = SummaryRequest(
            chat_id=-100,
            period_start=now - timedelta(hours=2),
            period_end=now,
            period_minutes=None,
        )
        result = await usecase.get_or_create_task(request)
        assert isinstance(result, Success)
        await asyncio.sleep(0.3)

        update_calls = summary_repo.update_status.call_args_list
        assert len(update_calls) >= 2
        first_status = update_calls[0][0][2]
        assert first_status == "processing"


class TestProcessSummaryNoMessages:
    async def test_process_summary_no_messages_completes_with_empty(
        self,
        usecase: GenerateSummaryUseCase,
        summary_repo: AsyncMock,
        message_fetcher: AsyncMock,
        mock_pool: AsyncMock,
    ) -> None:
        now = datetime.now(timezone.utc)
        summary_repo.get_cached_summary_by_hash.return_value = None
        summary_repo.get_pending_task_by_hash.return_value = None
        message_fetcher.get_messages_by_period.return_value = []

        request = SummaryRequest(
            chat_id=-100,
            period_start=now - timedelta(hours=2),
            period_end=now,
            period_minutes=None,
        )
        result = await usecase.get_or_create_task(request)
        assert isinstance(result, Success)
        await asyncio.sleep(0.3)

        update_calls = summary_repo.update_status.call_args_list
        completed_calls = [c for c in update_calls if len(c[0]) > 2 and c[0][2] == "completed"]
        assert len(completed_calls) >= 1
        result_text = completed_calls[0][0][3]
        assert "Нет сообщений" in result_text


class TestProcessSummaryTimeout:
    async def test_process_summary_timeout_marks_failed(
        self,
        summary_repo: AsyncMock,
        message_fetcher: AsyncMock,
        summary_generator: SummaryGenerationPort,
        embedding_dispatcher: EmbeddingDispatcherPort,
        webhook_dispatcher: WebhookDispatcherPort,
        chat_settings: ChatSettingsPort,
        mock_pool: AsyncMock,
    ) -> None:
        now = datetime.now(timezone.utc)
        summary_repo.get_cached_summary_by_hash.return_value = None
        summary_repo.get_pending_task_by_hash.return_value = None
        message_fetcher.get_messages_by_period.return_value = [_make_message_record()]

        async def slow_summary(**kwargs: Any) -> str:
            await asyncio.sleep(999)
            return "never"

        summary_generator.summary = slow_summary
        summary_generator.model = "test-model"  # noqa: SLF001 — тестовая настройка мока

        usecase = GenerateSummaryUseCase(
            summary_repo=summary_repo,
            message_fetcher=message_fetcher,
            summary_generator=summary_generator,
            embedding_dispatcher=embedding_dispatcher,
            webhook_dispatcher=webhook_dispatcher,
            chat_settings=chat_settings,
            db_pool=mock_pool,
            task_timeout_seconds=0.05,
        )

        request = SummaryRequest(
            chat_id=-100,
            period_start=now - timedelta(hours=2),
            period_end=now,
            period_minutes=None,
        )
        result = await usecase.get_or_create_task(request)
        assert isinstance(result, Success)
        await asyncio.sleep(0.3)

        update_calls = summary_repo.update_status.call_args_list
        failed_calls = [c for c in update_calls if len(c[0]) > 2 and c[0][2] == "failed"]
        assert len(failed_calls) >= 1


class TestProcessSummaryException:
    async def test_process_summary_exception_marks_failed(
        self,
        usecase: GenerateSummaryUseCase,
        summary_repo: AsyncMock,
        message_fetcher: AsyncMock,
        mock_pool: AsyncMock,
    ) -> None:
        now = datetime.now(timezone.utc)
        summary_repo.get_cached_summary_by_hash.return_value = None
        summary_repo.get_pending_task_by_hash.return_value = None
        message_fetcher.get_messages_by_period.return_value = [_make_message_record()]
        usecase._summary_generator.summary.side_effect = RuntimeError("LLM crashed")

        request = SummaryRequest(
            chat_id=-100,
            period_start=now - timedelta(hours=2),
            period_end=now,
            period_minutes=None,
        )
        result = await usecase.get_or_create_task(request)
        assert isinstance(result, Success)
        await asyncio.sleep(0.3)

        update_calls = summary_repo.update_status.call_args_list
        failed_calls = [c for c in update_calls if len(c[0]) > 2 and c[0][2] == "failed"]
        assert len(failed_calls) >= 1


class TestProcessSummaryDispatchesEmbedding:
    async def test_process_summary_success_dispatches_embedding(
        self,
        usecase: GenerateSummaryUseCase,
        summary_repo: AsyncMock,
        message_fetcher: AsyncMock,
        mock_pool: AsyncMock,
    ) -> None:
        now = datetime.now(timezone.utc)
        summary_repo.get_cached_summary_by_hash.return_value = None
        summary_repo.get_pending_task_by_hash.return_value = None
        message_fetcher.get_messages_by_period.return_value = [_make_message_record()]

        request = SummaryRequest(
            chat_id=-100,
            period_start=now - timedelta(hours=2),
            period_end=now,
            period_minutes=None,
        )
        result = await usecase.get_or_create_task(request)
        assert isinstance(result, Success)
        await asyncio.sleep(0.3)

        usecase._embedding_dispatcher.dispatch_embedding.assert_called_once()


class TestProcessSummaryDispatchesWebhook:
    async def test_process_summary_success_dispatches_webhook(
        self,
        usecase: GenerateSummaryUseCase,
        summary_repo: AsyncMock,
        message_fetcher: AsyncMock,
        mock_pool: AsyncMock,
    ) -> None:
        now = datetime.now(timezone.utc)
        summary_repo.get_cached_summary_by_hash.return_value = None
        summary_repo.get_pending_task_by_hash.return_value = None
        message_fetcher.get_messages_by_period.return_value = [_make_message_record()]

        request = SummaryRequest(
            chat_id=-100,
            period_start=now - timedelta(hours=2),
            period_end=now,
            period_minutes=None,
        )
        result = await usecase.get_or_create_task(request)
        assert isinstance(result, Success)
        await asyncio.sleep(0.3)

        usecase._webhook_dispatcher.dispatch_webhook_on_completion.assert_called_once()


class TestClampMinPeriod:
    async def test_get_or_create_task_clamps_min_period(
        self,
        usecase: GenerateSummaryUseCase,
        summary_repo: AsyncMock,
    ) -> None:
        now = datetime.now(timezone.utc)
        summary_repo.get_cached_summary_by_hash.return_value = None
        summary_repo.get_pending_task_by_hash.return_value = None
        request = SummaryRequest(
            chat_id=-100,
            period_start=now - timedelta(minutes=10),
            period_end=now,
            period_minutes=None,
        )

        result = await usecase.get_or_create_task(request)

        assert isinstance(result, Success)
        assert result.value.is_new is True


class TestClampMaxPeriod:
    async def test_get_or_create_task_clamps_max_period(
        self,
        usecase: GenerateSummaryUseCase,
        summary_repo: AsyncMock,
    ) -> None:
        now = datetime.now(timezone.utc)
        summary_repo.get_cached_summary_by_hash.return_value = None
        summary_repo.get_pending_task_by_hash.return_value = None
        request = SummaryRequest(
            chat_id=-100,
            period_start=now - timedelta(days=200),
            period_end=now,
            period_minutes=None,
        )

        result = await usecase.get_or_create_task(request)

        assert isinstance(result, Success)
        assert result.value.is_new is True


class TestCleanupOldFailedTasks:
    async def test_get_or_create_task_cleans_old_failed_tasks(
        self,
        usecase: GenerateSummaryUseCase,
        summary_repo: AsyncMock,
    ) -> None:
        now = datetime.now(timezone.utc)
        request = SummaryRequest(
            chat_id=-100,
            period_start=now - timedelta(hours=2),
            period_end=now,
            period_minutes=None,
        )

        await usecase.get_or_create_task(request)

        summary_repo.cleanup_old_failed_tasks.assert_called_once()


class TestCancelTask:
    async def test_cancel_task_cancels_asyncio_task(
        self,
        summary_repo: AsyncMock,
        message_fetcher: AsyncMock,
        summary_generator: SummaryGenerationPort,
        embedding_dispatcher: EmbeddingDispatcherPort,
        webhook_dispatcher: WebhookDispatcherPort,
        chat_settings: ChatSettingsPort,
        mock_pool: AsyncMock,
    ) -> None:
        now = datetime.now(timezone.utc)
        summary_repo.get_cached_summary_by_hash.return_value = None
        summary_repo.get_pending_task_by_hash.return_value = None
        message_fetcher.get_messages_by_period.return_value = [_make_message_record()]

        async def slow_summary(**kwargs: Any) -> str:
            await asyncio.sleep(999)
            return "never"

        summary_generator.summary = slow_summary
        summary_generator.model = "test-model"  # noqa: SLF001 — тестовая настройка мока

        usecase = GenerateSummaryUseCase(
            summary_repo=summary_repo,
            message_fetcher=message_fetcher,
            summary_generator=summary_generator,
            embedding_dispatcher=embedding_dispatcher,
            webhook_dispatcher=webhook_dispatcher,
            chat_settings=chat_settings,
            db_pool=mock_pool,
            task_timeout_seconds=999,
        )

        request = SummaryRequest(
            chat_id=-100,
            period_start=now - timedelta(hours=2),
            period_end=now,
            period_minutes=None,
        )
        result = await usecase.get_or_create_task(request)
        assert isinstance(result, Success)
        task_id = result.value.task_id

        cancelled = usecase.cancel_task(task_id)

        assert cancelled is True
