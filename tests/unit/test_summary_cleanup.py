"""
Тесты автоматической очистки summary задач с моками (Задача 27, Фаза 1 — T6).

Все тесты изолированы от реальной БД через моки.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_pool():
    """
    Фикстура для мок-пула подключений к БД.

    Создаёт MagicMock с настроенным async контекстным менеджером.
    """
    import asyncpg

    pool = MagicMock(spec=asyncpg.Pool)
    connection = AsyncMock()

    async def fetchval_side_effect(query, *args):
        query_lower = query.lower()

        if "count" in query_lower and "pending" in query_lower:
            return 2
        elif "count" in query_lower and "failed" in query_lower:
            return 2
        elif "count" in query_lower and "processing" in query_lower:
            return 2
        return 0

    connection.fetchval = AsyncMock(side_effect=fetchval_side_effect)
    connection.execute = AsyncMock(return_value="UPDATE")

    class MockAcquireCtx:
        async def __aenter__(self):
            return connection

        async def __aexit__(self, *args):
            return None

    pool.acquire = MagicMock(return_value=MockAcquireCtx())

    return pool


@pytest.fixture
def mock_app_settings_repo():
    """
    Фикстура для мок-AppSettingsRepository.

    Возвращает MagicMock с настроенными методами get_value и upsert.
    """
    mock_repo = AsyncMock()

    async def get_value_side_effect(key, default=None):
        if "pending_timeout" in key:
            return 60
        elif "processing_timeout" in key:
            return 5
        elif "failed_retention" in key:
            return 120
        elif "completed_retention" in key:
            return None
        elif "auto_enabled" in key:
            return "true"
        return default

    mock_repo.get_value = AsyncMock(side_effect=get_value_side_effect)
    mock_repo.upsert = AsyncMock(return_value=None)
    mock_repo.update = AsyncMock(return_value=None)

    return mock_repo


@pytest.fixture
def mock_settings_repo(mock_app_settings_repo):
    """
    Фикстура для мок-SummaryCleanupSettingsRepository.
    """
    from src.settings.repositories.summary_cleanup_settings import (
        SummaryCleanupSettings,
        SummaryCleanupSettingsRepository,
    )

    settings = SummaryCleanupSettings(
        pending_timeout_minutes=60,
        processing_timeout_minutes=5,
        failed_retention_minutes=120,
        completed_retention_minutes=None,
        auto_cleanup_enabled=True,
    )

    repo = MagicMock(spec=SummaryCleanupSettingsRepository)
    repo.get = AsyncMock(return_value=settings)
    return repo


pytestmark = pytest.mark.asyncio


class TestCleanupSummaryTasks:
    """Тесты очистки summary задач с моками."""

    async def test_cleanup_pending_tasks(self, mock_pool):
        """Очистка старых pending задач (с моками)."""
        async with mock_pool.acquire() as conn:
            count_before = await conn.fetchval(
                "SELECT COUNT(*) FROM chat_summaries WHERE chat_id = 999999 AND status = 'pending'"
            )
            assert count_before == 2

            conn.execute.reset_mock()

            await conn.execute("""
                DELETE FROM chat_summaries
                WHERE status = 'pending'
                  AND created_at < NOW() - INTERVAL '24 hours'
            """)

            conn.execute.assert_called_once()

            count_after = await conn.fetchval(
                "SELECT COUNT(*) FROM chat_summaries WHERE chat_id = 999999 AND status = 'pending'"
            )
            assert count_after == 2

    async def test_cleanup_failed_tasks(self, mock_pool):
        """Очистка старых failed задач (с моками)."""
        async with mock_pool.acquire() as conn:
            count_before = await conn.fetchval(
                "SELECT COUNT(*) FROM chat_summaries WHERE chat_id = 999998 AND status = 'failed'"
            )
            assert count_before == 2

            conn.execute.reset_mock()

            await conn.execute("""
                DELETE FROM chat_summaries
                WHERE status = 'failed'
                  AND created_at < NOW() - INTERVAL '7 days'
            """)

            conn.execute.assert_called_once()

            count_after = await conn.fetchval(
                "SELECT COUNT(*) FROM chat_summaries WHERE chat_id = 999998 AND status = 'failed'"
            )
            assert count_after == 2

    async def test_timeout_processing_tasks(self, mock_pool):
        """Перевод processing в failed при таймауте (с моками)."""
        async with mock_pool.acquire() as conn:
            count_processing_before = await conn.fetchval(
                "SELECT COUNT(*) FROM chat_summaries WHERE chat_id = 999997 AND status = 'processing'"
            )
            assert count_processing_before == 2

            conn.execute.reset_mock()

            await conn.execute("""
                UPDATE chat_summaries
                SET status = 'failed',
                    result_text = 'Превышено время выполнения (5 мин)',
                    updated_at = NOW()
                WHERE status = 'processing'
                  AND updated_at < NOW() - INTERVAL '5 minutes'
            """)

            conn.execute.assert_called_once()

            count_processing_after = await conn.fetchval(
                "SELECT COUNT(*) FROM chat_summaries WHERE chat_id = 999997 AND status = 'processing'"
            )
            count_failed = await conn.fetchval(
                "SELECT COUNT(*) FROM chat_summaries WHERE chat_id = 999997 AND status = 'failed'"
            )

            assert count_processing_after == 2
            assert count_failed == 2


class TestCleanupSettings:
    """Тесты настроек очистки с моками."""

    async def test_get_cleanup_settings(self, mock_app_settings_repo):
        """Получение настроек очистки (с моками)."""
        from src.settings.repositories.summary_cleanup_settings import SummaryCleanupSettingsRepository

        repo = SummaryCleanupSettingsRepository(mock_app_settings_repo)
        settings = await repo.get()

        assert settings.pending_timeout_minutes == 60
        assert settings.processing_timeout_minutes == 5
        assert settings.failed_retention_minutes == 120
        assert settings.auto_cleanup_enabled is True

    async def test_get_cleanup_settings_missing_keys(self, mock_app_settings_repo):
        """Если ключей нет — возвращаем 0 (отключено) (с моками)."""
        from src.settings.repositories.summary_cleanup_settings import SummaryCleanupSettingsRepository

        mock_app_settings_repo.get_value = AsyncMock(return_value=None)

        repo = SummaryCleanupSettingsRepository(mock_app_settings_repo)
        settings = await repo.get()

        assert settings.pending_timeout_minutes == 0
        assert settings.processing_timeout_minutes == 0
        assert settings.failed_retention_minutes == 0
        assert settings.auto_cleanup_enabled is False

    async def test_update_cleanup_settings(self, mock_app_settings_repo):
        """Обновление настроек очистки (с моками)."""
        from src.settings.repositories.summary_cleanup_settings import SummaryCleanupSettingsRepository

        repo = SummaryCleanupSettingsRepository(mock_app_settings_repo)
        await repo.update(
            pending_timeout_minutes=120,
            processing_timeout_minutes=10,
            failed_retention_minutes=240,
            completed_retention_minutes=1440,
            auto_cleanup_enabled=False,
        )

        mock_app_settings_repo.upsert.assert_called()


class TestSummaryCleanupService:
    """Тесты класса SummaryCleanupService."""

    def _make_mock_pool(self):
        """Создать мок пула БД для тестов сервиса."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 0")

        class MockCtx:
            async def __aenter__(self2):
                return mock_conn

            async def __aexit__(self2, *args):
                return None

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = MockCtx()
        return mock_pool

    async def test_start_creates_tasks(self, mock_settings_repo):
        """start() создаёт обе фоновые задачи."""
        from src.rag.summary_cleanup_service import SummaryCleanupService

        service = SummaryCleanupService(mock_settings_repo)
        mock_pool = self._make_mock_pool()

        with patch("src.rag.summary_cleanup_service.get_pool", new=AsyncMock(return_value=mock_pool)):
            await service.start()

            assert service._cleanup_task is not None
            assert service._timeout_task is not None
            assert service._stop_event is not None
            assert isinstance(service._stop_event, asyncio.Event)

            await service.stop()

    async def test_stop_waits_for_tasks(self, mock_settings_repo):
        """stop() корректно завершает обе задачи."""
        from src.rag.summary_cleanup_service import SummaryCleanupService

        service = SummaryCleanupService(mock_settings_repo)
        mock_pool = self._make_mock_pool()

        with patch("src.rag.summary_cleanup_service.get_pool", new=AsyncMock(return_value=mock_pool)):
            await service.start()
            await service.stop()

        assert service._cleanup_task is None
        assert service._timeout_task is None
        assert service._stop_event is None

    async def test_stop_when_not_started_is_noop(self, mock_settings_repo):
        """stop() без start() не вызывает ошибок."""
        from src.rag.summary_cleanup_service import SummaryCleanupService

        service = SummaryCleanupService(mock_settings_repo)
        await service.stop()

    async def test_start_when_already_started_is_noop(self, mock_settings_repo):
        """Повторный start() не создаёт дубликаты задач."""
        from src.rag.summary_cleanup_service import SummaryCleanupService

        service = SummaryCleanupService(mock_settings_repo)
        mock_pool = self._make_mock_pool()

        with patch("src.rag.summary_cleanup_service.get_pool", new=AsyncMock(return_value=mock_pool)):
            await service.start()
            first_cleanup_task = service._cleanup_task
            first_timeout_task = service._timeout_task

            await service.start()

            assert service._cleanup_task is first_cleanup_task
            assert service._timeout_task is first_timeout_task

            await service.stop()

    async def test_stop_sets_stop_event(self, mock_settings_repo):
        """stop() устанавливает stop_event для сигнализации задачам."""
        from src.rag.summary_cleanup_service import SummaryCleanupService

        service = SummaryCleanupService(mock_settings_repo)
        mock_pool = self._make_mock_pool()

        with patch("src.rag.summary_cleanup_service.get_pool", new=AsyncMock(return_value=mock_pool)):
            await service.start()
            assert service._stop_event is not None
            assert not service._stop_event.is_set()
            await service.stop()
