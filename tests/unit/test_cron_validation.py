"""
Тесты валидации cron выражений в set_summary_schedule endpoint.

Покрывает:
- Валидный cron выражение — HTTP 200
- Невалидные значения "99 99 99 99 99" — HTTP 400
- Невалидный синтаксис — HTTP 400
- Валидный HH:MM формат — HTTP 200
"""

from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.settings.repositories.chat_settings import ChatSettingsRepository


@pytest.fixture
def schedule_app() -> FastAPI:
    """Создать тестовое приложение только с summary schedule роутами."""
    from src.settings_api.chat_summary_settings_endpoints import (
        get_chat_settings_repo,
        router as schedule_router,
    )

    app = FastAPI(title="Schedule Test")
    app.state.timezone = "Etc/UTC"

    mock_repo = AsyncMock(spec=ChatSettingsRepository)
    mock_setting = MagicMock()
    mock_setting.summary_enabled = True
    mock_repo.set_summary_schedule = AsyncMock(return_value=mock_setting)
    mock_repo.update_next_schedule_run = AsyncMock(return_value=None)
    app.state.chat_settings_repo = mock_repo

    async def override_repo() -> ChatSettingsRepository:
        return mock_repo

    app.dependency_overrides[get_chat_settings_repo] = override_repo
    app.include_router(schedule_router)

    return app


@pytest.fixture
async def schedule_client(schedule_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """HTTP клиент для тестирования schedule endpoints."""
    transport = ASGITransport(app=schedule_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestSetSummaryScheduleValidation:
    """Тесты валидации расписания перед сохранением."""

    @pytest.mark.asyncio
    async def test_valid_hhmm_format_returns_200(
        self, schedule_client: AsyncClient, schedule_app: FastAPI,
    ) -> None:
        """Валидный HH:MM формат должен вернуть HTTP 200."""
        response = await schedule_client.put(
            "/chats/123/summary/schedule",
            json={"schedule": "09:00"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["chat_id"] == 123

        mock_repo = schedule_app.state.chat_settings_repo
        mock_repo.set_summary_schedule.assert_called_once()

    @pytest.mark.asyncio
    async def test_valid_cron_expression_returns_200(
        self, schedule_client: AsyncClient, schedule_app: FastAPI,
    ) -> None:
        """Валидный cron формат должен вернуть HTTP 200."""
        response = await schedule_client.put(
            "/chats/123/summary/schedule",
            json={"schedule": "0 9 * * 1"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["chat_id"] == 123

        mock_repo = schedule_app.state.chat_settings_repo
        mock_repo.set_summary_schedule.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_cron_values_returns_400(
        self, schedule_client: AsyncClient, schedule_app: FastAPI,
    ) -> None:
        """Cron с невалидными значениями 99 99 99 99 99 должен вернуть HTTP 400."""
        response = await schedule_client.put(
            "/chats/123/summary/schedule",
            json={"schedule": "99 99 99 99 99"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

        mock_repo = schedule_app.state.chat_settings_repo
        mock_repo.set_summary_schedule.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_cron_syntax_returns_400(
        self, schedule_client: AsyncClient, schedule_app: FastAPI,
    ) -> None:
        """Cron с невалидным синтаксисом должен вернуть HTTP 400."""
        response = await schedule_client.put(
            "/chats/123/summary/schedule",
            json={"schedule": "abc def"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

        mock_repo = schedule_app.state.chat_settings_repo
        mock_repo.set_summary_schedule.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_cron_interval_returns_400(
        self, schedule_client: AsyncClient, schedule_app: FastAPI,
    ) -> None:
        """Cron с невалидным интервалом */0 должен вернуть HTTP 400."""
        response = await schedule_client.put(
            "/chats/123/summary/schedule",
            json={"schedule": "*/0"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

        mock_repo = schedule_app.state.chat_settings_repo
        mock_repo.set_summary_schedule.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_format_returns_400(
        self, schedule_client: AsyncClient, schedule_app: FastAPI,
    ) -> None:
        """Полностью невалидный формат должен вернуть HTTP 400 на regex уровне."""
        response = await schedule_client.put(
            "/chats/123/summary/schedule",
            json={"schedule": "hello world!"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

        mock_repo = schedule_app.state.chat_settings_repo
        mock_repo.set_summary_schedule.assert_not_called()
