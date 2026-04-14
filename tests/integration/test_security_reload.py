"""
Интеграционный тест concurrent reload настроек.

Проверяется:
- Два concurrent PUT запроса выполняются последовательно благодаря asyncio.Lock
- Оба запроса возвращают 200
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.integration


class MockLoadSettings:
    """Мок-функция загрузки настроек с логом выполнения."""

    def __init__(self) -> None:
        self.execution_log: list[str] = []
        self._load_call_count = 0

    async def __call__(self) -> MagicMock:
        self._load_call_count += 1
        self.execution_log.append(f"load_start_{self._load_call_count}")
        await asyncio.sleep(0.05)
        self.execution_log.append(f"load_end_{self._load_call_count}")

        mock_settings = MagicMock()
        mock_settings.db_password = "test_secret"
        mock_settings.tg_api_id = 12345
        mock_settings.tg_api_hash = "valid_hash_32_chars_long_string_here"
        mock_settings.get_provider_config.return_value = MagicMock(
            name="ollama",
            api_key=None,
            base_url="http://localhost:11434",
            model="test-model",
        )
        return mock_settings

    @property
    def call_count(self) -> int:
        return self._load_call_count


@pytest.fixture
def mock_load_settings() -> MockLoadSettings:
    """Фикстура с мок-функцией загрузки настроек и логом выполнения."""
    return MockLoadSettings()


@pytest.fixture
def reload_test_app() -> FastAPI:
    """Фикстура с тестовым приложением и endpoint для reload."""
    router = APIRouter()

    @router.put("/test-reload")
    async def test_reload_endpoint() -> dict[str, str]:
        from src.config.loader import reload_settings

        await reload_settings()
        return {"status": "ok"}

    application = FastAPI()
    application.include_router(router)

    return application


@pytest.mark.asyncio
async def test_concurrent_reload_executes_sequentially(
    mock_load_settings: MockLoadSettings,
    reload_test_app: FastAPI,
) -> None:
    """Два concurrent PUT запроса к reload выполняются последовательно."""
    with (
        patch("src.config.loader.load_settings_from_db", new=mock_load_settings),
        patch("src.config.settings.get_settings") as mock_get,
    ):
        mock_get.cache_clear = MagicMock()

        transport = ASGITransport(app=reload_test_app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            results = await asyncio.gather(
                client.put("/test-reload"),
                client.put("/test-reload"),
            )

    assert results[0].status_code == 200
    assert results[1].status_code == 200
    assert mock_load_settings.call_count == 2

    start_indices = [
        i for i, entry in enumerate(mock_load_settings.execution_log)
        if entry.startswith("load_start")
    ]
    end_indices = [
        i for i, entry in enumerate(mock_load_settings.execution_log)
        if entry.startswith("load_end")
    ]

    for i in range(len(start_indices) - 1):
        assert end_indices[i] < start_indices[i + 1], (
            f"Вызов {i + 2} начался до завершения вызова {i + 1}"
        )
