"""
Модульные тесты для SessionMigrationService и MigrationError.

Тестируют:
- MigrationError исключение
- SessionMigrationService инициализация
- get_session_info
- ensure_session_data_column
- remove_session_path_column
- find_session_file
- save_session_data
- verify_session_data
- migrate (полная миграция)
- _read_session_file
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.auth.session_migration_service import BackupError, MigrationError, SessionMigrationService
from src.auth.session_validator import SessionValidationError


class TestMigrationError:
    """Тесты для исключения MigrationError."""

    def test_migration_error_with_message_and_code(self) -> None:
        """Создание исключения с message и code."""
        exc = MigrationError("Migration failed", "AUTH_NOT_FOUND")

        assert exc.message == "Migration failed"
        assert exc.code == "AUTH_NOT_FOUND"
        assert str(exc) == "Migration failed"

    def test_migration_error_default_code(self) -> None:
        """Создание исключения с кодом по умолчанию."""
        exc = MigrationError("Some error")

        assert exc.code == "MIGRATION_ERROR"


class TestSessionMigrationServiceInit:
    """Тесты инициализации SessionMigrationService."""

    def test_migration_service_init(self) -> None:
        """Инициализация с моками."""
        mock_conn = AsyncMock()
        mock_backup = MagicMock()
        mock_validator = MagicMock()

        service = SessionMigrationService(
            db_connection=mock_conn,
            backup_service=mock_backup,
            validator=mock_validator,
        )

        assert service._conn is mock_conn
        assert service._backup_service is mock_backup
        assert service._validator is mock_validator

    def test_migration_service_init_default_validator(self) -> None:
        """Инициализация создаёт SessionValidator по умолчанию."""
        mock_conn = AsyncMock()
        mock_backup = MagicMock()

        service = SessionMigrationService(
            db_connection=mock_conn,
            backup_service=mock_backup,
        )

        assert service._validator is not None
        assert isinstance(service._validator, object)


class TestGetSessionInfo:
    """Тесты метода get_session_info."""

    @pytest.mark.asyncio
    async def test_get_session_info_found(self) -> None:
        """Запись найдена в БД."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {
            "session_name": "my_session",
            "session_path": "/data/sessions",
        }
        mock_backup = MagicMock()
        service = SessionMigrationService(mock_conn, mock_backup)

        result = await service.get_session_info()

        assert result is not None
        assert result == ("my_session", "/data/sessions")

    @pytest.mark.asyncio
    async def test_get_session_info_not_found(self) -> None:
        """Запись отсутствует — возвращает None."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = None
        mock_backup = MagicMock()
        service = SessionMigrationService(mock_conn, mock_backup)

        result = await service.get_session_info()

        assert result is None

    @pytest.mark.asyncio
    async def test_get_session_info_defaults(self) -> None:
        """Использование дефолтов при None значениях."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {
            "session_name": None,
            "session_path": None,
        }
        mock_backup = MagicMock()
        service = SessionMigrationService(mock_conn, mock_backup)

        result = await service.get_session_info()

        assert result is not None
        assert result[0] == "qr_auth_session"
        assert result[1] == "./sessions"


class TestEnsureSessionDataColumn:
    """Тесты метода ensure_session_data_column."""

    @pytest.mark.asyncio
    async def test_ensure_session_data_column_exists(self) -> None:
        """Колонка уже существует."""
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = True
        mock_backup = MagicMock()
        service = SessionMigrationService(mock_conn, mock_backup)

        await service.ensure_session_data_column()

        mock_conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_session_data_column_not_exists(self) -> None:
        """Добавление колонки."""
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = False
        mock_conn.execute = AsyncMock()
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction = MagicMock(return_value=mock_tx)
        mock_backup = MagicMock()
        service = SessionMigrationService(mock_conn, mock_backup)

        await service.ensure_session_data_column()

        mock_conn.execute.assert_called_once_with(
            "ALTER TABLE telegram_auth ADD COLUMN session_data BYTEA DEFAULT NULL"
        )


