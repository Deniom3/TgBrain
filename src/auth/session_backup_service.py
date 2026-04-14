"""
Сервис бэкапа сессий Telegram.

Назначение:
- Создание бэкапа файлов сессии
- Проверка места на диске
- Установка безопасных прав доступа (0o600)
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path

from .session_validator import SessionValidator

logger = logging.getLogger(__name__)


class BackupError(Exception):
    """Исключение ошибки бэкапа."""

    def __init__(self, message: str, code: str = "BACKUP_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(self.message)


class SessionBackupService:
    """Сервис бэкапа сессий Telegram."""

    MIN_FREE_SPACE_MB = 10
    BACKUP_PERMISSIONS = 0o600

    def __init__(
        self,
        backup_dir: Path,
        validator: SessionValidator | None = None
    ) -> None:
        """
        Инициализация сервиса бэкапа.

        Args:
            backup_dir: Директория для хранения бэкапов.
            validator: Валидатор сессий.
        """
        self._backup_dir = backup_dir
        self._validator = validator or SessionValidator()

    def _ensure_backup_directory(self) -> None:
        """Создать директорию бэкапа если не существует."""
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Backup directory ensured: {self._backup_dir}")

    def _check_disk_space(self, source_file: Path) -> None:
        """
        Проверить свободное место на диске.

        Args:
            source_file: Исходный файл для оценки размера.

        Raises:
            BackupError: Если недостаточно места.
        """
        if not source_file.exists():
            return

        file_size = source_file.stat().st_size
        file_size_mb = file_size / (1024 * 1024)

        try:
            stat = shutil.disk_usage(self._backup_dir)
            free_mb = stat.free / (1024 * 1024)

            if free_mb < self.MIN_FREE_SPACE_MB:
                raise BackupError(
                    f"Insufficient disk space: {free_mb:.1f} MB free, "
                    f"required {self.MIN_FREE_SPACE_MB} MB minimum",
                    "INSUFFICIENT_DISK_SPACE"
                )

            logger.debug(
                f"Disk space check passed: {free_mb:.1f} MB free, "
                f"file size {file_size_mb:.1f} MB"
            )

        except OSError as e:
            logger.warning(f"Could not check disk space: {e}")

    def _generate_backup_filename(self, source_file: Path) -> str:
        """
        Сгенерировать имя файла бэкапа.

        Args:
            source_file: Исходный файл.

        Returns:
            Имя файла бэкапа.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{source_file.stem}_backup_{timestamp}{source_file.suffix}"

    def _set_secure_permissions(self, backup_file: Path) -> None:
        """
        Установить безопасные права доступа на файл бэкапа.

        Args:
            backup_file: Файл бэкапа.
        """
        try:
            backup_file.chmod(self.BACKUP_PERMISSIONS)
            logger.debug(f"Set permissions {oct(self.BACKUP_PERMISSIONS)} on {backup_file}")
        except OSError as e:
            logger.warning(f"Could not set permissions on {backup_file}: {e}")

    def create_backup(self, source_file: Path) -> Path:
        """
        Создать бэкап файла сессии.

        Args:
            source_file: Путь к файлу сессии.

        Returns:
            Путь к файлу бэкапа.

        Raises:
            BackupError: Если создание бэкапа не удалось.
            SessionValidationError: Если файл не прошёл валидацию.
        """
        self._validator.validate_session_file(source_file)
        self._ensure_backup_directory()
        self._check_disk_space(source_file)

        backup_filename = self._generate_backup_filename(source_file)
        backup_file = self._backup_dir / backup_filename

        try:
            shutil.copy2(source_file, backup_file)
            self._set_secure_permissions(backup_file)

            logger.info(f"Backup created: {backup_file}")
            return backup_file

        except shutil.Error as e:
            raise BackupError(
                f"Failed to copy session file: {e}",
                "COPY_FAILED"
            )
        except OSError as e:
            raise BackupError(
                f"OS error during backup: {e}",
                "OS_ERROR"
            )

    def get_backup_size(self, backup_file: Path) -> int:
        """
        Получить размер файла бэкапа.

        Args:
            backup_file: Файл бэкапа.

        Returns:
            Размер в байтах.
        """
        if not backup_file.exists():
            return 0
        return backup_file.stat().st_size
