"""
Валидация данных сессии Telegram.

Назначение:
- Валидация session_name
- Валидация session_data
- Проверка целостности данных
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


class SessionValidationError(Exception):
    """Исключение валидации сессии."""

    def __init__(self, message: str, code: str = "VALIDATION_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(self.message)


class SessionValidator:
    """Валидатор данных сессии Telegram."""

    MIN_SESSION_SIZE = 100
    MAX_SESSION_NAME_LENGTH = 255
    # Поддержка буквенно-цифровых символов, дефисов и подчёркиваний
    SESSION_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+(\.[a-zA-Z0-9_-]+)*$')

    def __init__(self) -> None:
        """Инициализация валидатора."""
        pass

    def validate_session_name(self, session_name: str) -> None:
        """
        Валидировать имя сессии.

        Args:
            session_name: Имя сессии для проверки.

        Raises:
            SessionValidationError: Если имя невалидно.
        """
        if not session_name:
            raise SessionValidationError(
                "Session name cannot be empty",
                "EMPTY_SESSION_NAME"
            )

        if len(session_name) > self.MAX_SESSION_NAME_LENGTH:
            raise SessionValidationError(
                f"Session name too long: {len(session_name)} > {self.MAX_SESSION_NAME_LENGTH}",
                "SESSION_NAME_TOO_LONG"
            )

        # Проверка на path traversal атаку
        if '..' in session_name or session_name.startswith('/'):
            raise SessionValidationError(
                "Invalid session name",
                "PATH_TRAVERSAL"
            )

        # Проверка формата: поддержка UUID с дефисами (например, qr_auth_550e8400-e29b-41d4-a716-446655440000)
        if not self.SESSION_NAME_PATTERN.match(session_name):
            raise SessionValidationError(
                f"Session name has invalid format: {session_name}",
                "INVALID_SESSION_NAME_FORMAT"
            )

    def validate_session_data(self, session_data: bytes) -> None:
        """
        Валидировать данные сессии.

        Args:
            session_data: Бинарные данные сессии.

        Raises:
            SessionValidationError: Если данные невалидны.
        """
        if not session_data:
            raise SessionValidationError(
                "Session data cannot be empty",
                "EMPTY_SESSION_DATA"
            )

        if len(session_data) < self.MIN_SESSION_SIZE:
            raise SessionValidationError(
                f"Session data too small: {len(session_data)} < {self.MIN_SESSION_SIZE}",
                "SESSION_DATA_TOO_SMALL"
            )

    def validate_session_file(self, session_file: Path) -> None:
        """
        Валидировать файл сессии.

        Args:
            session_file: Путь к файлу сессии.

        Raises:
            SessionValidationError: Если файл невалиден.
        """
        if not session_file.exists():
            raise SessionValidationError(
                f"Session file not found: {session_file}",
                "FILE_NOT_FOUND"
            )

        if not session_file.is_file():
            raise SessionValidationError(
                f"Session path is not a file: {session_file}",
                "NOT_A_FILE"
            )

        if session_file.suffix != ".session":
            logger.warning(f"Session file has unexpected extension: {session_file.suffix}")

        file_size = session_file.stat().st_size
        if file_size < self.MIN_SESSION_SIZE:
            raise SessionValidationError(
                f"Session file too small: {file_size} < {self.MIN_SESSION_SIZE}",
                "FILE_TOO_SMALL"
            )

    def validate_backup_path(self, backup_path: Path) -> None:
        """
        Валидировать путь к бэкапу.

        Args:
            backup_path: Путь к файлу бэкапа.

        Raises:
            SessionValidationError: Если путь невалиден.
        """
        if not backup_path:
            raise SessionValidationError(
                "Backup path cannot be None",
                "EMPTY_BACKUP_PATH"
            )

        if not backup_path.parent.exists():
            raise SessionValidationError(
                f"Backup directory does not exist: {backup_path.parent}",
                "BACKUP_DIR_NOT_FOUND"
            )
