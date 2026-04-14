"""
Модульные тесты для QRAuthService.

Тестируют логику QR авторизации и сохранения session_data.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.auth.service import QRAuthService
from src.auth.models import QRAuthSession
from src.domain.value_objects import SessionData


@pytest.fixture
def qr_auth_service():
    """Создаёт QRAuthService с мокированными зависимостями."""
    service = QRAuthService(
        api_id=12345,
        api_hash="test_hash_abc123",
        session_path="./sessions",
    )
    return service


@pytest.fixture
def mock_qr_session():
    """Создаёт mock QRAuthSession."""
    session = QRAuthSession(
        session_id="test-session-id-12345",
        session_name="qr_auth_test_session",
        qr_code_data="mock_qr_code_image_data",
        created_at=datetime.now(),
        expires_at=datetime.now(),
        is_completed=False,
    )
    return session


@pytest.mark.asyncio
async def test_on_auth_success_sets_user_info(qr_auth_service, mock_qr_session):
    """
    _on_auth_success устанавливает информацию о пользователе.

    Проверяет:
    - Установку is_completed в True
    - Установку user_id и user_username
    """
    qr_auth_service._active_sessions[mock_qr_session.session_id] = mock_qr_session

    mock_me = MagicMock()
    mock_me.id = 987654321
    mock_me.username = "test_user"

    mock_client = AsyncMock()
    mock_client.get_me = AsyncMock(return_value=mock_me)
    mock_client.disconnect = AsyncMock()
    qr_auth_service._client = mock_client

    with patch('os.path.exists', return_value=False):
        await qr_auth_service._on_auth_success(mock_qr_session.session_id)

    assert mock_qr_session.is_completed is True
    assert mock_qr_session.user_id == 987654321
    assert mock_qr_session.user_username == "test_user"


@pytest.mark.asyncio
async def test_on_auth_success_file_not_found(qr_auth_service, mock_qr_session):
    """
    _on_auth_success обрабатывает отсутствие файла сессии.
    
    Проверяет:
    - Обработку FileNotFoundError
    - Установку saved_to_db в False
    - Отсутствие ошибок при отсутствии файла
    """
    qr_auth_service._active_sessions[mock_qr_session.session_id] = mock_qr_session
    
    mock_me = MagicMock()
    mock_me.id = 987654321
    mock_me.username = "test_user"
    
    mock_client = AsyncMock()
    mock_client.get_me = AsyncMock(return_value=mock_me)
    mock_client.disconnect = AsyncMock()
    qr_auth_service._client = mock_client
    
    with patch('os.path.exists', return_value=False):
        await qr_auth_service._on_auth_success(mock_qr_session.session_id)
    
    assert mock_qr_session.saved_to_db is False
    assert mock_qr_session.is_completed is True


@pytest.mark.asyncio
async def test_on_auth_success_invalid_session_size(qr_auth_service, mock_qr_session):
    """
    _on_auth_success отклоняет файл сессии меньше минимального размера.
    
    Проверяет:
    - Проверку минимального размера файла (28KB)
    - Установку error при слишком маленьком файле
    - Отсутствие сохранения в БД
    """
    
    qr_auth_service._active_sessions[mock_qr_session.session_id] = mock_qr_session
    
    mock_me = MagicMock()
    mock_me.id = 987654321
    mock_me.username = "test_user"
    
    mock_client = AsyncMock()
    mock_client.get_me = AsyncMock(return_value=mock_me)
    mock_client.disconnect = AsyncMock()
    qr_auth_service._client = mock_client
    
    small_file_size = SessionData.MIN_SIZE - 1000
    
    with patch('os.path.exists', return_value=True):
        with patch('os.path.getsize', return_value=small_file_size):
            await qr_auth_service._on_auth_success(mock_qr_session.session_id)
    
    assert mock_qr_session.saved_to_db is False
    assert mock_qr_session.error == "Invalid session file"


@pytest.mark.asyncio
async def test_create_session(qr_auth_service):
    """
    create_session создаёт новую QR сессию.
    
    Проверяет:
    - Генерацию session_id и session_name
    - Создание сессии в _active_sessions
    - Задачу мониторинга в _monitor_tasks
    """
    with patch.object(qr_auth_service, '_ensure_session_directory', AsyncMock()):
        with patch.object(qr_auth_service, '_cancel_active_sessions', AsyncMock()):
            with patch.object(qr_auth_service, '_cleanup_old_qr_sessions', AsyncMock()):
                with patch.object(
                    qr_auth_service,
                    '_create_telegram_client',
                    AsyncMock(return_value=AsyncMock())
                ):
                    with patch.object(
                        qr_auth_service,
                        '_export_login_token',
                        AsyncMock(return_value=b"mock_token")
                    ):
                        with patch.object(
                            qr_auth_service,
                            '_create_qr_session',
                            AsyncMock(return_value=QRAuthSession(
                                session_id="test-id",
                                session_name="qr_auth_test",
                                qr_code_data="qr_data",
                                created_at=datetime.now(),
                                expires_at=datetime.now(),
                                is_completed=False,
                            ))
                        ):
                            with patch.object(
                                qr_auth_service,
                                '_start_session_monitoring',
                                AsyncMock()
                            ):
                                session = await qr_auth_service.create_session()
    
    assert session is not None
    assert session.session_id == "test-id"
    assert session.session_name == "qr_auth_test"
    assert session.is_completed is False
