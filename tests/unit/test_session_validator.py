"""
Модульные тесты для SessionValidator и SessionValidationError.

Тестируют:
- SessionValidationError с message и code
- SessionValidator.validate_session_name()
- SessionValidator.validate_session_data()
- SessionValidator.validate_session_file()
- SessionValidator.validate_backup_path()
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from src.auth.session_validator import SessionValidationError, SessionValidator


@pytest.fixture
def validator() -> SessionValidator:
    return SessionValidator()


class TestSessionValidationError:
    """Тесты для исключения SessionValidationError."""

    def test_error_has_message(self) -> None:
        """Исключение содержит message."""
        exc = SessionValidationError("Test message", "TEST_CODE")

        assert exc.message == "Test message"

    def test_error_has_code(self) -> None:
        """Исключение содержит code."""
        exc = SessionValidationError("Test message", "TEST_CODE")

        assert exc.code == "TEST_CODE"

    def test_error_str_returns_message(self) -> None:
        """str(exc) возвращает message."""
        exc = SessionValidationError("Test message", "TEST_CODE")

        assert str(exc) == "Test message"

    def test_error_default_code(self) -> None:
        """Код по умолчанию — VALIDATION_ERROR."""
        exc = SessionValidationError("Test message")

        assert exc.code == "VALIDATION_ERROR"


class TestValidateSessionName:
    """Тесты для validate_session_name."""

    def test_valid_letters(self, validator: SessionValidator) -> None:
        """Валидное имя из букв — проходит."""
        validator.validate_session_name("my_session")

    def test_valid_digits(self, validator: SessionValidator) -> None:
        """Валидное имя из цифр — проходит."""
        validator.validate_session_name("session123")

    def test_valid_dashes(self, validator: SessionValidator) -> None:
        """Валидное имя с дефисами — проходит."""
        validator.validate_session_name("my-session-name")

    def test_valid_uuid_format(self, validator: SessionValidator) -> None:
        """Валидное имя в формате UUID — проходит."""
        validator.validate_session_name("qr_auth_550e8400-e29b-41d4-a716-446655440000")

    def test_valid_dotted(self, validator: SessionValidator) -> None:
        """Валидное имя с точками — проходит."""
        validator.validate_session_name("session.v2")

    def test_valid_exactly_255_chars(self, validator: SessionValidator) -> None:
        """Имя ровно 255 символов — проходит (граничное значение)."""
        name = "a" * 255

        validator.validate_session_name(name)

    def test_empty_raises(self, validator: SessionValidator) -> None:
        """Пустое имя — EMPTY_SESSION_NAME."""
        with pytest.raises(SessionValidationError) as exc_info:
            validator.validate_session_name("")

        assert exc_info.value.code == "EMPTY_SESSION_NAME"

    def test_none_raises(self, validator: SessionValidator) -> None:
        """None — EMPTY_SESSION_NAME."""
        with pytest.raises(SessionValidationError) as exc_info:
            validator.validate_session_name(None)  # type: ignore[arg-type]

        assert exc_info.value.code == "EMPTY_SESSION_NAME"

    def test_too_long_raises(self, validator: SessionValidator) -> None:
        """256 символов — SESSION_NAME_TOO_LONG."""
        long_name = "a" * 256

        with pytest.raises(SessionValidationError) as exc_info:
            validator.validate_session_name(long_name)

        assert exc_info.value.code == "SESSION_NAME_TOO_LONG"

    def test_path_traversal_double_dot_raises(self, validator: SessionValidator) -> None:
        """С .. — PATH_TRAVERSAL."""
        with pytest.raises(SessionValidationError) as exc_info:
            validator.validate_session_name("../etc/passwd")

        assert exc_info.value.code == "PATH_TRAVERSAL"

    def test_path_traversal_leading_slash_raises(self, validator: SessionValidator) -> None:
        """Начинается с / — PATH_TRAVERSAL."""
        with pytest.raises(SessionValidationError) as exc_info:
            validator.validate_session_name("/absolute/path")

        assert exc_info.value.code == "PATH_TRAVERSAL"

    def test_invalid_format_special_chars_raises(self, validator: SessionValidator) -> None:
        """Спецсимволы — INVALID_SESSION_NAME_FORMAT."""
        with pytest.raises(SessionValidationError) as exc_info:
            validator.validate_session_name("session@name!")

        assert exc_info.value.code == "INVALID_SESSION_NAME_FORMAT"

    def test_invalid_format_spaces_raises(self, validator: SessionValidator) -> None:
        """Пробелы — INVALID_SESSION_NAME_FORMAT."""
        with pytest.raises(SessionValidationError) as exc_info:
            validator.validate_session_name("my session")

        assert exc_info.value.code == "INVALID_SESSION_NAME_FORMAT"


class TestValidateSessionData:
    """Тесты для validate_session_data."""

    def test_valid_200_bytes(self, validator: SessionValidator) -> None:
        """200 байт — проходит."""
        validator.validate_session_data(b"x" * 200)

    def test_valid_exactly_100_bytes(self, validator: SessionValidator) -> None:
        """Ровно 100 байт — проходит (нижняя граница)."""
        validator.validate_session_data(b"x" * 100)

    def test_empty_raises(self, validator: SessionValidator) -> None:
        """Пустые байты — EMPTY_SESSION_DATA."""
        with pytest.raises(SessionValidationError) as exc_info:
            validator.validate_session_data(b"")

        assert exc_info.value.code == "EMPTY_SESSION_DATA"

    def test_none_raises(self, validator: SessionValidator) -> None:
        """None — EMPTY_SESSION_DATA."""
        with pytest.raises(SessionValidationError) as exc_info:
            validator.validate_session_data(None)  # type: ignore[arg-type]

        assert exc_info.value.code == "EMPTY_SESSION_DATA"

    def test_99_bytes_raises(self, validator: SessionValidator) -> None:
        """99 байт — SESSION_DATA_TOO_SMALL (граничное значение)."""
        with pytest.raises(SessionValidationError) as exc_info:
            validator.validate_session_data(b"x" * 99)

        assert exc_info.value.code == "SESSION_DATA_TOO_SMALL"

    def test_50_bytes_raises(self, validator: SessionValidator) -> None:
        """50 байт — SESSION_DATA_TOO_SMALL."""
        with pytest.raises(SessionValidationError) as exc_info:
            validator.validate_session_data(b"x" * 50)

        assert exc_info.value.code == "SESSION_DATA_TOO_SMALL"


class TestValidateSessionFile:
    """Тесты для validate_session_file с использованием tmp_path."""

    def test_valid_session_file(self, validator: SessionValidator, tmp_path: Path) -> None:
        """Существующий .session файл >= 100 байт — проходит."""
        session_file = tmp_path / "test.session"
        session_file.write_bytes(b"x" * 200)

        validator.validate_session_file(session_file)

    def test_exactly_100_bytes(self, validator: SessionValidator, tmp_path: Path) -> None:
        """Файл ровно 100 байт — проходит (нижняя граница)."""
        session_file = tmp_path / "min.session"
        session_file.write_bytes(b"x" * 100)

        validator.validate_session_file(session_file)

    def test_not_found_raises(self, validator: SessionValidator, tmp_path: Path) -> None:
        """Несуществующий файл — FILE_NOT_FOUND."""
        missing_file = tmp_path / "missing.session"

        with pytest.raises(SessionValidationError) as exc_info:
            validator.validate_session_file(missing_file)

        assert exc_info.value.code == "FILE_NOT_FOUND"

    def test_directory_raises(self, validator: SessionValidator, tmp_path: Path) -> None:
        """Директория вместо файла — NOT_A_FILE."""
        with pytest.raises(SessionValidationError) as exc_info:
            validator.validate_session_file(tmp_path)

        assert exc_info.value.code == "NOT_A_FILE"

    def test_too_small_raises(self, validator: SessionValidator, tmp_path: Path) -> None:
        """Файл < 100 байт — FILE_TOO_SMALL."""
        small_file = tmp_path / "small.session"
        small_file.write_bytes(b"x" * 50)

        with pytest.raises(SessionValidationError) as exc_info:
            validator.validate_session_file(small_file)

        assert exc_info.value.code == "FILE_TOO_SMALL"

    def test_wrong_extension_warns(self, validator: SessionValidator, tmp_path: Path) -> None:
        """Файл с другим расширением — warning в лог, но не exception."""
        txt_file = tmp_path / "data.txt"
        txt_file.write_bytes(b"x" * 200)

        with patch("src.auth.session_validator.logger") as mock_logger:
            validator.validate_session_file(txt_file)
            mock_logger.warning.assert_called_once()


class TestValidateBackupPath:
    """Тесты для validate_backup_path."""

    def test_valid_path(self, validator: SessionValidator, tmp_path: Path) -> None:
        """Валидный путь с существующей родительской директорией — проходит."""
        backup_path = tmp_path / "backup.session"

        validator.validate_backup_path(backup_path)

    def test_none_raises(self, validator: SessionValidator) -> None:
        """None — EMPTY_BACKUP_PATH."""
        with pytest.raises(SessionValidationError) as exc_info:
            validator.validate_backup_path(None)  # type: ignore[arg-type]

        assert exc_info.value.code == "EMPTY_BACKUP_PATH"

    def test_dir_not_found_raises(self, validator: SessionValidator, tmp_path: Path) -> None:
        """Несуществующая родительская директория — BACKUP_DIR_NOT_FOUND."""
        nonexistent_parent = tmp_path / "nonexistent" / "backup.session"

        with pytest.raises(SessionValidationError) as exc_info:
            validator.validate_backup_path(nonexistent_parent)

        assert exc_info.value.code == "BACKUP_DIR_NOT_FOUND"
