"""Тесты для SummaryWebhookService."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from src.domain.exceptions import (
    WebhookGenerationError,
    WebhookNotConfiguredError,
    WebhookNotFoundError,
)
from src.infrastructure.services.summary_webhook_service import (
    SummaryWebhookResult,
    SummaryWebhookService,
)
from src.models.data_models import ChatSummary, SummaryStatus
from src.application.usecases.generate_summary import SummaryTaskResult
from src.application.usecases.result import Success, Failure


@pytest.fixture
def mock_config() -> MagicMock:
    """Фикстура mock настроек."""
    return MagicMock()


@pytest.fixture
def mock_rag_search() -> AsyncMock:
    """Фикстура mock RAG поиска."""
    return AsyncMock()


@pytest.fixture
def mock_llm_client() -> AsyncMock:
    """Фикстура mock LLM клиента."""
    return AsyncMock()


@pytest.fixture
def mock_embeddings_client() -> AsyncMock:
    """Фикстура mock embeddings клиента."""
    return AsyncMock()


@pytest.fixture
def mock_db_pool() -> MagicMock:
    """Фикстура mock DB pool."""
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=mock_cm)
    return mock_pool


@pytest.fixture
def mock_webhook_service() -> AsyncMock:
    """Фикстура mock webhook сервиса."""
    return AsyncMock()


@pytest.fixture
def mock_chat_settings_repo() -> AsyncMock:
    """Фикстура mock репозитория настроек чатов."""
    return AsyncMock()


@pytest.fixture
def mock_summary_usecase() -> AsyncMock:
    """Фикстура mock GenerateSummaryUseCase."""
    return AsyncMock()


@pytest.fixture
def summary_webhook_service(
    mock_config: MagicMock,
    mock_rag_search: AsyncMock,
    mock_llm_client: AsyncMock,
    mock_embeddings_client: AsyncMock,
    mock_db_pool: MagicMock,
    mock_webhook_service: AsyncMock,
    mock_chat_settings_repo: AsyncMock,
    mock_summary_usecase: AsyncMock,
) -> SummaryWebhookService:
    """Фикстура SummaryWebhookService с мокнутыми зависимостями."""
    return SummaryWebhookService(
        config=mock_config,
        rag_search=mock_rag_search,
        llm_client=mock_llm_client,
        embeddings_client=mock_embeddings_client,
        db_pool=mock_db_pool,
        webhook_service=mock_webhook_service,
        chat_settings_repo=mock_chat_settings_repo,
        summary_usecase=mock_summary_usecase,
    )


def make_chat_setting(title: str = "Test Chat") -> MagicMock:
    """Создаёт мок ChatSetting."""
    setting = MagicMock()
    setting.title = title
    setting.webhook_enabled = True
    return setting


def make_chat_summary(
    task_id: int = 1,
    status: str = "completed",
    result_text: str | None = "Summary text",
    messages_count: int = 10,
) -> ChatSummary:
    """Создаёт ChatSummary для тестов."""
    now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return ChatSummary(
        id=task_id,
        chat_id=42,
        created_at=now,
        period_start=now - timedelta(hours=1),
        period_end=now,
        result_text=result_text or "",
        messages_count=messages_count,
        status=SummaryStatus(status),
    )


def make_task_result(
    task_id: int = 1,
    status: str = "pending",
    from_cache: bool = False,
    is_new: bool = True,
) -> SummaryTaskResult:
    """Создаёт SummaryTaskResult для тестов."""
    return SummaryTaskResult(
        task_id=task_id,
        status=status,
        from_cache=from_cache,
        is_new=is_new,
        chat_id=42,
    )


class TestSummaryWebhookResult:
    """Тесты SummaryWebhookResult."""

    def test_properties(self) -> None:
        """Все свойства возвращают корректные значения."""
        summary = make_chat_summary()
        result = SummaryWebhookResult(
            summary=summary,
            from_cache=True,
            webhook_sent=True,
            webhook_pending=False,
        )

        assert result.summary is summary
        assert result.from_cache is True
        assert result.webhook_sent is True
        assert result.webhook_pending is False

    def test_webhook_pending_default_false(self) -> None:
        """webhook_pending по умолчанию False."""
        summary = make_chat_summary()
        result = SummaryWebhookResult(
            summary=summary,
            from_cache=False,
            webhook_sent=False,
        )

        assert result.webhook_pending is False


class TestSummaryWebhookServiceInit:
    """Тесты инициализации SummaryWebhookService."""

    def test_init(self, summary_webhook_service: SummaryWebhookService) -> None:
        """Сервис создаётся без ошибок."""
        assert summary_webhook_service is not None


class TestGenerateAndSendWebhook:
    """Тесты generate_and_send_webhook."""

    async def test_chat_not_found_raises_webhook_not_found_error(
        self, summary_webhook_service: SummaryWebhookService,
        mock_chat_settings_repo: AsyncMock,
    ) -> None:
        """Чат не найден → WebhookNotFoundError WHK-001."""
        mock_chat_settings_repo.get.return_value = None

        with pytest.raises(WebhookNotFoundError) as exc_info:
            await summary_webhook_service.generate_and_send_webhook(
                chat_id=999, period_minutes=60,
            )

        assert exc_info.value.code == "WHK-001"
        assert exc_info.value.chat_id == 999

    async def test_webhook_not_configured_raises_webhook_not_configured_error(
        self, summary_webhook_service: SummaryWebhookService,
        mock_chat_settings_repo: AsyncMock,
    ) -> None:
        """Webhook не настроен → WebhookNotConfiguredError WHK-006."""
        setting = make_chat_setting()
        setting.webhook_enabled = False
        mock_chat_settings_repo.get.return_value = setting
        mock_chat_settings_repo.get_webhook_config_raw.return_value = None

        with pytest.raises(WebhookNotConfiguredError) as exc_info:
            await summary_webhook_service.generate_and_send_webhook(
                chat_id=42, period_minutes=60,
            )

        assert exc_info.value.code == "WHK-006"
        assert exc_info.value.chat_id == 42

    async def test_not_cached_returns_pending(
        self, summary_webhook_service: SummaryWebhookService,
        mock_chat_settings_repo: AsyncMock,
        mock_summary_usecase: AsyncMock,
    ) -> None:
        """Задача не завершена → pending."""
        setting = make_chat_setting()
        mock_chat_settings_repo.get.return_value = setting
        mock_chat_settings_repo.get_webhook_config_raw.return_value = {"url": "https://example.com"}

        task_result = make_task_result(task_id=1, status="pending", from_cache=False, is_new=True)
        mock_summary_usecase.get_or_create_task.return_value = Success(task_result)

        result = await summary_webhook_service.generate_and_send_webhook(
            chat_id=42, period_minutes=60,
        )

        assert result.from_cache is False
        assert result.webhook_sent is False
        assert result.webhook_pending is True

    async def test_from_cache_success(
        self, summary_webhook_service: SummaryWebhookService,
        mock_chat_settings_repo: AsyncMock,
        mock_webhook_service: AsyncMock,
        mock_summary_usecase: AsyncMock,
        mock_db_pool: MagicMock,
    ) -> None:
        """Отправка webhook из кэша успешна."""
        setting = make_chat_setting()
        mock_chat_settings_repo.get.return_value = setting
        mock_chat_settings_repo.get_webhook_config_raw.return_value = {"url": "https://example.com"}

        task_result = make_task_result(task_id=1, status="completed", from_cache=True, is_new=False)
        mock_summary_usecase.get_or_create_task.return_value = Success(task_result)

        completed_summary = make_chat_summary(status="completed", result_text="Done")
        mock_conn = AsyncMock()
        mock_conn.get_summary_task = AsyncMock(return_value=completed_summary)
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_db_pool.acquire = MagicMock(return_value=mock_cm)
        summary_webhook_service._summary_repo = AsyncMock()
        summary_webhook_service._summary_repo.get_summary_task = AsyncMock(return_value=completed_summary)

        mock_webhook_service.send_summary_webhook.return_value = True

        result = await summary_webhook_service.generate_and_send_webhook(
            chat_id=42, period_minutes=60,
        )

        assert result.from_cache is True
        assert result.webhook_sent is True
        assert result.webhook_pending is False
        mock_webhook_service.send_summary_webhook.assert_awaited_once()

    async def test_from_cache_network_error(
        self, summary_webhook_service: SummaryWebhookService,
        mock_chat_settings_repo: AsyncMock,
        mock_webhook_service: AsyncMock,
        mock_summary_usecase: AsyncMock,
        mock_db_pool: MagicMock,
    ) -> None:
        """Сетевая ошибка при отправке webhook из кэша."""
        setting = make_chat_setting()
        mock_chat_settings_repo.get.return_value = setting
        mock_chat_settings_repo.get_webhook_config_raw.return_value = {"url": "https://example.com"}

        task_result = make_task_result(task_id=1, status="completed", from_cache=True, is_new=False)
        mock_summary_usecase.get_or_create_task.return_value = Success(task_result)

        completed_summary = make_chat_summary(status="completed", result_text="Done")
        summary_webhook_service._summary_repo = AsyncMock()
        summary_webhook_service._summary_repo.get_summary_task = AsyncMock(return_value=completed_summary)

        mock_webhook_service.send_summary_webhook.side_effect = aiohttp.ClientError("Connection refused")

        result = await summary_webhook_service.generate_and_send_webhook(
            chat_id=42, period_minutes=60,
        )

        assert result.from_cache is True
        assert result.webhook_sent is False

    async def test_from_cache_timeout_error(
        self, summary_webhook_service: SummaryWebhookService,
        mock_chat_settings_repo: AsyncMock,
        mock_webhook_service: AsyncMock,
        mock_summary_usecase: AsyncMock,
    ) -> None:
        """TimeoutError при отправке webhook из кэша."""
        setting = make_chat_setting()
        mock_chat_settings_repo.get.return_value = setting
        mock_chat_settings_repo.get_webhook_config_raw.return_value = {"url": "https://example.com"}

        task_result = make_task_result(task_id=1, status="completed", from_cache=True, is_new=False)
        mock_summary_usecase.get_or_create_task.return_value = Success(task_result)

        completed_summary = make_chat_summary(status="completed", result_text="Done")
        summary_webhook_service._summary_repo = AsyncMock()
        summary_webhook_service._summary_repo.get_summary_task = AsyncMock(return_value=completed_summary)

        mock_webhook_service.send_summary_webhook.side_effect = TimeoutError("Timed out")

        result = await summary_webhook_service.generate_and_send_webhook(
            chat_id=42, period_minutes=60,
        )

        assert result.from_cache is True
        assert result.webhook_sent is False

    async def test_usecase_failure_raises_webhook_generation_error(
        self, summary_webhook_service: SummaryWebhookService,
        mock_chat_settings_repo: AsyncMock,
        mock_summary_usecase: AsyncMock,
    ) -> None:
        """Ошибка UseCase → WebhookGenerationError WHK-007."""
        setting = make_chat_setting()
        mock_chat_settings_repo.get.return_value = setting
        mock_chat_settings_repo.get_webhook_config_raw.return_value = {"url": "https://example.com"}

        mock_summary_usecase.get_or_create_task.return_value = Failure(Exception("DB error"))

        with pytest.raises(WebhookGenerationError) as exc_info:
            await summary_webhook_service.generate_and_send_webhook(
                chat_id=42, period_minutes=60,
            )

        assert exc_info.value.code == "WHK-007"


class TestSendWebhookForSummary:
    """Тесты send_webhook_for_summary."""

    def _make_db_pool_with_acquire(
        self, mock_conn: AsyncMock,
    ) -> MagicMock:
        """Создаёт мок db_pool с поддержкой acquire() как async context manager."""
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_cm)
        return mock_pool

    async def test_success(
        self, summary_webhook_service: SummaryWebhookService,
        mock_chat_settings_repo: AsyncMock,
        mock_webhook_service: AsyncMock,
    ) -> None:
        """Успешная отправка webhook для summary."""
        mock_summary_repo = AsyncMock()
        summary = make_chat_summary()
        mock_summary_repo.get_summary_task.return_value = summary
        summary_webhook_service._summary_repo = mock_summary_repo

        mock_conn = AsyncMock()
        summary_webhook_service._db_pool = self._make_db_pool_with_acquire(mock_conn)

        mock_chat_settings_repo.get.return_value = make_chat_setting()
        mock_webhook_service.send_summary_webhook.return_value = True

        config = {"url": "https://example.com"}
        result = await summary_webhook_service.send_webhook_for_summary(
            task_id=1, chat_id=42, config=config,
        )

        assert result is True

    async def test_summary_not_found(
        self, summary_webhook_service: SummaryWebhookService,
    ) -> None:
        """Summary не найден → False."""
        mock_summary_repo = AsyncMock()
        mock_summary_repo.get_summary_task.return_value = None
        summary_webhook_service._summary_repo = mock_summary_repo

        mock_conn = AsyncMock()
        summary_webhook_service._db_pool = self._make_db_pool_with_acquire(mock_conn)

        result = await summary_webhook_service.send_webhook_for_summary(
            task_id=1, chat_id=42, config={},
        )

        assert result is False

    async def test_summary_no_result(
        self, summary_webhook_service: SummaryWebhookService,
    ) -> None:
        """Summary без result_text → False."""
        mock_summary_repo = AsyncMock()
        summary = make_chat_summary(result_text=None)
        mock_summary_repo.get_summary_task.return_value = summary
        summary_webhook_service._summary_repo = mock_summary_repo

        mock_conn = AsyncMock()
        summary_webhook_service._db_pool = self._make_db_pool_with_acquire(mock_conn)

        result = await summary_webhook_service.send_webhook_for_summary(
            task_id=1, chat_id=42, config={},
        )

        assert result is False

    async def test_no_repo_returns_false(
        self, summary_webhook_service: SummaryWebhookService,
    ) -> None:
        """Repository не инициализирован → False."""
        summary_webhook_service._summary_repo = None

        result = await summary_webhook_service.send_webhook_for_summary(
            task_id=1, chat_id=42, config={},
        )

        assert result is False


class TestSendWebhookAfterGeneration:
    """Тесты send_webhook_after_generation."""

    async def test_send_webhook_after_generation(
        self, summary_webhook_service: SummaryWebhookService,
    ) -> None:
        """Фоновая отправка webhook вызывает send_webhook_for_summary."""
        with patch.object(
            summary_webhook_service,
            "send_webhook_for_summary",
            new=AsyncMock(return_value=True),
        ) as mock_send:
            await summary_webhook_service.send_webhook_after_generation(
                task_id=1, chat_id=42, config={},
            )

            mock_send.assert_called_once_with(task_id=1, chat_id=42, config={})
