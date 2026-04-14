"""Тесты для AppStateStore."""

from unittest.mock import MagicMock

import pytest

from src.common.application_state import AppStateStore


@pytest.fixture(autouse=True)
def reset_app_state_store() -> None:
    """Сбрасывает AppStateStore перед каждым тестом."""
    AppStateStore.reset()


class TestAppStateStoreNotInitialized:
    """Тесты поведения при неинициализированном хранилище."""

    def test_get_app_before_set_raises(self) -> None:
        """get_app до set вызывает RuntimeError."""
        with pytest.raises(RuntimeError) as exc_info:
            AppStateStore.get_app()

        assert "не инициализирован" in str(exc_info.value)

    def test_is_initialized_false_before_set(self) -> None:
        """is_initialized возвращает False до set."""
        result = AppStateStore.is_initialized()

        assert result is False


class TestAppStateStoreSetAndGet:
    """Тесты установки и получения app."""

    async def test_set_and_get_app(self) -> None:
        """Установка и получение app работает."""
        mock_app = MagicMock()

        await AppStateStore.set(mock_app)
        result = AppStateStore.get_app()

        assert result is mock_app

    async def test_is_initialized_true_after_set(self) -> None:
        """is_initialized возвращает True после set."""
        mock_app = MagicMock()

        await AppStateStore.set(mock_app)

        assert AppStateStore.is_initialized() is True


class TestAppStateStoreGetState:
    """Тесты получения app.state."""

    async def test_get_state_returns_app_state(self) -> None:
        """get_state возвращает app.state."""
        mock_app = MagicMock()

        await AppStateStore.set(mock_app)
        result = AppStateStore.get_state()

        assert result is mock_app.state

    async def test_get_state_before_set_raises(self) -> None:
        """get_state до set вызывает RuntimeError."""
        with pytest.raises(RuntimeError):
            AppStateStore.get_state()


class TestAppStateStoreReset:
    """Тесты сброса хранилища."""

    async def test_reset_clears_app(self) -> None:
        """reset очищает хранилище."""
        mock_app = MagicMock()

        await AppStateStore.set(mock_app)
        AppStateStore.reset()

        assert AppStateStore.is_initialized() is False

    async def test_reset_makes_get_app_raise(self) -> None:
        """После reset get_app вызывает RuntimeError."""
        mock_app = MagicMock()

        await AppStateStore.set(mock_app)
        AppStateStore.reset()

        with pytest.raises(RuntimeError):
            AppStateStore.get_app()