class TestRemoveSessionPathColumn:
    """Тесты метода remove_session_path_column."""

    @pytest.mark.asyncio
    async def test_remove_session_path_column_exists(self) -> None:
        """Удаление существующей колонки."""
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = True
        mock_conn.execute = AsyncMock()
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction = MagicMock(return_value=mock_tx)
        mock_backup = MagicMock()
        service = SessionMigrationService(mock_conn, mock_backup)

        await service.remove_session_path_column()

        mock_conn.execute.assert_called_once_with(
            "ALTER TABLE telegram_auth DROP COLUMN session_path"
        )

    @pytest.mark.asyncio
    async def test_remove_session_path_column_not_exists(self) -> None:
        """Колонка уже удалена."""
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = False
        mock_backup = MagicMock()
        service = SessionMigrationService(mock_conn, mock_backup)

        await service.remove_session_path_column()

        mock_conn.execute.assert_not_called()


class TestFindSessionFile:
    """Тесты метода find_session_file."""

    def test_find_session_file_found(self) -> None:
        """Файл найден по первому пути."""
        mock_conn = AsyncMock()
        mock_backup = MagicMock()
        service = SessionMigrationService(mock_conn, mock_backup)

        with patch("pathlib.Path.exists", return_value=True):
            result = service.find_session_file("my_session", "/data/sessions")

        assert result is not None

    def test_find_session_file_not_found(self) -> None:
        """Файл не найден ни в одном пути."""
        mock_conn = AsyncMock()
        mock_backup = MagicMock()
        service = SessionMigrationService(mock_conn, mock_backup)

        with patch("pathlib.Path.exists", return_value=False):
            result = service.find_session_file("missing_session", "/data/sessions")

        assert result is None

    def test_find_session_file_with_search_paths(self) -> None:
        """Поиск с дополнительными путями находит файл."""
        mock_conn = AsyncMock()
        mock_backup = MagicMock()
        service = SessionMigrationService(mock_conn, mock_backup)

        search_paths = [Path("/custom/path1"), Path("/custom/path2")]

        call_index = [0]

        def mock_exists_side_effect(self_path) -> bool:  # noqa: ANN001
            call_index[0] += 1
            return call_index[0] == 3

        with patch.object(Path, "exists", mock_exists_side_effect):
            result = service.find_session_file("my_session", "/data", search_paths)

        assert result is not None
        assert call_index[0] == 3


class TestSaveSessionData:
    """Тесты метода save_session_data."""

    @pytest.mark.asyncio
    async def test_save_session_data_valid(self) -> None:
        """Сохранение валидных данных."""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction = MagicMock(return_value=mock_tx)
        mock_backup = MagicMock()
        mock_validator = MagicMock()
        service = SessionMigrationService(mock_conn, mock_backup, mock_validator)

        session_data = b"x" * 200

        await service.save_session_data(session_data)

        mock_validator.validate_session_data.assert_called_once_with(session_data)
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_session_data_validation_error(self) -> None:
        """Ошибка валидации данных пробрасывается."""
        mock_conn = AsyncMock()
        mock_backup = MagicMock()
        mock_validator = MagicMock()
        mock_validator.validate_session_data.side_effect = SessionValidationError(
            "Invalid data", "INVALID_DATA"
        )
        service = SessionMigrationService(mock_conn, mock_backup, mock_validator)

        with pytest.raises(SessionValidationError):
            await service.save_session_data(b"short")


class TestVerifySessionData:
    """Тесты метода verify_session_data."""

    @pytest.mark.asyncio
    async def test_verify_session_data_valid(self) -> None:
        """Успешная верификация."""
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = 5000
        mock_backup = MagicMock()
        service = SessionMigrationService(mock_conn, mock_backup)

        result = await service.verify_session_data()

        assert result == 5000

    @pytest.mark.asyncio
    async def test_verify_session_data_not_found(self) -> None:
        """Данные не найдены — DATA_NOT_FOUND."""
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = None
        mock_backup = MagicMock()
        service = SessionMigrationService(mock_conn, mock_backup)

        with pytest.raises(MigrationError) as exc_info:
            await service.verify_session_data()

        assert exc_info.value.code == "DATA_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_verify_session_data_empty(self) -> None:
        """Данные пусты — DATA_EMPTY."""
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = 0
        mock_backup = MagicMock()
        service = SessionMigrationService(mock_conn, mock_backup)

        with pytest.raises(MigrationError) as exc_info:
            await service.verify_session_data()

        assert exc_info.value.code == "DATA_EMPTY"


