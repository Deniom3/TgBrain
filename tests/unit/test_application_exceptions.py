"""
Тесты для иерархии исключений application слоя.

Проверяет корректность работы исключений ApplicationError, UseCaseError,
ServiceUnavailableError и DuplicateError.
"""

import pytest

from src.application.exceptions import (
    ApplicationError,
    DuplicateError,
    ServiceUnavailableError,
    UseCaseError,
)


class TestApplicationError:
    """Тесты для базового исключения ApplicationError."""

    def test_application_error_creation(self) -> None:
        """ApplicationError может быть создано с сообщением."""
        error = ApplicationError("Test error message")
        assert error.message == "Test error message"
        assert str(error) == "Test error message"

    def test_application_error_inherits_from_exception(self) -> None:
        """ApplicationError наследуется от Exception."""
        error = ApplicationError("Test")
        assert isinstance(error, Exception)

    def test_application_error_can_be_raised(self) -> None:
        """ApplicationError может быть выброшено и поймано."""
        with pytest.raises(ApplicationError) as exc_info:
            raise ApplicationError("Application error occurred")
        assert exc_info.value.message == "Application error occurred"


class TestUseCaseError:
    """Тесты для исключения UseCaseError."""

    def test_use_case_error_without_name(self) -> None:
        """UseCaseError без указания имени use case."""
        error = UseCaseError("Use case failed")
        assert error.message == "Use case failed"
        assert error.use_case_name is None
        assert "UseCaseError" in str(error)

    def test_use_case_error_with_name(self) -> None:
        """UseCaseError с указанием имени use case."""
        error = UseCaseError("Invalid input data", use_case_name="GenerateSummary")
        assert error.message == "Invalid input data"
        assert error.use_case_name == "GenerateSummary"
        assert "use_case='GenerateSummary'" in str(error)

    def test_use_case_error_inherits_from_application_error(self) -> None:
        """UseCaseError наследуется от ApplicationError."""
        error = UseCaseError("Test")
        assert isinstance(error, ApplicationError)

    def test_use_case_error_can_be_caught_as_application_error(self) -> None:
        """UseCaseError может быть поймано как ApplicationError."""
        with pytest.raises(ApplicationError):
            raise UseCaseError("Use case failed")


class TestServiceUnavailableError:
    """Тесты для исключения ServiceUnavailableError."""

    def test_service_unavailable_error_without_name(self) -> None:
        """ServiceUnavailableError без указания имени сервиса."""
        error = ServiceUnavailableError("Service is down")
        assert error.message == "Service is down"
        assert error.service_name is None
        assert "ServiceUnavailableError" in str(error)

    def test_service_unavailable_error_with_name(self) -> None:
        """ServiceUnavailableError с указанием имени сервиса."""
        error = ServiceUnavailableError("Connection timeout", service_name="LLM Provider")
        assert error.message == "Connection timeout"
        assert error.service_name == "LLM Provider"
        assert "service='LLM Provider'" in str(error)

    def test_service_unavailable_error_inherits_from_application_error(self) -> None:
        """ServiceUnavailableError наследуется от ApplicationError."""
        error = ServiceUnavailableError("Test")
        assert isinstance(error, ApplicationError)

    def test_service_unavailable_error_can_be_caught_as_application_error(self) -> None:
        """ServiceUnavailableError может быть поймано как ApplicationError."""
        with pytest.raises(ApplicationError):
            raise ServiceUnavailableError("Service unavailable")


class TestDuplicateError:
    """Тесты для исключения DuplicateError."""

    def test_duplicate_error_without_entity_type(self) -> None:
        """DuplicateError без указания типа сущности."""
        error = DuplicateError("Record already exists")
        assert error.message == "Record already exists"
        assert error.entity_type is None
        assert "DuplicateError" in str(error)

    def test_duplicate_error_with_entity_type(self) -> None:
        """DuplicateError с указанием типа сущности."""
        error = DuplicateError("Chat with this ID already exists", entity_type="Chat")
        assert error.message == "Chat with this ID already exists"
        assert error.entity_type == "Chat"
        assert "entity='Chat'" in str(error)

    def test_duplicate_error_inherits_from_application_error(self) -> None:
        """DuplicateError наследуется от ApplicationError."""
        error = DuplicateError("Test")
        assert isinstance(error, ApplicationError)

    def test_duplicate_error_can_be_caught_as_application_error(self) -> None:
        """DuplicateError может быть поймано как ApplicationError."""
        with pytest.raises(ApplicationError):
            raise DuplicateError("Duplicate record")


class TestApplicationExceptionHierarchy:
    """Тесты для проверки иерархии исключений application слоя."""

    def test_all_application_exceptions_are_catchable(self) -> None:
        """Все application исключения могут быть пойманы как ApplicationError."""
        exceptions = [
            UseCaseError("test"),
            ServiceUnavailableError("test"),
            DuplicateError("test"),
        ]

        for exc in exceptions:
            with pytest.raises(ApplicationError):
                raise exc

    def test_use_case_error_is_subclass_of_application_error(self) -> None:
        """UseCaseError является подклассом ApplicationError."""
        assert issubclass(UseCaseError, ApplicationError)

    def test_service_unavailable_error_is_subclass_of_application_error(self) -> None:
        """ServiceUnavailableError является подклассом ApplicationError."""
        assert issubclass(ServiceUnavailableError, ApplicationError)

    def test_duplicate_error_is_subclass_of_application_error(self) -> None:
        """DuplicateError является подклассом ApplicationError."""
        assert issubclass(DuplicateError, ApplicationError)
