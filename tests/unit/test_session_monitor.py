"""
Модульные тесты для SessionMonitor и cleanup_old_qr_sessions.

Тестируют:
- SessionMonitor.__init__
- SessionMonitor.stop()
- SessionMonitor.run() — полный набор сценариев
- cleanup_old_qr_sessions — все варианты
"""

import asyncio
import os
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.auth.session_monitor import SessionMonitor, cleanup_old_qr_sessions


class TestSessionMonitorInit:
    """Тесты инициализации SessionMonitor."""

    def test_session_monitor_init(self) -> None:
        """Инициализация с параметрами."""
        mock_service = MagicMock()
        monitor = SessionMonitor(
            service=mock_service,
            session_id="test-session-123",
            api_id=12345,
            api_hash="test_api_hash",
            session_path="./sessions",
        )

        assert monitor._service is mock_service
        assert monitor._session_id == "test-session-123"
        assert monitor._api_id == 12345
        assert monitor._api_hash == "test_api_hash"
        assert monitor._session_path == "./sessions"
        assert monitor._is_running is False
        assert monitor._task is None


class TestSessionMonitorStop:
    """Тесты метода stop."""

    def test_stop_not_running(self) -> None:
        """Остановка когда мониторинг не запущен."""
        mock_service = MagicMock()
        monitor = SessionMonitor(
            service=mock_service,
            session_id="test-session",
            api_id=12345,
            api_hash="test_hash",
            session_path="./sessions",
        )
        monitor._task = None

        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            monitor.stop()

            mock_logger.debug.assert_called_once()

    def test_stop_running(self) -> None:
        """Остановка когда мониторинг запущен."""
        mock_service = MagicMock()
        monitor = SessionMonitor(
            service=mock_service,
            session_id="test-session",
            api_id=12345,
            api_hash="test_hash",
            session_path="./sessions",
        )

        mock_task = MagicMock()
        mock_task.done.return_value = False
        mock_task.cancel = MagicMock()
        monitor._task = mock_task

        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            monitor.stop()

            mock_task.cancel.assert_called_once()
            assert monitor._is_running is False
            mock_logger.info.assert_called_once()


