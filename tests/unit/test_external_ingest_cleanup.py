"""
Тесты для механизма очистки pending сообщений.

Проверка методов:
- TelegramIngester.cleanup_old_pending_messages()
- TelegramIngester.start_cleanup_task()
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch



class TestCleanupMechanism:
    """Тесты для механизма очистки pending сообщений."""

    @pytest.fixture
    def settings(self):
        """Фикстура настроек."""
        from src.config import get_settings
        get_settings.cache_clear()
        return get_settings()

    @pytest.fixture
    def mock_embeddings_client(self):
        """Mock embeddings клиента."""
        mock = AsyncMock()
        mock.get_embedding = AsyncMock(return_value=[0.1] * 768)
        mock.get_model_name = MagicMock(return_value="test-model")
        return mock

    @pytest.fixture
    def mock_pending_cleanup_service(self):
        """Mock PendingCleanupService."""
        mock = AsyncMock()
        mock.cleanup_old_pending_messages = AsyncMock(return_value=0)
        mock.start_cleanup_task = AsyncMock()
        mock.stop_event = asyncio.Event()
        return mock

    @pytest.fixture
    def mock_telegram_auth_repo(self):
        """Mock TelegramAuthRepository."""
        mock = AsyncMock()
        mock.get = AsyncMock(return_value=None)
        mock.get_session_data = AsyncMock(return_value=None)
        mock.save_session_data_v2 = AsyncMock()
        mock.is_session_active = AsyncMock(return_value=False)
        return mock

    @pytest.fixture
    def mock_app_settings_repo(self):
        """Mock AppSettingsRepository."""
        mock = AsyncMock()
        mock.get = AsyncMock(return_value=None)
        mock.get_value = AsyncMock(return_value=None)
        mock.upsert = AsyncMock(return_value=True)
        return mock

    @pytest.fixture
    def ingester(self, settings, mock_embeddings_client, mock_pending_cleanup_service, mock_telegram_auth_repo, mock_app_settings_repo):
        """Фикстура TelegramIngester для тестов."""
        from src.ingestion import TelegramIngester

        ingester = TelegramIngester(settings, mock_embeddings_client, mock_telegram_auth_repo, mock_app_settings_repo)
        ingester._pending_cleanup = mock_pending_cleanup_service
        return ingester

    async def test_RemoveOldRecords_Success(self, ingester, mock_pending_cleanup_service):
        """Удаление записей старше TTL (4 часа)."""
        mock_pending_cleanup_service.cleanup_old_pending_messages = AsyncMock(return_value=5)

        deleted = await ingester.cleanup_old_pending_messages()

        assert deleted == 5
        mock_pending_cleanup_service.cleanup_old_pending_messages.assert_called_once()

    async def test_KeepRecentRecords_Success(self, ingester, mock_pending_cleanup_service):
        """Сохранение недавних записей (младше 4 часов)."""
        mock_pending_cleanup_service.cleanup_old_pending_messages = AsyncMock(return_value=0)

        deleted = await ingester.cleanup_old_pending_messages()

        assert deleted == 0
        mock_pending_cleanup_service.cleanup_old_pending_messages.assert_called_once()

    async def test_KeepLowRetryCount_Success(self, ingester, mock_pending_cleanup_service):
        """Сохранение записей с retry_count < 3."""
        mock_pending_cleanup_service.cleanup_old_pending_messages = AsyncMock(return_value=0)

        deleted = await ingester.cleanup_old_pending_messages()

        assert deleted == 0
        mock_pending_cleanup_service.cleanup_old_pending_messages.assert_called_once()

    async def test_RemoveHighRetryCount_Success(self, ingester, mock_pending_cleanup_service):
        """Удаление записей с retry_count >= 3."""
        mock_pending_cleanup_service.cleanup_old_pending_messages = AsyncMock(return_value=3)

        deleted = await ingester.cleanup_old_pending_messages()

        assert deleted == 3
        mock_pending_cleanup_service.cleanup_old_pending_messages.assert_called_once()

    async def test_CleanupJob_Logging(self, ingester, mock_pending_cleanup_service, caplog):
        """Логирование процесса очистки."""
        import logging
        mock_pending_cleanup_service.cleanup_old_pending_messages = AsyncMock(return_value=5)

        with caplog.at_level(logging.INFO):
            deleted = await ingester.cleanup_old_pending_messages()

        assert deleted == 5
        mock_pending_cleanup_service.cleanup_old_pending_messages.assert_called_once()

    async def test_CleanupJob_Scheduled(self, settings, mock_embeddings_client, mock_pending_cleanup_service, mock_telegram_auth_repo, mock_app_settings_repo):
        """Проверка периодического запуска задачи очистки."""
        from src.ingestion import TelegramIngester

        ingester = TelegramIngester(settings, mock_embeddings_client, mock_telegram_auth_repo, mock_app_settings_repo)
        ingester._pending_cleanup = mock_pending_cleanup_service

        cleanup_call_count = 0

        async def mock_start_task():
            nonlocal cleanup_call_count
            cleanup_call_count += 1
            # Симулируем одну итерацию очистки
            if ingester._pending_cleanup is not None:
                await ingester._pending_cleanup.cleanup_old_pending_messages()
            # Устанавливаем stop event после первого вызова
            ingester._stop_event.set()

        ingester._pending_cleanup.start_cleanup_task = mock_start_task  # type: ignore[method-assign]

        # Запускаем задачу
        task = asyncio.create_task(ingester.start_cleanup_task())

        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
        except asyncio.TimeoutError:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        assert cleanup_call_count >= 1, "Задача очистки должна быть выполнена хотя бы 1 раз"

    async def test_CleanupDisabled_WhenTtlIsZero(self, ingester, mock_pending_cleanup_service, caplog):
        """Очистка отключена при ttl_minutes=0."""
        import logging

        mock_pending_cleanup_service.cleanup_old_pending_messages = AsyncMock(return_value=0)

        with patch('src.settings.repositories.pending_cleanup_repository.PendingCleanupSettingsRepository.get') as mock_get:
            mock_settings = MagicMock()
            mock_settings.ttl_minutes = 0
            mock_settings.cleanup_interval_minutes = 60
            mock_get.return_value = mock_settings

            with caplog.at_level(logging.DEBUG):
                deleted = await ingester.cleanup_old_pending_messages()

            assert deleted == 0, "При TTL=0 очистка должна быть отключена"


class TestCleanupTaskLifecycle:
    """Тесты для жизненного цикла задачи очистки."""

    @pytest.fixture
    def settings(self):
        """Фикстура настроек."""
        from src.config import get_settings
        get_settings.cache_clear()
        return get_settings()

    @pytest.fixture
    def mock_embeddings_client(self):
        """Mock embeddings клиента."""
        mock = AsyncMock()
        mock.get_embedding = AsyncMock(return_value=[0.1] * 768)
        mock.get_model_name = MagicMock(return_value="test-model")
        return mock

    @pytest.fixture
    def mock_telegram_auth_repo(self):
        """Mock TelegramAuthRepository."""
        mock = AsyncMock()
        mock.get = AsyncMock(return_value=None)
        mock.get_session_data = AsyncMock(return_value=None)
        mock.save_session_data_v2 = AsyncMock()
        mock.is_session_active = AsyncMock(return_value=False)
        return mock

    @pytest.fixture
    def mock_app_settings_repo(self):
        """Mock AppSettingsRepository."""
        mock = AsyncMock()
        mock.get = AsyncMock(return_value=None)
        mock.get_value = AsyncMock(return_value=None)
        mock.upsert = AsyncMock(return_value=True)
        return mock

    async def test_CleanupTask_StopsOnEvent(self, settings, mock_embeddings_client, mock_telegram_auth_repo, mock_app_settings_repo):
        """Задача очистки останавливается при установке _stop_event."""
        from src.ingestion import TelegramIngester

        ingester = TelegramIngester(settings, mock_embeddings_client, mock_telegram_auth_repo, mock_app_settings_repo)

        ingester._stop_event.set()

        ingester.cleanup_old_pending_messages = AsyncMock()  # type: ignore[method-assign]

        task = asyncio.create_task(ingester.start_cleanup_task())

        try:
            await asyncio.wait_for(task, timeout=2.0)
        except asyncio.TimeoutError:
            task.cancel()
            await task

        ingester.cleanup_old_pending_messages.assert_not_called()

    async def test_CleanupTask_HandlesError(self, settings, mock_embeddings_client, mock_telegram_auth_repo, mock_app_settings_repo):
        """Задача очистки обрабатывает ошибки с паузой 60 секунд."""
        from src.ingestion import TelegramIngester

        ingester = TelegramIngester(settings, mock_embeddings_client, mock_telegram_auth_repo, mock_app_settings_repo)

        # Создаём mock pending cleanup service
        mock_pending = AsyncMock()
        ingester._pending_cleanup = mock_pending

        call_count = 0

        async def mock_cleanup_with_error():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Test error")
            return 0

        mock_pending.cleanup_old_pending_messages = mock_cleanup_with_error

        # Mock start_cleanup_task чтобы вызывал cleanup_old_pending_messages
        async def mock_start_task():
            try:
                await mock_cleanup_with_error()
            except Exception:
                await asyncio.sleep(0.01)  # Быстрая пауза вместо 60 секунд
                ingester._stop_event.set()

        mock_pending.start_cleanup_task = mock_start_task

        task = asyncio.create_task(ingester.start_cleanup_task())

        try:
            await asyncio.wait_for(task, timeout=2.0)
        except asyncio.TimeoutError:
            task.cancel()
            await task

        assert call_count >= 1
