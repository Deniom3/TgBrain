"""
Unit-тесты ChatSettingsRepository: фильтр-методы update и get_chat_filter_configs.

Проверяет:
- update(chat_id, filter_bots=False) → dynamic SQL содержит filter_bots
- update(chat_id, filter_bots=None) → dynamic SQL НЕ содержит filter_bots
- get_chat_filter_configs() → возвращает dict[int, ChatFilterConfig]
- update(chat_id, ...) со всеми 4 фильтр-полями → все поля в SQL
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.models.chat_filter_config import ChatFilterConfig
from src.settings.repositories.chat_settings import ChatSettingsRepository


def _make_existing_row(chat_id: int = -1001111111111) -> dict:
    """Создать мок-строку существующей записи chat_settings."""
    return {
        "id": 1,
        "chat_id": chat_id,
        "title": "test-chat",
        "type": "group",
        "last_message_id": 0,
        "is_monitored": True,
        "summary_enabled": True,
        "summary_period_minutes": 1440,
        "summary_schedule": None,
        "custom_prompt": None,
        "webhook_config": None,
        "webhook_enabled": False,
        "filter_bots": True,
        "filter_actions": True,
        "filter_min_length": 15,
        "filter_ads": True,
        "next_schedule_run": None,
        "created_at": None,
        "updated_at": None,
    }


def _create_mock_pool_with_update(
    existing_row: dict | None = None,
    updated_row: dict | None = None,
) -> MagicMock:
    """Создать мок пула с настройенным fetchrow для update-сценария.

    Первый вызов fetchrow (SELECT) возвращает existing_row.
    Второй вызов fetchrow (UPDATE) возвращает updated_row.
    """
    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    if existing_row is not None:
        mock_record = MagicMock()
        mock_record.__iter__ = lambda self: iter(existing_row.items())
        mock_conn.fetchrow = AsyncMock(side_effect=[existing_row, updated_row])
    else:
        mock_conn.fetchrow = AsyncMock(side_effect=[None])

    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.execute = AsyncMock(return_value=None)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_conn)
    return mock_pool


def _create_mock_pool_for_filter_configs(
    filter_rows: list[dict],
) -> MagicMock:
    """Создать мок пула с настроенным fetch для get_chat_filter_configs."""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    mock_records = []
    for row_data in filter_rows:
        mock_record = MagicMock()
        for key, value in row_data.items():
            mock_record.__getitem__ = lambda self, k=key, v=value, **_: v if k == self else None
        mock_records.append(row_data)

    mock_conn.fetch = AsyncMock(return_value=filter_rows)
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.execute = AsyncMock(return_value=None)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_conn)
    return mock_pool


@pytest.mark.asyncio
async def test_update_filter_bots_false_contains_in_sql() -> None:
    """
    Arrange: существующая запись, update с filter_bots=False.
    Act: вызов update(chat_id, filter_bots=False).
    Assert: SQL, переданный в fetchrow, содержит filter_bots = $N.
    """
    chat_id = -1001111111111
    existing_row = _make_existing_row(chat_id)
    updated_row = {**existing_row, "filter_bots": False}
    mock_pool = _create_mock_pool_with_update(existing_row, updated_row)

    repo = ChatSettingsRepository(mock_pool)
    await repo.update(chat_id, filter_bots=False)

    mock_conn = await mock_pool.acquire().__aenter__()
    update_call_args = mock_conn.fetchrow.call_args_list[1]
    sql_arg = update_call_args[0][0]

    assert "filter_bots = $" in sql_arg


@pytest.mark.asyncio
async def test_update_filter_none_skips_field() -> None:
    """
    Arrange: существующая запись, update с filter_bots=None (пропуск).
    Act: вызов update(chat_id, filter_bots=None).
    Assert: SQL, переданный в fetchrow, НЕ содержит filter_bots.
    """
    chat_id = -1001111111111
    existing_row = _make_existing_row(chat_id)

    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    mock_conn.fetchrow = AsyncMock(side_effect=[existing_row])
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.execute = AsyncMock(return_value=None)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_conn)

    repo = ChatSettingsRepository(mock_pool)
    await repo.update(chat_id, filter_bots=None)

    assert mock_conn.fetchrow.call_count == 1
    first_call_sql = mock_conn.fetchrow.call_args_list[0][0][0]
    assert "filter_bots" not in first_call_sql


@pytest.mark.asyncio
async def test_get_chat_filter_configs_returns_dict() -> None:
    """
    Arrange: БД возвращает две записи с фильтр-конфигами.
    Act: вызов get_chat_filter_configs().
    Assert: возвращён dict[int, ChatFilterConfig] с корректными значениями.
    """
    filter_rows = [
        {
            "chat_id": -1001111111111,
            "filter_bots": False,
            "filter_actions": True,
            "filter_min_length": 10,
            "filter_ads": True,
        },
        {
            "chat_id": -1002222222222,
            "filter_bots": True,
            "filter_actions": False,
            "filter_min_length": 0,
            "filter_ads": False,
        },
    ]
    mock_pool = _create_mock_pool_for_filter_configs(filter_rows)

    repo = ChatSettingsRepository(mock_pool)
    result = await repo.get_chat_filter_configs()

    assert isinstance(result, dict)
    assert len(result) == 2
    assert -1001111111111 in result
    assert -1002222222222 in result
    assert isinstance(result[-1001111111111], ChatFilterConfig)
    assert result[-1001111111111].filter_bots is False
    assert result[-1001111111111].filter_actions is True
    assert result[-1001111111111].filter_min_length == 10
    assert result[-1001111111111].filter_ads is True
    assert result[-1002222222222].filter_bots is True
    assert result[-1002222222222].filter_ads is False


@pytest.mark.asyncio
async def test_update_all_filter_params_in_sql() -> None:
    """
    Arrange: существующая запись, update со всеми 4 фильтр-полями.
    Act: вызов update(chat_id, filter_bots=False, filter_actions=False,
                       filter_min_length=0, filter_ads=False).
    Assert: SQL содержит все 4 поля: filter_bots, filter_actions,
            filter_min_length, filter_ads.
    """
    chat_id = -1001111111111
    existing_row = _make_existing_row(chat_id)
    updated_row = {
        **existing_row,
        "filter_bots": False,
        "filter_actions": False,
        "filter_min_length": 0,
        "filter_ads": False,
    }
    mock_pool = _create_mock_pool_with_update(existing_row, updated_row)

    repo = ChatSettingsRepository(mock_pool)
    await repo.update(
        chat_id,
        filter_bots=False,
        filter_actions=False,
        filter_min_length=0,
        filter_ads=False,
    )

    mock_conn = await mock_pool.acquire().__aenter__()
    update_call_args = mock_conn.fetchrow.call_args_list[1]
    sql_arg = update_call_args[0][0]

    assert "filter_bots = $" in sql_arg
    assert "filter_actions = $" in sql_arg
    assert "filter_min_length = $" in sql_arg
    assert "filter_ads = $" in sql_arg
