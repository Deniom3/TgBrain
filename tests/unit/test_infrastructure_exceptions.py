"""
Тесты для иерархии исключений infrastructure слоя.

Проверяет корректность работы исключений InfrastructureError, DatabaseError,
ExternalServiceError и FileStorageError.
"""

import pytest

from src.infrastructure.exceptions import (
    DatabaseError,
    ExternalServiceError,
    FileStorageError,
    InfrastructureError,
)


class TestInfrastructureError:
    """Тесты для базового исключения InfrastructureError."""

    def test_infrastructure_error_creation(self) -> None:
        """InfrastructureError может быть создано с сообщением."""
        error = InfrastructureError("Test error message")
        assert error.message == "Test error message"
        assert str(error) == "Test error message"

    def test_infrastructure_error_inherits_from_exception(self) -> None:
        """InfrastructureError наследуется от Exception."""
        error = InfrastructureError("Test")
        assert isinstance(error, Exception)

    def test_infrastructure_error_can_be_raised(self) -> None:
        """InfrastructureError может быть выброшено и поймано."""
        with pytest.raises(InfrastructureError) as exc_info:
            raise InfrastructureError("Infrastructure error occurred")
        assert exc_info.value.message == "Infrastructure error occurred"


class TestDatabaseError:
    """Тесты для исключения DatabaseError."""

    def test_database_error_without_query(self) -> None:
        """DatabaseError без указания SQL запроса."""
        error = DatabaseError("Connection failed")
        assert error.message == "Connection failed"
        assert error.query is None
        assert "DatabaseError" in str(error)

    def test_database_error_with_query(self) -> None:
        """DatabaseError с указанием SQL запроса."""
        query = "SELECT * FROM users WHERE id = $1"
        error = DatabaseError("Syntax error in SQL", query=query)
        assert error.message == "Syntax error in SQL"
        assert error.query == query
        assert f"query={query!r}" in str(error)

    def test_database_error_inherits_from_infrastructure_error(self) -> None:
        """DatabaseError наследуется от InfrastructureError."""
        error = DatabaseError("Test")
        assert isinstance(error, InfrastructureError)

    def test_database_error_can_be_caught_as_infrastructure_error(self) -> None:
        """DatabaseError может быть поймано как InfrastructureError."""
        with pytest.raises(InfrastructureError):
            raise DatabaseError("Database error")


class TestExternalServiceError:
    """Тесты для исключения ExternalServiceError."""

    def test_external_service_error_without_metadata(self) -> None:
        """ExternalServiceError без метаданных."""
        error = ExternalServiceError("API timeout")
        assert error.message == "API timeout"
        assert error.service_name is None
        assert error.status_code is None
        assert "ExternalServiceError" in str(error)

    def test_external_service_error_with_service_name(self) -> None:
        """ExternalServiceError с указанием имени сервиса."""
        error = ExternalServiceError("Rate limit exceeded", service_name="Telegram API")
        assert error.message == "Rate limit exceeded"
        assert error.service_name == "Telegram API"
        assert error.status_code is None
        assert "service='Telegram API'" in str(error)

    def test_external_service_error_with_status_code(self) -> None:
        """ExternalServiceError с указанием status code."""
        error = ExternalServiceError("Not Found", service_name="Webhook", status_code=404)
        assert error.message == "Not Found"
        assert error.service_name == "Webhook"
        assert error.status_code == 404
        assert "service='Webhook'" in str(error)
        assert "status=404" in str(error)

    def test_external_service_error_inherits_from_infrastructure_error(self) -> None:
        """ExternalServiceError наследуется от InfrastructureError."""
        error = ExternalServiceError("Test")
        assert isinstance(error, InfrastructureError)

    def test_external_service_error_can_be_caught_as_infrastructure_error(self) -> None:
        """ExternalServiceError может быть поймано как InfrastructureError."""
        with pytest.raises(InfrastructureError):
            raise ExternalServiceError("External service error")


class TestFileStorageError:
    """Тесты для исключения FileStorageError."""

    def test_file_storage_error_without_path(self) -> None:
        """FileStorageError без указания пути к файлу."""
        error = FileStorageError("Disk full")
        assert error.message == "Disk full"
        assert error.file_path is None
        assert "FileStorageError" in str(error)

    def test_file_storage_error_with_path(self) -> None:
        """FileStorageError с указанием пути к файлу."""
        path = "/data/uploads/file.json"
        error = FileStorageError("Permission denied", file_path=path)
        assert error.message == "Permission denied"
        assert error.file_path == path
        assert f"path={path!r}" in str(error)

    def test_file_storage_error_inherits_from_infrastructure_error(self) -> None:
        """FileStorageError наследуется от InfrastructureError."""
        error = FileStorageError("Test")
        assert isinstance(error, InfrastructureError)

    def test_file_storage_error_can_be_caught_as_infrastructure_error(self) -> None:
        """FileStorageError может быть поймано как InfrastructureError."""
        with pytest.raises(InfrastructureError):
            raise FileStorageError("File storage error")


class TestInfrastructureExceptionHierarchy:
    """Тесты для проверки иерархии исключений infrastructure слоя."""

    def test_all_infrastructure_exceptions_are_catchable(self) -> None:
        """Все infrastructure исключения могут быть пойманы как InfrastructureError."""
        exceptions = [
            DatabaseError("test"),
            ExternalServiceError("test"),
            FileStorageError("test"),
        ]

        for exc in exceptions:
            with pytest.raises(InfrastructureError):
                raise exc

    def test_database_error_is_subclass_of_infrastructure_error(self) -> None:
        """DatabaseError является подклассом InfrastructureError."""
        assert issubclass(DatabaseError, InfrastructureError)

    def test_external_service_error_is_subclass_of_infrastructure_error(self) -> None:
        """ExternalServiceError является подклассом InfrastructureError."""
        assert issubclass(ExternalServiceError, InfrastructureError)

    def test_file_storage_error_is_subclass_of_infrastructure_error(self) -> None:
        """FileStorageError является подклассом InfrastructureError."""
        assert issubclass(FileStorageError, InfrastructureError)
