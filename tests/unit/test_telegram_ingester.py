"""
Модульные тесты для TelegramIngester.

Тестируют публичные методы и новую архитектуру.
"""

import os
import pytest
import tempfile
from unittest.mock import AsyncMock, MagicMock

from src.config import Settings
from src.embeddings import EmbeddingsClient
from src.ingestion import TelegramIngester


@pytest.fixture
def mock_telegram_auth_repo():
    """Создаёт mock TelegramAuthRepository."""
    repo = MagicMock()
    repo.get = AsyncMock(return_value=None)
    repo.get_session_data = AsyncMock(return_value=None)
    repo.save_session_data_v2 = AsyncMock()
    repo.is_session_active = AsyncMock(return_value=False)
    return repo


@pytest.fixture
def mock_app_settings_repo():
    """Создаёт mock AppSettingsRepository."""
    repo = MagicMock()
    repo.get = AsyncMock(return_value=None)
    repo.get_value = AsyncMock(return_value=None)
    repo.upsert = AsyncMock(return_value=True)
    return repo


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
def mock_embeddings_client():
    """Создаёт mock EmbeddingsClient."""
    embeddings = MagicMock(spec=EmbeddingsClient)
    embeddings.get_embedding = AsyncMock(return_value=[0.1] * 768)
    embeddings.close = AsyncMock()
    return embeddings


@pytest.fixture
def mock_temp_file():
    """Создаёт временный файл для тестов."""
    fd, temp_path = tempfile.mkstemp(suffix=".session")
    os.close(fd)

    yield temp_path

    if os.path.exists(temp_path):
        os.remove(temp_path)


@pytest.mark.asyncio
async def test_is_running_initial_state(
    mock_settings,
    mock_embeddings_client,
    mock_telegram_auth_repo,
    mock_app_settings_repo,
):
    """
    is_running() возвращает False для не запущенного Ingester.

    Проверяет:
    - Начальное состояние _running = False
    - Публичный метод is_running() корректно возвращает состояние
    """
    ingester = TelegramIngester(
        mock_settings, mock_embeddings_client, mock_telegram_auth_repo, mock_app_settings_repo
    )

    # Проверка начального состояния
    assert ingester.is_running() is False


@pytest.mark.asyncio
async def test_is_running_after_start(
    mock_settings,
    mock_embeddings_client,
    mock_telegram_auth_repo,
    mock_app_settings_repo,
):
    """
    is_running() возвращает True после запуска.

    Проверяет:
    - Изменение состояния после start()
    - Публичный метод is_running() корректно возвращает состояние
    """
    ingester = TelegramIngester(
        mock_settings, mock_embeddings_client, mock_telegram_auth_repo, mock_app_settings_repo
    )

    # Устанавливаем _running вручную (симуляция запуска)
    ingester._running = True

    # Проверка состояния
    assert ingester.is_running() is True


@pytest.mark.asyncio
async def test_stop_cleanup_task_none(
    mock_settings,
    mock_embeddings_client,
    mock_telegram_auth_repo,
    mock_app_settings_repo,
):
    """
    stop_cleanup_task() корректно обрабатывает отсутствие задачи.

    Проверяет:
    - Отсутствие ошибок при _cleanup_task = None
    - Метод завершается без исключений
    """
    ingester = TelegramIngester(
        mock_settings, mock_embeddings_client, mock_telegram_auth_repo, mock_app_settings_repo
    )
    ingester._cleanup_task = None

    # Не должно быть исключений
    await ingester.stop_cleanup_task()


@pytest.mark.asyncio
async def test_stop_cleanup_task_cancels_task(
    mock_settings,
    mock_embeddings_client,
    mock_telegram_auth_repo,
    mock_app_settings_repo,
):
    """
    stop_cleanup_task() отменяет задачу очистки.

    Проверяет:
    - Отмена задачи через cancel()
    - Ожидание завершения задачи
    - Очистка _cleanup_task в None
    """
    ingester = TelegramIngester(
        mock_settings, mock_embeddings_client, mock_telegram_auth_repo, mock_app_settings_repo
    )

    # Создаём mock задачи
    mock_task = AsyncMock()
    mock_task.cancel = MagicMock()
    ingester._cleanup_task = mock_task

    # Вызов метода
    await ingester.stop_cleanup_task()

    # Проверки
    mock_task.cancel.assert_called_once()
    assert ingester._cleanup_task is None


@pytest.mark.asyncio
async def test_stop_cleanup_task_handles_exception(
    mock_settings,
    mock_embeddings_client,
    mock_telegram_auth_repo,
    mock_app_settings_repo,
):
    """
    stop_cleanup_task() обрабатывает исключения при отмене.

    Проверяет:
    - Обработку исключений отличных от CancelledError
    - Логирование ошибок
    - Очистка _cleanup_task в None
    """
    ingester = TelegramIngester(
        mock_settings, mock_embeddings_client, mock_telegram_auth_repo, mock_app_settings_repo
    )

    # Создаём mock задачи с исключением
    mock_task = AsyncMock()
    mock_task.cancel = MagicMock()
    mock_task.__await__ = MagicMock(side_effect=Exception("Test error"))
    ingester._cleanup_task = mock_task

    # Не должно быть исключений
    await ingester.stop_cleanup_task()

    # Проверка что задача очищена
    assert ingester._cleanup_task is None


@pytest.mark.asyncio
async def test_message_handler_deduplication(
    mock_settings,
    mock_embeddings_client,
    mock_telegram_auth_repo,
    mock_app_settings_repo,
):
    """
    _register_event_handler() удаляет старый обработчик перед регистрацией.

    Проверяет:
    - Сохранение ссылки на обработчик в _message_handler
    - Удаление старого обработчика при повторной регистрации
    """
    ingester = TelegramIngester(
        mock_settings, mock_embeddings_client, mock_telegram_auth_repo, mock_app_settings_repo
    )

    # Mock session lifecycle и клиента
    mock_client = AsyncMock()
    mock_client.on = MagicMock()
    mock_client.remove_event_handler = MagicMock()

    mock_lifecycle = AsyncMock()
    mock_lifecycle.get_client = MagicMock(return_value=mock_client)
    mock_lifecycle.is_connected = MagicMock(return_value=True)

    ingester._session_lifecycle = mock_lifecycle
    ingester._message_processor = AsyncMock()

    # Первая регистрация
    ingester._register_event_handler()
    first_handler = ingester._message_handler

    # Проверка что обработчик сохранён
    assert first_handler is not None
    mock_client.remove_event_handler.assert_not_called()

    # Вторая регистрация (должна удалить старый обработчик)
    ingester._register_event_handler()

    # Проверка что старый обработчик удалён
    mock_client.remove_event_handler.assert_called_once_with(first_handler)
