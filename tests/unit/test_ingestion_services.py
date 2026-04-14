"""
Модульные тесты для IngestionServices.

Тестируют координатор сервисов ingestion:
- Инициализация с пулом и без
- Запуск и остановка мониторинга
- Синхронизация чатов
- Применение настроек
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import Settings
from src.embeddings import EmbeddingsClient
from src.ingestion.services import IngestionServices
from src.settings.repositories.telegram_auth import TelegramAuthRepository


@pytest.fixture
def mock_settings():
    """Создаёт mock Settings для тестов."""
    settings = MagicMock(spec=Settings)
    settings.tg_api_id = 12345
    settings.tg_api_hash = "test_hash_abc123"
    settings.tg_chat_enable_list = []
    settings.tg_chat_disable_list = []
    return settings


@pytest.fixture
def mock_embeddings():
    """Создаёт mock EmbeddingsClient."""
    embeddings = MagicMock(spec=EmbeddingsClient)
    embeddings.get_embedding = AsyncMock(return_value=[0.1] * 768)
    embeddings.close = AsyncMock()
    embeddings.get_model_name = MagicMock(return_value="nomic-embed-text")
    return embeddings


@pytest.fixture
def mock_telegram_auth_repo():
    """Создаёт mock TelegramAuthRepository."""
    repo = MagicMock(spec=TelegramAuthRepository)
    repo.get = AsyncMock(return_value=None)
    repo.get_session_data = AsyncMock(return_value=None)
    repo.save_session_data_v2 = AsyncMock()
    repo.is_session_active = AsyncMock(return_value=False)
    return repo


@pytest.fixture
def mock_app_settings_repo():
    """Создаёт mock AppSettingsRepository."""
    repo = AsyncMock()
    repo.get = AsyncMock(return_value=None)
    repo.get_value = AsyncMock(return_value=None)
    repo.upsert = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def mock_pool():
    """Создаёт mock asyncpg.Pool."""
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=None)
    pool.execute = AsyncMock()
    return pool


@pytest.fixture
def ingestion_services(
    mock_settings,
    mock_embeddings,
    mock_telegram_auth_repo,
    mock_app_settings_repo,
):
    """Создаёт IngestionServices с мокированными зависимостями."""
    services = IngestionServices(
        config=mock_settings,
        embeddings=mock_embeddings,
        telegram_auth_repo=mock_telegram_auth_repo,
        app_settings_repo=mock_app_settings_repo,
    )
    return services


class TestIngestionServicesInit:
    """Тесты инициализации IngestionServices."""

    def test_ingestion_services_init(self, ingestion_services, mock_settings, mock_embeddings):
        """
        IngestionServices корректно инициализируется.

        Проверяет:
        - Сохранение config и embeddings
        - Создание session_manager и ingester
        - saver равен None до инициализации
        """
        assert ingestion_services.config == mock_settings
        assert ingestion_services.embeddings == mock_embeddings
        assert ingestion_services.saver is None
        assert ingestion_services.session_manager is not None
        assert ingestion_services.ingester is not None


class TestInitialize:
    """Тесты метода initialize."""

    @pytest.mark.asyncio
    async def test_initialize_with_pool(self, mock_settings, mock_embeddings, mock_telegram_auth_repo, mock_app_settings_repo, mock_pool):
        """
        Инициализация с переданным пулом.

        Проверяет:
        - Создание MessageSaver с переданным пулом
        - saver не равен None после инициализации
        """
        services = IngestionServices(
            config=mock_settings,
            embeddings=mock_embeddings,
            telegram_auth_repo=mock_telegram_auth_repo,
            app_settings_repo=mock_app_settings_repo,
            pool=mock_pool,
        )

        await services.initialize()

        assert services.saver is not None

    @pytest.mark.asyncio
    async def test_initialize_without_pool(self, ingestion_services, mock_pool):
        """
        Инициализация без пула (получает из get_pool).

        Проверяет:
        - Вызов get_pool для получения пула
        - Создание MessageSaver
        """
        with patch("src.database.get_pool", new_callable=AsyncMock) as mock_get_pool:
            mock_get_pool.return_value = mock_pool

            await ingestion_services.initialize()

        mock_get_pool.assert_called_once()
        assert ingestion_services.saver is not None


class TestStartMonitoring:
    """Тесты метода start_monitoring."""

    @pytest.mark.asyncio
    async def test_start_monitoring(self, ingestion_services, mock_pool):
        """
        Запуск мониторинга чатов.

        Проверяет:
        - Инициализация saver если не инициализирован
        - Вызов ingester.initialize_monitored_chats
        """
        with patch("src.database.get_pool", new_callable=AsyncMock) as mock_get_pool:
            mock_get_pool.return_value = mock_pool

            with patch.object(
                ingestion_services.ingester,
                "initialize_monitored_chats",
                new_callable=AsyncMock,
            ) as mock_init:
                await ingestion_services.start_monitoring([-1001234567890])

            mock_init.assert_called_once_with([-1001234567890])

    @pytest.mark.asyncio
    async def test_start_monitoring_no_saver(self, ingestion_services):
        """
        Запуск без инициализации saver.

        Проверяет:
        - Автоматическая инициализация saver
        """
        assert ingestion_services.saver is None

        with patch.object(
            ingestion_services,
            "initialize",
            new_callable=AsyncMock,
        ) as mock_init:
            with patch.object(
                ingestion_services.ingester,
                "initialize_monitored_chats",
                new_callable=AsyncMock,
            ):
                await ingestion_services.start_monitoring([-1001234567890])

        mock_init.assert_called_once()


class TestStopMonitoring:
    """Тесты метода stop_monitoring."""

    @pytest.mark.asyncio
    async def test_stop_monitoring(self, ingestion_services):
        """
        Остановка мониторинга.

        Проверяет:
        - Вызов ingester.stop
        - Вызов pending_cleanup.stop
        """
        with patch.object(
            ingestion_services.ingester,
            "stop",
            new_callable=AsyncMock,
        ) as mock_stop_ingester:
            with patch.object(
                ingestion_services.pending_cleanup,
                "stop",
            ) as mock_stop_cleanup:
                await ingestion_services.stop_monitoring()

            mock_stop_ingester.assert_called_once()
            mock_stop_cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_monitoring_no_ingester(self, ingestion_services):
        """
        Остановка мониторинга когда ingester отсутствует.

        Проверяет:
        - pending_cleanup.stop вызван
        - ingester не вызывается (None)
        - Ошибок не возникает
        """
        ingestion_services.ingester = None

        with patch.object(
            ingestion_services.pending_cleanup,
            "stop",
        ) as mock_stop_cleanup:
            await ingestion_services.stop_monitoring()

            mock_stop_cleanup.assert_called_once()


class TestGetMonitoredChats:
    """Тесты метода get_monitored_chats."""

    @pytest.mark.asyncio
    async def test_get_monitored_chats(self, ingestion_services, mock_pool):
        """
        Получение списка чатов.

        Проверяет:
        - Вызов ChatSettingsRepository.get_monitored_chat_ids
        """
        mock_repo = AsyncMock()
        mock_repo.get_monitored_chat_ids = AsyncMock(return_value=[-1001234567890, -1009876543210])

        with patch("src.database.get_pool", new_callable=AsyncMock) as mock_get_pool:
            mock_get_pool.return_value = mock_pool

            with patch("src.settings.repositories.chat_settings.ChatSettingsRepository", return_value=mock_repo):
                result = await ingestion_services.get_monitored_chats()

        assert result == [-1001234567890, -1009876543210]


class TestSyncChats:
    """Тесты метода sync_chats."""

    @pytest.mark.asyncio
    async def test_sync_chats(self, ingestion_services, mock_pool):
        """
        Синхронизация чатов с Telegram.

        Проверяет:
        - Создание ChatSyncService
        - Вызов sync_chats_with_telegram
        """
        mock_client = AsyncMock()
        sync_result = {"created": 5, "updated": 3, "unchanged": 10}

        mock_sync_service = AsyncMock()
        mock_sync_service.sync_chats_with_telegram = AsyncMock(return_value=sync_result)

        with patch("src.ingestion.services.ChatSyncService", return_value=mock_sync_service):
            ingestion_services._pool = mock_pool
            result = await ingestion_services.sync_chats(mock_client, limit=50)

        mock_sync_service.sync_chats_with_telegram.assert_called_once()
        assert result == sync_result


class TestApplyEnvSettings:
    """Тесты метода apply_env_settings."""

    @pytest.mark.asyncio
    async def test_apply_env_settings(self, ingestion_services, mock_pool, mock_settings):
        """
        Применение настроек из .env.

        Проверяет:
        - Создание ChatSyncService
        - Вызов apply_env_initialization
        """
        mock_settings.tg_chat_enable_list = [-1001234567890]
        mock_settings.tg_chat_disable_list = [-1009876543210]

        mock_sync_service = AsyncMock()
        mock_sync_service.apply_env_initialization = AsyncMock(return_value={"enabled": 1, "disabled": 1})

        with patch("src.ingestion.services.ChatSyncService", return_value=mock_sync_service):
            ingestion_services._pool = mock_pool
            result = await ingestion_services.apply_env_settings()

        mock_sync_service.apply_env_initialization.assert_called_once_with(
            [-1001234567890],
            [-1009876543210],
        )
        assert result == {"enabled": 1, "disabled": 1}


class TestGetStats:
    """Тесты метода get_stats."""

    def test_get_stats(self, ingestion_services):
        """
        Получение статистики.

        Проверяет:
        - Вызов ingester.get_stats
        """
        expected_stats = {"processed": 42, "filtered": 10, "errors": 3}

        with patch.object(
            ingestion_services.ingester,
            "get_stats",
            return_value=expected_stats,
        ):
            result = ingestion_services.get_stats()

        assert result == expected_stats

    def test_get_stats_no_ingester(self, ingestion_services):
        """
        Статистика без ingester.

        Проверяет:
        - Возврат пустого dict при ingester=None
        """
        ingestion_services.ingester = None

        result = ingestion_services.get_stats()

        assert result == {}
