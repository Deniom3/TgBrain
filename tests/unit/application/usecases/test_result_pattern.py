"""Тесты для паттерна Result[T, E]."""

import pytest

from src.application.exceptions import UseCaseError
from src.application.usecases.result import Failure, Result, Success


class TestSuccess:
    def test_success_creates_with_value(self) -> None:
        success: Success[int, str] = Success(42)
        assert success.value == 42

    def test_success_is_success_true(self) -> None:
        result: Result[int, str] = Success(42)
        assert result.is_success is True

    def test_success_is_failure_false(self) -> None:
        result: Result[int, str] = Success(42)
        assert result.is_failure is False

    def test_success_unwrap_returns_value(self) -> None:
        result: Result[str, Exception] = Success("hello")
        unwrapped = result.unwrap(use_case_name="TestUseCase")
        assert unwrapped == "hello"


class TestFailure:
    def test_failure_creates_with_error(self) -> None:
        failure: Failure[int, str] = Failure("error message")
        assert failure.error == "error message"

    def test_failure_is_failure_true(self) -> None:
        result: Result[int, str] = Failure("error message")
        assert result.is_failure is True

    def test_failure_is_success_false(self) -> None:
        result: Result[int, str] = Failure("error message")
        assert result.is_success is False

    def test_failure_unwrap_raises_exception(self) -> None:
        result: Result[int, str] = Failure("something went wrong")
        with pytest.raises(UseCaseError, match="something went wrong"):
            result.unwrap(use_case_name="TestUseCase")