class TestSessionMonitorRun:
    """Тесты метода run().

    Все тесты мокают asyncio.sleep чтобы избежать реальных задержек
    из-за rate limiting в исходном коде.
    """

    def _make_monitor(self) -> tuple[SessionMonitor, MagicMock]:
        mock_service = MagicMock()
        mock_service._lock = AsyncMock()
        mock_service._lock.__aenter__ = AsyncMock(return_value=None)
        mock_service._lock.__aexit__ = AsyncMock(return_value=None)
        mock_service._active_sessions = {}
        monitor = SessionMonitor(
            service=mock_service,
            session_id="test-session",
            api_id=12345,
            api_hash="test_hash",
            session_path="./sessions",
        )
        return monitor, mock_service

    @pytest.mark.asyncio
    async def test_run_session_not_in_active_sessions(self) -> None:
        """Сессия отсутствует в _active_sessions — ранний выход."""
        monitor, _ = self._make_monitor()

        with patch("asyncio.sleep", new_callable=AsyncMock), \
             patch("logging.getLogger"):
            await monitor.run()

    @pytest.mark.asyncio
    async def test_run_session_expired(self) -> None:
        """Сессия истекла — выход без авторизации."""
        monitor, mock_service = self._make_monitor()

        mock_session = MagicMock()
        mock_session.session_name = "test_session"
        mock_session.expires_at = datetime.now() - timedelta(hours=1)
        mock_session.is_completed = False
        mock_service._active_sessions["test-session"] = mock_session

        with patch("asyncio.sleep", new_callable=AsyncMock), \
             patch("logging.getLogger"):
            await monitor.run()

    @pytest.mark.asyncio
    async def test_run_session_already_completed(self) -> None:
        """Сессия уже завершена — выход."""
        monitor, mock_service = self._make_monitor()

        mock_session = MagicMock()
        mock_session.session_name = "test_session"
        mock_session.expires_at = datetime.now() + timedelta(minutes=5)
        mock_session.is_completed = True
        mock_service._active_sessions["test-session"] = mock_session

        with patch("asyncio.sleep", new_callable=AsyncMock), \
             patch("logging.getLogger"):
            await monitor.run()

    @pytest.mark.asyncio
    async def test_run_auth_success(self) -> None:
        """Авторизация обнаружена — _on_auth_success вызван."""
        monitor, mock_service = self._make_monitor()

        mock_session = MagicMock()
        mock_session.session_name = "test_session"
        mock_session.expires_at = datetime.now() + timedelta(minutes=5)
        mock_session.is_completed = False
        mock_service._active_sessions["test-session"] = mock_session
        mock_service._client = None

        mock_test_client = AsyncMock()
        mock_test_client.is_user_authorized = AsyncMock(return_value=True)
        mock_test_client.connect = AsyncMock()
        mock_test_client.disconnect = AsyncMock()

        auth_called = [False]

        async def mock_on_auth_success(session_id: str) -> None:
            mock_service._active_sessions[session_id].is_completed = True
            auth_called[0] = True

        mock_service._on_auth_success = mock_on_auth_success

        with patch("src.auth.session_monitor.os.path.exists", return_value=True), \
             patch("src.auth.session_monitor.TelegramClient", return_value=mock_test_client), \
             patch("asyncio.sleep", new_callable=AsyncMock), \
             patch("logging.getLogger"):

            await monitor.run()

        assert auth_called[0] is True

    @pytest.mark.asyncio
    async def test_run_auth_not_authorized(self) -> None:
        """Авторизация не подтверждена — disconnect вызван."""
        monitor, mock_service = self._make_monitor()

        mock_session = MagicMock()
        mock_session.session_name = "test_session"
        mock_session.expires_at = datetime.now() + timedelta(minutes=5)
        mock_session.is_completed = False
        mock_service._active_sessions["test-session"] = mock_session
        mock_service._client = None

        mock_test_client = AsyncMock()
        mock_test_client.is_user_authorized = AsyncMock(return_value=False)
        mock_test_client.connect = AsyncMock()
        mock_test_client.disconnect = AsyncMock()

        sleep_count = [0]

        async def mock_sleep(seconds: float) -> None:
            sleep_count[0] += 1
            if sleep_count[0] >= 2:
                mock_session.is_completed = True

        with patch("src.auth.session_monitor.os.path.exists", return_value=True), \
             patch("src.auth.session_monitor.TelegramClient", return_value=mock_test_client), \
             patch("asyncio.sleep", side_effect=mock_sleep), \
             patch("logging.getLogger"):

            await monitor.run()

        mock_test_client.disconnect.assert_called()

    @pytest.mark.asyncio
    async def test_run_file_not_found_during_check(self) -> None:
        """Файл сессии не найден во время проверки — логирует warning."""
        monitor, mock_service = self._make_monitor()

        mock_session = MagicMock()
        mock_session.session_name = "test_session"
        mock_session.expires_at = datetime.now() + timedelta(minutes=5)
        mock_session.is_completed = False
        mock_service._active_sessions["test-session"] = mock_session

        sleep_count = [0]

        async def mock_sleep(seconds: float) -> None:
            sleep_count[0] += 1
            if sleep_count[0] >= 2:
                mock_session.is_completed = True

        with patch("src.auth.session_monitor.os.path.exists", return_value=False), \
             patch("asyncio.sleep", side_effect=mock_sleep), \
             patch("logging.getLogger") as mock_get_logger:

            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            await monitor.run()

            mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_run_auth_check_error(self) -> None:
        """Ошибка проверки авторизации — логирует warning."""
        monitor, mock_service = self._make_monitor()

        mock_session = MagicMock()
        mock_session.session_name = "test_session"
        mock_session.expires_at = datetime.now() + timedelta(minutes=5)
        mock_session.is_completed = False
        mock_service._active_sessions["test-session"] = mock_session

        mock_test_client = AsyncMock()
        mock_test_client.connect = AsyncMock(side_effect=ConnectionError("Network error"))

        sleep_count = [0]

        async def mock_sleep(seconds: float) -> None:
            sleep_count[0] += 1
            if sleep_count[0] >= 2:
                mock_session.is_completed = True

        with patch("src.auth.session_monitor.os.path.exists", return_value=True), \
             patch("src.auth.session_monitor.TelegramClient", return_value=mock_test_client), \
             patch("asyncio.sleep", side_effect=mock_sleep), \
             patch("logging.getLogger") as mock_get_logger:

            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            await monitor.run()

            mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_run_cancelled_error(self) -> None:
        """CancelledError — корректная обработка отмены."""
        monitor, mock_service = self._make_monitor()

        mock_session = MagicMock()
        mock_session.session_name = "test_session"
        mock_session.expires_at = datetime.now() + timedelta(minutes=5)
        mock_session.is_completed = False
        mock_service._active_sessions["test-session"] = mock_session

        with patch("src.auth.session_monitor.os.path.exists", return_value=True), \
             patch("asyncio.sleep", side_effect=asyncio.CancelledError()), \
             patch("logging.getLogger") as mock_get_logger:

            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            await monitor.run()

            mock_logger.info.assert_called()


