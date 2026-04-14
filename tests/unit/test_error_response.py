"""
Тесты для моделей ErrorResponse и ErrorDetail.

Проверяет обязательные и опциональные поля, сериализацию
и соответствие стандартному envelope-формату.
"""


from src.api.models import ErrorDetail, ErrorResponse


class TestErrorResponseRequiredFields:
    """Тесты обязательных полей ErrorResponse."""

    def test_error_response_required_fields(self) -> None:
        """code и message обязательны."""
        error = ErrorResponse(
            error=ErrorDetail(code="APP-101", message="Internal server error"),
        )
        assert error.error.code == "APP-101"
        assert error.error.message == "Internal server error"


class TestErrorResponseOptionalField:
    """Тесты опционального поля field."""

    def test_error_response_with_field(self) -> None:
        """field опционален, serializes."""
        error = ErrorResponse(
            error=ErrorDetail(code="APP-102", message="Validation error"),
            field="timezone",
        )
        assert error.field == "timezone"
        dumped = error.model_dump()
        assert dumped["field"] == "timezone"


class TestErrorResponseOptionalRuleCode:
    """Тесты опционального поля rule_code."""

    def test_error_response_with_rule_code(self) -> None:
        """rule_code опционален."""
        error = ErrorResponse(
            error=ErrorDetail(code="APP-104", message="Business rule error"),
            rule_code="BR-001",
        )
        assert error.rule_code == "BR-001"


class TestErrorResponseOptionalRetryAfter:
    """Тесты опционального поля retry_after_seconds."""

    def test_error_response_with_retry_after(self) -> None:
        """retry_after_seconds опционален."""
        error = ErrorResponse(
            error=ErrorDetail(code="RATE-002", message="Rate limit exceeded"),
            retry_after_seconds=60,
        )
        assert error.retry_after_seconds == 60


class TestErrorResponseEnvelope:
    """Тесты envelope-формата сериализации."""

    def test_error_response_model_dump_matches_envelope(self) -> None:
        """model_dump() = {"error": {"code": ..., "message": ...}}."""
        error = ErrorResponse(
            error=ErrorDetail(code="APP-101", message="Internal server error"),
        )
        dumped = error.model_dump()
        assert "error" in dumped
        assert dumped["error"]["code"] == "APP-101"
        assert dumped["error"]["message"] == "Internal server error"


class TestErrorResponseAllOptionalFields:
    """Тесты всех опциональных полей одновременно."""

    def test_error_response_all_optional_fields(self) -> None:
        """Все optional поля одновременно."""
        error = ErrorResponse(
            error=ErrorDetail(code="APP-102", message="Validation error"),
            field="some_field",
            rule_code="BR-042",
            retry_after_seconds=30,
        )
        dumped = error.model_dump()
        assert dumped["error"]["code"] == "APP-102"
        assert dumped["field"] == "some_field"
        assert dumped["rule_code"] == "BR-042"
        assert dumped["retry_after_seconds"] == 30
