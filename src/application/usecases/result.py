"""Универсальный паттерн Result[T, E] для UseCase-классов.

Обеспечивает типизированное представление успешного результата
или ошибки без использования исключений для управляющего потока.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from src.application.exceptions import UseCaseError

T = TypeVar("T")
E = TypeVar("E")


class Result(ABC, Generic[T, E]):
    """Базовый абстрактный класс для паттерна Result[T, E]."""

    @property
    @abstractmethod
    def is_success(self) -> bool:
        """Возвращает True, если результат успешен."""

    @property
    @abstractmethod
    def is_failure(self) -> bool:
        """Возвращает True, если результат содержит ошибку."""

    @abstractmethod
    def unwrap(self, use_case_name: str) -> T:
        """Возвращает значение для Success или вызывает UseCaseError для Failure."""


class Success(Result[T, E]):
    """Успешный результат, содержащий значение типа T."""

    def __init__(self, value: T) -> None:
        self.value: T = value

    @property
    def is_success(self) -> bool:
        return True

    @property
    def is_failure(self) -> bool:
        return False

    def unwrap(self, use_case_name: str) -> T:
        del use_case_name
        return self.value

    def __repr__(self) -> str:
        return f"Success({self.value!r})"


class Failure(Result[T, E]):
    """Результат с ошибкой, содержащий значение типа E."""

    def __init__(self, error: E) -> None:
        self.error: E = error

    @property
    def is_success(self) -> bool:
        return False

    @property
    def is_failure(self) -> bool:
        return True

    def unwrap(self, use_case_name: str) -> T:
        """Возвращает значение для Success или вызывает UseCaseError для Failure.

        Args:
            use_case_name: Имя UseCase-класса для контекста ошибки.
        """
        raise UseCaseError(
            message=str(self.error),
            use_case_name=use_case_name,
        )

    def __repr__(self) -> str:
        return f"Failure({self.error!r})"
