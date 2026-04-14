"""
Модульные тесты для SessionBackupService и BackupError.

Тестируют:
- BackupError исключение
- SessionBackupService инициализация
- _ensure_backup_directory
- _check_disk_space
- _generate_backup_filename
- _set_secure_permissions
- create_backup
- get_backup_size
"""

import shutil

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.auth.session_backup_service import BackupError, SessionBackupService
from src.auth.session_validator import SessionValidationError


class TestBackupError:
    """Тесты для исключения BackupError."""

    def test_backup_error_with_message_and_code(self) -> None:
        """Создание исключения с message и code."""
        exc = BackupError("Backup failed", "COPY_FAILED")

        assert exc.message == "Backup failed"
        assert exc.code == "COPY_FAILED"
        assert str(exc) == "Backup failed"

    def test_backup_error_default_code(self) -> None:
        """Создание исключения с кодом по умолчанию."""
        exc = BackupError("Some backup error")

        assert exc.code == "BACKUP_ERROR"


class TestSessionBackupServiceInit:
    """Тесты инициализации SessionBackupService."""

    def test_backup_service_init(self) -> None:
        """Инициализация сервиса."""
        backup_dir = Path("/backups")
        mock_validator = MagicMock()

        service = SessionBackupService(
            backup_dir=backup_dir,
            validator=mock_validator,
        )

        assert service._backup_dir == backup_dir
        assert service._validator is mock_validator

    def test_backup_service_init_default_validator(self) -> None:
        """Инициализация с валидатором по умолчанию."""
        backup_dir = Path("/backups")

        service = SessionBackupService(backup_dir=backup_dir)

        assert service._backup_dir == backup_dir
        assert service._validator is not None


class TestEnsureBackupDirectory:
    """Тесты метода _ensure_backup_directory."""

    def test_ensure_backup_directory(self) -> None:
        """Создание директории бэкапа."""
        backup_dir = MagicMock(spec=Path)
        service = SessionBackupService(backup_dir=backup_dir, validator=MagicMock())

        service._ensure_backup_directory()

        backup_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)


class TestCheckDiskSpace:
    """Тесты метода _check_disk_space."""

    def test_check_disk_space_sufficient(self) -> None:
        """Достаточно места на диске."""
        backup_dir = Path("/backups")
        service = SessionBackupService(backup_dir=backup_dir, validator=MagicMock())

        mock_source = MagicMock(spec=Path)
        mock_source.exists.return_value = True
        mock_source.stat.return_value = MagicMock(st_size=1024 * 1024)

        mock_disk_usage = MagicMock()
        mock_disk_usage.free = 100 * 1024 * 1024

        with patch("shutil.disk_usage", return_value=mock_disk_usage):
            service._check_disk_space(mock_source)

    def test_check_disk_space_insufficient(self) -> None:
        """Недостаточно места — INSUFFICIENT_DISK_SPACE."""
        backup_dir = Path("/backups")
        service = SessionBackupService(backup_dir=backup_dir, validator=MagicMock())

        mock_source = MagicMock(spec=Path)
        mock_source.exists.return_value = True
        mock_source.stat.return_value = MagicMock(st_size=1024 * 1024)

        mock_disk_usage = MagicMock()
        mock_disk_usage.free = 5 * 1024 * 1024

        with patch("shutil.disk_usage", return_value=mock_disk_usage):
            with pytest.raises(BackupError) as exc_info:
                service._check_disk_space(mock_source)

        assert exc_info.value.code == "INSUFFICIENT_DISK_SPACE"

    def test_check_disk_space_os_error(self) -> None:
        """OSError при проверке — warning в лог."""
        backup_dir = Path("/backups")
        service = SessionBackupService(backup_dir=backup_dir, validator=MagicMock())

        mock_source = MagicMock(spec=Path)
        mock_source.exists.return_value = True
        mock_source.stat.return_value = MagicMock(st_size=1024 * 1024)

        with patch("shutil.disk_usage", side_effect=OSError("Cannot stat")), \
             patch("src.auth.session_backup_service.logger") as mock_logger:

            service._check_disk_space(mock_source)

            mock_logger.warning.assert_called_once()

    def test_check_disk_space_source_not_exists(self) -> None:
        """Исходный файл не существует — проверка пропускается."""
        backup_dir = Path("/backups")
        service = SessionBackupService(backup_dir=backup_dir, validator=MagicMock())

        mock_source = MagicMock(spec=Path)
        mock_source.exists.return_value = False

        with patch("shutil.disk_usage") as mock_disk_usage:
            service._check_disk_space(mock_source)

            mock_disk_usage.assert_not_called()