class TestMigrate:
    """Тесты метода migrate."""

    @pytest.mark.asyncio
    async def test_migrate_success(self) -> None:
        """Полная успешная миграция."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {
            "session_name": "my_session",
            "session_path": "/data/sessions",
        }
        mock_conn.fetchval.return_value = 5000
        mock_conn.execute = AsyncMock()
        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=None)
        mock_tx.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction = MagicMock(return_value=mock_tx)

        mock_backup = MagicMock()
        mock_backup.create_backup.return_value = Path("/backups/backup.session")

        mock_validator = MagicMock()

        mock_session_file = MagicMock(spec=Path)
        mock_session_file.stat.return_value = MagicMock(st_size=5000)

        service = SessionMigrationService(mock_conn, mock_backup, mock_validator)

        with patch.object(service, "find_session_file", return_value=mock_session_file), \
             patch.object(service, "_read_session_file", return_value=b"x" * 5000):

            result = await service.migrate()

        assert result["success"] is True
        assert result["session_name"] == "my_session"
        assert result["data_size"] == 5000
        assert result["backup_path"] is not None

    @pytest.mark.asyncio
    async def test_migrate_auth_not_found(self) -> None:
        """Auth запись не найдена — AUTH_NOT_FOUND."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = None
        mock_backup = MagicMock()
        service = SessionMigrationService(mock_conn, mock_backup)

        with pytest.raises(MigrationError) as exc_info:
            await service.migrate()

        assert exc_info.value.code == "AUTH_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_migrate_session_file_not_found(self) -> None:
        """Файл сессии не найден — SESSION_FILE_NOT_FOUND."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {
            "session_name": "my_session",
            "session_path": "/data/sessions",
        }
        mock_backup = MagicMock()
        service = SessionMigrationService(mock_conn, mock_backup)

        with patch.object(service, "find_session_file", return_value=None):
            with pytest.raises(MigrationError) as exc_info:
                await service.migrate()

        assert exc_info.value.code == "SESSION_FILE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_migrate_backup_error(self) -> None:
        """BackupError при создании бэкапа — миграция падает с MigrationError."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {
            "session_name": "my_session",
            "session_path": "/data/sessions",
        }
        mock_backup = MagicMock()
        mock_backup.create_backup.side_effect = BackupError("Disk full", "DISK_FULL")
        service = SessionMigrationService(mock_conn, mock_backup)

        mock_file = MagicMock(spec=Path)
        with patch.object(service, "find_session_file", return_value=mock_file):
            with pytest.raises(MigrationError) as exc_info:
                await service.migrate()

        assert exc_info.value.code == "DISK_FULL"

    @pytest.mark.asyncio
    async def test_migrate_validation_error(self) -> None:
        """SessionValidationError при сохранении — миграция падает с MigrationError."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {
            "session_name": "my_session",
            "session_path": "/data/sessions",
        }
        mock_backup = MagicMock()
        mock_backup.create_backup.return_value = Path("/backup/session.session")
        service = SessionMigrationService(mock_conn, mock_backup)

        mock_file = MagicMock(spec=Path)
        with patch.object(service, "find_session_file", return_value=mock_file), \
             patch.object(service, "_read_session_file", return_value=b"tiny"):
            with pytest.raises(MigrationError) as exc_info:
                await service.migrate()

        assert exc_info.value.code == "SESSION_DATA_TOO_SMALL"


class TestReadSessionFile:
    """Тесты метода _read_session_file."""

    def test_read_session_file_too_large(self) -> None:
        """Файл > 10MB вызывает FILE_TOO_LARGE."""
        mock_conn = AsyncMock()
        mock_backup = MagicMock()
        service = SessionMigrationService(mock_conn, mock_backup)

        mock_file = MagicMock(spec=Path)
        mock_file.stat.return_value = MagicMock(st_size=11 * 1024 * 1024)

        with pytest.raises(MigrationError) as exc_info:
            service._read_session_file(mock_file)

        assert exc_info.value.code == "FILE_TOO_LARGE"

    def test_read_session_file_valid(self) -> None:
        """Чтение файла в пределах лимита."""
        mock_conn = AsyncMock()
        mock_backup = MagicMock()
        service = SessionMigrationService(mock_conn, mock_backup)

        mock_file = MagicMock(spec=Path)
        mock_file.stat.return_value = MagicMock(st_size=5000)

        mock_open = MagicMock()
        mock_open.__enter__ = MagicMock(return_value=mock_open)
        mock_open.__exit__ = MagicMock(return_value=None)
        mock_open.read.return_value = b"x" * 5000

        with patch("builtins.open", return_value=mock_open):
            result = service._read_session_file(mock_file)

        assert result == b"x" * 5000
