"""
Тесты для иерархии исключений domain слоя.

Проверяет корректность работы исключений DomainError, ValidationError,
BusinessRuleError и NotFoundError.
"""

import pytest

from src.domain.exceptions import (
    BusinessRuleError,
    DomainError,
    NotFoundError,
    ValidationError,
)


class TestDomainError:
    """Тесты для базового исключения DomainError."""

    def test_domain_error_creation(self) -> None:
        """DomainError может быть создано с сообщением."""
        error = DomainError("Test error message")
        assert error.message == "Test error message"
        assert str(error) == "Test error message"

    def test_domain_error_inherits_from_exception(self) -> None:
        """DomainError наследуется от Exception."""
        error = DomainError("Test")
        assert isinstance(error, Exception)

    def test_domain_error_can_be_raised(self) -> None:
        """DomainError может быть выброшено и поймано."""
        with pytest.raises(DomainError) as exc_info:
            raise DomainError("Domain error occurred")
        assert exc_info.value.message == "Domain error occurred"


class TestValidationError:
    """Тесты для исключения ValidationError."""

    def test_validation_error_without_field(self) -> None:
        """ValidationError без указания поля."""
        error = ValidationError("Invalid value")
        assert error.message == "Invalid value"
        assert error.field is None
        assert "ValidationError" in str(error)
        assert "Invalid value" in str(error)

    def test_validation_error_with_field(self) -> None:
        """ValidationError с указанием поля."""
        error = ValidationError("Cannot be empty", field="username")
        assert error.message == "Cannot be empty"
        assert error.field == "username"
        assert "field='username'" in str(error)

    def test_validation_error_inherits_from_domain_error(self) -> None:
        """ValidationError наследуется от DomainError."""
        error = ValidationError("Test")
        assert isinstance(error, DomainError)

    def test_validation_error_can_be_caught_as_domain_error(self) -> None:
        """ValidationError может быть поймано как DomainError."""
        with pytest.raises(DomainError):
            raise ValidationError("Validation failed")

    def test_validation_error_in_value_object(self) -> None:
        """ValidationError выбрасывается в Value Object."""
        from src.domain.value_objects import ApiId

        with pytest.raises(ValidationError) as exc_info:
            ApiId(-1)
        assert exc_info.value.field == "value"
        assert "положительным" in exc_info.value.message


class TestBusinessRuleError:
    """Тесты для исключения BusinessRuleError."""

    def test_business_rule_error_without_code(self) -> None:
        """BusinessRuleError без кода правила."""
        error = BusinessRuleError("Rule violated")
        assert error.message == "Rule violated"
        assert error.rule_code is None
        assert "BusinessRuleError" in str(error)

    def test_business_rule_error_with_code(self) -> None:
        """BusinessRuleError с кодом правила."""
        error = BusinessRuleError("Cannot delete active chat", rule_code="CHAT-001")
        assert error.message == "Cannot delete active chat"
        assert error.rule_code == "CHAT-001"
        assert "code='CHAT-001'" in str(error)

    def test_business_rule_error_inherits_from_domain_error(self) -> None:
        """BusinessRuleError наследуется от DomainError."""
        error = BusinessRuleError("Test")
        assert isinstance(error, DomainError)

    def test_business_rule_error_can_be_caught_as_domain_error(self) -> None:
        """BusinessRuleError может быть поймано как DomainError."""
        with pytest.raises(DomainError):
            raise BusinessRuleError("Business rule violated")


class TestNotFoundError:
    """Тесты для исключения NotFoundError."""

    def test_not_found_error_creation(self) -> None:
        """NotFoundError с указанием типа сущности (identifier скрыт для безопасности)."""
        error = NotFoundError("Chat", "12345")
        assert error.entity_type == "Chat"
        assert error.identifier == "12345"
        assert "Chat" in str(error)
        # identifier не включается в str() для предотвращения information disclosure

    def test_not_found_error_message_format(self) -> None:
        """Формат сообщения NotFoundError (без identifier для безопасности)."""
        error = NotFoundError("Message", "abc-123")
        expected_message = "Message не найден"
        assert error.message == expected_message

    def test_not_found_error_inherits_from_domain_error(self) -> None:
        """NotFoundError наследуется от DomainError."""
        error = NotFoundError("Entity", "id")
        assert isinstance(error, DomainError)

    def test_not_found_error_can_be_caught_as_domain_error(self) -> None:
        """NotFoundError может быть поймано как DomainError."""
        with pytest.raises(DomainError):
            raise NotFoundError("User", "unknown")


class TestExceptionHierarchy:
    """Тесты для проверки иерархии исключений."""

    def test_all_domain_exceptions_are_catchable(self) -> None:
        """Все domain исключения могут быть пойманы как DomainError."""
        exceptions = [
            ValidationError("test"),
            BusinessRuleError("test"),
            NotFoundError("Entity", "id"),
        ]

        for exc in exceptions:
            with pytest.raises(DomainError):
                raise exc

    def test_validation_error_is_subclass_of_domain_error(self) -> None:
        """ValidationError является подклассом DomainError."""
        assert issubclass(ValidationError, DomainError)

    def test_business_rule_error_is_subclass_of_domain_error(self) -> None:
        """BusinessRuleError является подклассом DomainError."""
        assert issubclass(BusinessRuleError, DomainError)

    def test_not_found_error_is_subclass_of_domain_error(self) -> None:
        """NotFoundError является подклассом DomainError."""
        assert issubclass(NotFoundError, DomainError)