class TestGenerateBackupFilename:
    """Тесты метода _generate_backup_filename."""

    def test_generate_backup_filename(self) -> None:
        """Формат имени файла с timestamp."""
        backup_dir = Path("/backups")
        service = SessionBackupService(backup_dir=backup_dir, validator=MagicMock())

        mock_source = MagicMock(spec=Path)
        mock_source.stem = "my_session"
        mock_source.suffix = ".session"

        with patch("src.auth.session_backup_service.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.strftime.return_value = "20240101_120000"
            mock_datetime.now.return_value = mock_now

            filename = service._generate_backup_filename(mock_source)

        assert filename == "my_session_backup_20240101_120000.session"


class TestSetSecurePermissions:
    """Тесты метода _set_secure_permissions."""

    def test_set_secure_permissions(self) -> None:
        """Установка прав 0o600."""
        backup_dir = Path("/backups")
        service = SessionBackupService(backup_dir=backup_dir, validator=MagicMock())

        mock_file = MagicMock(spec=Path)

        service._set_secure_permissions(mock_file)

        mock_file.chmod.assert_called_once_with(0o600)

    def test_set_secure_permissions_os_error(self) -> None:
        """OSError при установке прав — warning в лог."""
        backup_dir = Path("/backups")
        service = SessionBackupService(backup_dir=backup_dir, validator=MagicMock())

        mock_file = MagicMock(spec=Path)
        mock_file.chmod.side_effect = OSError("Operation not permitted")

        with patch("src.auth.session_backup_service.logger") as mock_logger:
            service._set_secure_permissions(mock_file)

            mock_logger.warning.assert_called_once()


class TestCreateBackup:
    """Тесты метода create_backup."""

    def test_create_backup_success(self) -> None:
        """Успешный бэкап."""
        backup_dir = MagicMock(spec=Path)
        backup_dir.__truediv__ = lambda self, x: Path("/backups") / x
        mock_validator = MagicMock()

        service = SessionBackupService(backup_dir=backup_dir, validator=mock_validator)

        mock_source = MagicMock(spec=Path)
        mock_source.exists.return_value = True
        mock_source.is_file.return_value = True
        mock_source.suffix = ".session"
        mock_source.stat.return_value = MagicMock(st_size=5000)
        mock_source.stem = "my_session"

        mock_backup_file = MagicMock(spec=Path)
        mock_backup_file.chmod = MagicMock()

        with patch("shutil.copy2") as mock_copy, \
             patch.object(service, "_ensure_backup_directory"), \
             patch.object(service, "_check_disk_space"), \
             patch.object(service, "_generate_backup_filename", return_value="my_session_backup.session"), \
             patch.object(service, "_set_secure_permissions"):

            result = service.create_backup(mock_source)

            mock_copy.assert_called_once()
            assert result is not None

    def test_create_backup_validation_error(self) -> None:
        """Ошибка валидации файла пробрасывается."""
        backup_dir = Path("/backups")
        mock_validator = MagicMock()
        mock_validator.validate_session_file.side_effect = SessionValidationError(
            "Invalid file", "FILE_NOT_FOUND"
        )

        service = SessionBackupService(backup_dir=backup_dir, validator=mock_validator)
        mock_source = MagicMock(spec=Path)

        with pytest.raises(SessionValidationError) as exc_info:
            service.create_backup(mock_source)

        assert exc_info.value.code == "FILE_NOT_FOUND"

    def test_create_backup_copy_failed(self) -> None:
        """Ошибка копирования — COPY_FAILED."""
        backup_dir = MagicMock(spec=Path)
        backup_dir.__truediv__ = lambda self, x: Path("/backups") / x
        mock_validator = MagicMock()

        service = SessionBackupService(backup_dir=backup_dir, validator=mock_validator)

        mock_source = MagicMock(spec=Path)
        mock_source.exists.return_value = True
        mock_source.is_file.return_value = True
        mock_source.suffix = ".session"
        mock_source.stat.return_value = MagicMock(st_size=5000)
        mock_source.stem = "my_session"

        with patch("shutil.copy2", side_effect=shutil.Error("Copy failed")), \
             patch.object(service, "_ensure_backup_directory"), \
             patch.object(service, "_check_disk_space"), \
             patch.object(service, "_generate_backup_filename", return_value="backup.session"):

            with pytest.raises(BackupError) as exc_info:
                service.create_backup(mock_source)

        assert exc_info.value.code == "COPY_FAILED"

    def test_create_backup_os_error(self) -> None:
        """OSError — OS_ERROR."""
        backup_dir = MagicMock(spec=Path)
        backup_dir.__truediv__ = lambda self, x: Path("/backups") / x
        mock_validator = MagicMock()

        service = SessionBackupService(backup_dir=backup_dir, validator=mock_validator)

        mock_source = MagicMock(spec=Path)
        mock_source.exists.return_value = True
        mock_source.is_file.return_value = True
        mock_source.suffix = ".session"
        mock_source.stat.return_value = MagicMock(st_size=5000)
        mock_source.stem = "my_session"

        with patch("shutil.copy2", side_effect=OSError("Disk full")), \
             patch.object(service, "_ensure_backup_directory"), \
             patch.object(service, "_check_disk_space"), \
             patch.object(service, "_generate_backup_filename", return_value="backup.session"):

            with pytest.raises(BackupError) as exc_info:
                service.create_backup(mock_source)

        assert exc_info.value.code == "OS_ERROR"


class TestGetBackupSize:
    """Тесты метода get_backup_size."""

    def test_get_backup_size_exists(self) -> None:
        """Размер существующего файла."""
        backup_dir = Path("/backups")
        service = SessionBackupService(backup_dir=backup_dir, validator=MagicMock())

        mock_file = MagicMock(spec=Path)
        mock_file.exists.return_value = True
        mock_file.stat.return_value = MagicMock(st_size=12345)

        result = service.get_backup_size(mock_file)

        assert result == 12345

    def test_get_backup_size_not_exists(self) -> None:
        """0 для несуществующего файла."""
        backup_dir = Path("/backups")
        service = SessionBackupService(backup_dir=backup_dir, validator=MagicMock())

        mock_file = MagicMock(spec=Path)
        mock_file.exists.return_value = False

        result = service.get_backup_size(mock_file)

        assert result == 0