class TestCleanupOldQrSessions:
    """Тесты функции cleanup_old_qr_sessions."""

    @pytest.mark.asyncio
    async def test_path_not_exists(self) -> None:
        """Путь не существует — функция ничего не делает."""
        with patch("os.path.exists", return_value=False):
            await cleanup_old_qr_sessions("/nonexistent/path")

    @pytest.mark.asyncio
    async def test_remove_old_unauthorized(self) -> None:
        """Удаление старых неавторизованных сессий.

        Arrange: файл < 30KB и старше 5 минут.
        Act: вызов cleanup_old_qr_sessions.
        Assert: файл удалён.
        """
        session_path = "/tmp/sessions"
        filename = "qr_auth_old_session.session"
        file_path = os.path.join(session_path, filename)

        with patch("os.path.exists", return_value=True), \
             patch("os.listdir", return_value=[filename]), \
             patch("os.path.getsize", return_value=1000), \
             patch("os.path.getmtime", return_value=time.time() - 600), \
             patch("os.remove") as mock_remove:

            await cleanup_old_qr_sessions(session_path)

            mock_remove.assert_called_once_with(file_path)

    @pytest.mark.asyncio
    async def test_keep_authorized(self) -> None:
        """Сохранение авторизованных сессий (> 30KB)."""
        session_path = "/tmp/sessions"
        filename = "qr_auth_authorized.session"

        with patch("os.path.exists", return_value=True), \
             patch("os.listdir", return_value=[filename]), \
             patch("os.path.getsize", return_value=35000), \
             patch("os.path.getmtime", return_value=time.time() - 600), \
             patch("os.remove") as mock_remove:

            await cleanup_old_qr_sessions(session_path)

            mock_remove.assert_not_called()

    @pytest.mark.asyncio
    async def test_keep_recent(self) -> None:
        """Сохранение недавних сессий (< 5 минут)."""
        session_path = "/tmp/sessions"
        filename = "qr_auth_recent.session"

        with patch("os.path.exists", return_value=True), \
             patch("os.listdir", return_value=[filename]), \
             patch("os.path.getsize", return_value=1000), \
             patch("os.path.getmtime", return_value=time.time() - 60), \
             patch("os.remove") as mock_remove:

            await cleanup_old_qr_sessions(session_path)

            mock_remove.assert_not_called()

    @pytest.mark.asyncio
    async def test_keep_active_session(self) -> None:
        """Сохранение активной сессии из БД."""
        session_path = "/tmp/sessions"
        filename = "qr_auth_active_session.session"

        with patch("os.path.exists", return_value=True), \
             patch("os.listdir", return_value=[filename]), \
             patch("os.remove") as mock_remove:

            await cleanup_old_qr_sessions(session_path, active_session_name="qr_auth_active_session")

            mock_remove.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_qr_files(self) -> None:
        """Игнорирование не-QR файлов."""
        session_path = "/tmp/sessions"
        non_qr_files = [
            "regular_session.session",
            "qr_auth_incomplete.txt",
            "other_file.dat",
            "not_a_session",
        ]

        with patch("os.path.exists", return_value=True), \
             patch("os.listdir", return_value=non_qr_files), \
             patch("os.remove") as mock_remove:

            await cleanup_old_qr_sessions(session_path)

            mock_remove.assert_not_called()

    @pytest.mark.asyncio
    async def test_os_error_on_remove(self) -> None:
        """OSError при удалении файла логируется."""
        session_path = "/tmp/sessions"
        filename = "qr_auth_old_session.session"

        with patch("os.path.exists", return_value=True), \
             patch("os.listdir", return_value=[filename]), \
             patch("os.path.getsize", return_value=1000), \
             patch("os.path.getmtime", return_value=time.time() - 600), \
             patch("os.remove", side_effect=OSError("Permission denied")), \
             patch("logging.getLogger") as mock_get_logger:

            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            await cleanup_old_qr_sessions(session_path)

            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_general_exception(self) -> None:
        """Общее исключение логируется."""
        with patch("os.path.exists", side_effect=Exception("Unexpected error")), \
             patch("logging.getLogger") as mock_get_logger:

            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            await cleanup_old_qr_sessions("/tmp/sessions")

            mock_logger.error.assert_called_once()
