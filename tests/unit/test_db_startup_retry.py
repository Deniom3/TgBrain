"""
Тесты retry-логики подключения к БД при старте.

Все тесты изолированы от реальной БД через моки.
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest

from src.database import (
    DB_STARTUP_MAX_RETRIES,
    DB_STARTUP_RETRY_DELAY_SECONDS,
    DatabaseConnectionError,
    _create_pool_with_retry,
    get_pool,
)


@pytest.fixture(autouse=True)
def _reset_pool_state() -> None:
    """Сбросить состояние глобального пула перед каждым тестом."""
    import src.database as db_module

    db_module._pool = None


def _make_settings(host: str = "localhost", port: int = 5432) -> MagicMock:
    """Создать мок настроек БД."""
    settings = MagicMock()
    settings.db_host = host
    settings.db_port = port
    settings.db_name = "tg_db"
    settings.db_user = "postgres"
    settings.db_password = "secret"
    return settings


def _make_mock_pool() -> MagicMock:
    """Создать мок пула подключений."""
    pool = MagicMock(spec=asyncpg.Pool)
    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock()
    acquire_ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_ctx)
    return pool


@pytest.mark.asyncio
async def test_get_pool_succeeds_on_first_attempt() -> None:
    """get_pool успешно подключается с первой попытки."""
    mock_pool = _make_mock_pool()

    with patch("src.database.asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool) as mock_create:
        pool = await get_pool()

        assert pool is mock_pool
        mock_create.assert_called_once()


@pytest.mark.asyncio
async def test_create_pool_with_retry_succeeds_on_first_attempt(caplog: pytest.LogCaptureFixture) -> None:
    """_create_pool_with_retry успешно подключается с первой попытки."""
    settings = _make_settings()
    mock_pool = _make_mock_pool()

    with caplog.at_level(logging.INFO, logger="src.database"):
        with patch("src.database.asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool):
            result = await _create_pool_with_retry(settings)

    assert result is mock_pool

    log_messages = [record.message for record in caplog.records]
    assert any("Попытка подключения к БД 1/5" in msg for msg in log_messages)


@pytest.mark.asyncio
async def test_create_pool_with_retry_succeeds_on_third_attempt(caplog: pytest.LogCaptureFixture) -> None:
    """_create_pool_with_retry подключается с третьей попытки после двух неудач."""
    settings = _make_settings()
    mock_pool = _make_mock_pool()

    call_count = 0

    async def create_pool_side_effect(**kwargs: object) -> MagicMock:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionRefusedError("Connection refused")
        return mock_pool

    with caplog.at_level(logging.INFO, logger="src.database"):
        with patch("src.database.asyncpg.create_pool", side_effect=create_pool_side_effect):
            with patch("src.database.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                result = await _create_pool_with_retry(settings)

    assert result is mock_pool
    assert call_count == 3
    assert mock_sleep.call_count == 2

    log_messages = [record.message for record in caplog.records]
    assert any("Попытка 1/5 не удалась" in msg for msg in log_messages)
    assert any("Попытка 2/5 не удалась" in msg for msg in log_messages)
    assert any("Подключение к БД установлено с попытки 3" in msg for msg in log_messages)


@pytest.mark.asyncio
async def test_create_pool_with_retry_fails_after_all_attempts(caplog: pytest.LogCaptureFixture) -> None:
    """_create_pool_with_retry выбрасывает DatabaseConnectionError после всех попыток."""
    settings = _make_settings(host="db.example.com", port=5433)

    async def create_pool_side_effect(**kwargs: object) -> None:
        raise ConnectionRefusedError("Connection refused")

    with patch("src.database.asyncpg.create_pool", side_effect=create_pool_side_effect):
        with patch("src.database.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(DatabaseConnectionError) as exc_info:
                await _create_pool_with_retry(settings)

    error = exc_info.value
    assert error.host == "db.example.com"
    assert error.port == 5433
    assert error.max_retries == DB_STARTUP_MAX_RETRIES
    assert "db.example.com:5433" in str(error)
    assert "после 5 попыток" in str(error)
    assert mock_sleep.call_count == DB_STARTUP_MAX_RETRIES - 1

    log_messages = [record.message for record in caplog.records]
    for attempt_num in range(1, DB_STARTUP_MAX_RETRIES + 1):
        assert any(f"Попытка {attempt_num}/{DB_STARTUP_MAX_RETRIES} не удалась" in msg for msg in log_messages)


@pytest.mark.asyncio
async def test_create_pool_with_retry_catches_os_error() -> None:
    """_create_pool_with_retry перехватывает OSError."""
    settings = _make_settings()

    async def create_pool_side_effect(**kwargs: object) -> None:
        raise OSError("Network is unreachable")

    with patch("src.database.asyncpg.create_pool", side_effect=create_pool_side_effect):
        with patch("src.database.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(DatabaseConnectionError):
                await _create_pool_with_retry(settings)


@pytest.mark.asyncio
async def test_create_pool_with_retry_catches_asyncpg_postgres_error() -> None:
    """_create_pool_with_retry перехватывает asyncpg.PostgresError."""
    settings = _make_settings()

    async def create_pool_side_effect(**kwargs: object) -> None:
        raise asyncpg.PostgresError("Cannot connect now")

    with patch("src.database.asyncpg.create_pool", side_effect=create_pool_side_effect):
        with patch("src.database.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(DatabaseConnectionError):
                await _create_pool_with_retry(settings)


@pytest.mark.asyncio
async def test_create_pool_with_retry_catches_asyncpg_interface_error() -> None:
    """_create_pool_with_retry перехватывает asyncpg.InterfaceError."""
    settings = _make_settings()

    async def create_pool_side_effect(**kwargs: object) -> None:
        raise asyncpg.InterfaceError("Interface error")

    with patch("src.database.asyncpg.create_pool", side_effect=create_pool_side_effect):
        with patch("src.database.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(DatabaseConnectionError):
                await _create_pool_with_retry(settings)


@pytest.mark.asyncio
async def test_create_pool_with_retry_uses_correct_delay() -> None:
    """_create_pool_with_retry использует фиксированный интервал между попытками."""
    settings = _make_settings()
    call_count = 0

    async def create_pool_side_effect(**kwargs: object) -> MagicMock:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionRefusedError("Connection refused")
        return _make_mock_pool()

    with patch("src.database.asyncpg.create_pool", side_effect=create_pool_side_effect):
        with patch("src.database.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await _create_pool_with_retry(settings)

    for call in mock_sleep.call_args_list:
        assert call[0][0] == DB_STARTUP_RETRY_DELAY_SECONDS


@pytest.mark.asyncio
async def test_database_connection_error_stores_last_error() -> None:
    """DatabaseConnectionError сохраняет последнее исключение."""
    original_error = ConnectionRefusedError("Test error")

    error = DatabaseConnectionError(
        host="localhost",
        port=5432,
        max_retries=5,
        last_error=original_error,
    )

    assert error.last_error is original_error
    assert isinstance(error.last_error, ConnectionRefusedError)


@pytest.mark.asyncio
async def test_get_pool_uses_retry_logic() -> None:
    """get_pool использует retry-логику при создании пула."""
    mock_pool = _make_mock_pool()
    call_count = 0

    async def create_pool_side_effect(**kwargs: object) -> MagicMock:
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise ConnectionRefusedError("Connection refused")
        return mock_pool

    with patch("src.database._get_settings", return_value=_make_settings()):
        with patch("src.database.asyncpg.create_pool", side_effect=create_pool_side_effect):
            with patch("src.database.asyncio.sleep", new_callable=AsyncMock):
                result = await get_pool()

    assert result is mock_pool
    assert call_count == 2
