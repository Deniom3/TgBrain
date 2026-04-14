"""
Тесты синхронизации Ingester после logout.

Проверяют:
1. Метод reload_session() в TelegramIngester
2. Обработку неавторизованной сессии
3. Обработку отсутствующего файла сессии
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.ingestion import TelegramIngester
from src.config import Settings
from src.embeddings import EmbeddingsClient
from src.settings import TelegramAuthRepository
from src.domain.models.auth import TelegramAuth


# ==================== Фикстуры ====================

@pytest.fixture
def mock_settings():
    """Фикстура с моком настроек."""
    settings = MagicMock(spec=Settings)
    settings.tg_api_id = 12345678
    settings.tg_api_hash = "test_api_hash_1234567890123456789012"
    settings.tg_phone_number = "+79991234567"
    settings.tg_chat_enable_list = []
    settings.tg_chat_disable_list = []
    return settings


@pytest.fixture
def mock_embeddings():
    """Фикстура с моком embeddings клиента."""
    embeddings = MagicMock(spec=EmbeddingsClient)
    return embeddings


@pytest.fixture
def mock_telegram_auth_repo():
    """Фикстура с моком TelegramAuthRepository."""
    repo = MagicMock()
    repo.get = AsyncMock(return_value=None)
    repo.get_session_data = AsyncMock(return_value=None)
    repo.save_session_data_v2 = AsyncMock()
    repo.is_session_active = AsyncMock(return_value=False)
    return repo


@pytest.fixture
def mock_app_settings_repo():
    """Фикстура с моком AppSettingsRepository."""
    repo = MagicMock()
    repo.get = AsyncMock(return_value=None)
    repo.get_value = AsyncMock(return_value=None)
    repo.upsert = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def ingester(mock_settings, mock_embeddings, mock_telegram_auth_repo, mock_app_settings_repo):
    """Фикстура TelegramIngester для тестов."""
    return TelegramIngester(mock_settings, mock_embeddings, mock_telegram_auth_repo, mock_app_settings_repo)


@pytest.fixture
def mock_auth():
    """Фикстура с моком TelegramAuth."""
    auth = MagicMock(spec=TelegramAuth)
    auth.api_id = 12345678
    auth.api_hash = "test_api_hash_1234567890123456789012"
    auth.phone_number = "+79991234567"
    auth.session_name = "qr_auth_test_session"
    auth.session_data = b"test_session_data"
    return auth


# ==================== Тесты reload_session() ====================

class TestReloadSession:
    """Тесты метода reload_session()."""

    @pytest.mark.asyncio
    async def test_reload_session_no_auth_in_db(self, ingester):
        """Тест обработки отсутствия авторизации в БД."""
        # Arrange
        with patch.object(TelegramAuthRepository, 'get', return_value=None):
            # Act
            success = await ingester.reload_session()

            # Assert
            assert success is False

    @pytest.mark.asyncio
    async def test_reload_session_no_session_name(self, ingester, mock_auth):
        """Тест обработки отсутствия session_name."""
        # Arrange
        mock_auth.session_name = None
        with patch.object(TelegramAuthRepository, 'get', return_value=mock_auth):
            # Act
            success = await ingester.reload_session()

            # Assert
            assert success is False

    @pytest.mark.asyncio
    async def test_reload_session_file_not_found(self, ingester, mock_auth):
        """Тест обработки отсутствующего файла сессии."""
        # Arrange
        with patch.object(TelegramAuthRepository, 'get', return_value=mock_auth):
            with patch('os.path.exists', return_value=False):
                # Act
                success = await ingester.reload_session()

                # Assert
                assert success is False


# ==================== Тесты restart_ingester ====================

class TestRestartIngester:
    """Тесты функции restart_ingester()."""

    @pytest.mark.asyncio
    async def test_restart_ingester_already_running(self):
        """Тест что restart_ingester не перезапускает если Ingester запущен."""
        # Arrange
        mock_state = MagicMock()
        mock_ingester = AsyncMock()
        mock_ingester.is_running = MagicMock(return_value=True)
        mock_state.ingester = mock_ingester
        mock_state.embeddings = MagicMock()
        mock_state.rate_limiter = None

        from src.api.callbacks.qr_auth_callback import restart_ingester

        # Act
        await restart_ingester(mock_state)

        # Assert - IngesterRestartService.start_ingester должен быть вызван
        # start_ingester сам проверяет is_running() внутри
        assert mock_ingester.is_running.called

    @pytest.mark.asyncio
    async def test_restart_ingester_no_ingester(self, mock_settings, mock_embeddings):
        """Тест что restart_ingester создаёт новый Ingester если старый отсутствует."""
        # Arrange
        mock_state = MagicMock()
        mock_state.ingester = None
        mock_state.embeddings = mock_embeddings
        mock_state.rate_limiter = None

        mock_auth = MagicMock()
        mock_auth.session_name = "test_session"

        with patch('src.config.loader.load_settings_from_db', return_value=mock_settings):
            with patch('src.settings.telegram_auth.TelegramAuthRepository.get', return_value=mock_auth):
                with patch('src.services.ingester_restart_service.IngesterRestartService.start_ingester', new_callable=AsyncMock) as mock_start:
                    mock_start.return_value = True

                    from src.api.callbacks.qr_auth_callback import restart_ingester

                    # Act
                    await restart_ingester(mock_state)

                    # Assert - start_ingester должен быть вызван
                    mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_restart_ingester_no_auth_in_db(self, mock_settings, mock_embeddings):
        """Тест обработки отсутствия авторизации в БД."""
        # Arrange
        mock_app = MagicMock()
        mock_app.state.ingester = None
        mock_app.state.embeddings = mock_embeddings

        with patch('src.config.loader.load_settings_from_db', return_value=mock_settings):
            with patch.object(TelegramAuthRepository, 'get', return_value=None):
                # Мок start_ingester чтобы он возвращал False (не удалось запустить)
                with patch('src.services.ingester_restart_service.IngesterRestartService.start_ingester', new_callable=AsyncMock) as mock_start:
                    mock_start.return_value = False

                    from src.api.callbacks.qr_auth_callback import restart_ingester

                    # Act
                    await restart_ingester(mock_app)

                    # Assert
                    # Ingester может быть создан, но не запущен
                    # Проверяем что start_ingester был вызван
                    mock_start.assert_called_once()
