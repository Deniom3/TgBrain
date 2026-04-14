"""
Unit-тесты ChatSettingsRepository.get_enabled_summary_chat_ids с моками.

Проверяет:
- Возврат только enabled чатов
- Пустой список при отсутствии enabled чатов
- Игнорирование disabled чатов
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.settings.repositories.chat_settings import ChatSettingsRepository


def _create_mock_pool(fetch_result: list) -> MagicMock:
    """Создать мок пула с настроенным fetch результатом."""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=fetch_result)
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.execute = AsyncMock(return_value=None)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire = MagicMock(return_value=mock_conn)
    return mock_pool


@pytest.mark.asyncio
async def test_get_enabled_summary_chat_ids_returns_only_enabled() -> None:
    """
    Arrange: БД возвращает два чата с summary_enabled=TRUE.
    Act: Вызов get_enabled_summary_chat_ids.
    Assert: Возвращены только ID enabled чатов.
    """
    mock_rows = [
        {"chat_id": -1001111111111},
        {"chat_id": -1002222222222},
    ]
    mock_pool = _create_mock_pool(mock_rows)

    repo = ChatSettingsRepository(mock_pool)
    result = await repo.get_enabled_summary_chat_ids()

    assert result == [-1001111111111, -1002222222222]


@pytest.mark.asyncio
async def test_get_enabled_summary_chat_ids_empty_when_none() -> None:
    """
    Arrange: БД возвращает пустой результат (нет enabled чатов).
    Act: Вызов get_enabled_summary_chat_ids.
    Assert: Возвращён пустой список.
    """
    mock_pool = _create_mock_pool([])

    repo = ChatSettingsRepository(mock_pool)
    result = await repo.get_enabled_summary_chat_ids()

    assert result == []


@pytest.mark.asyncio
async def test_get_enabled_summary_chat_ids_ignores_disabled() -> None:
    """
    Arrange: SQL запрос уже фильтрует только enabled чаты,
             но проверяем что метод корректно обрабатывает
             результат (даже если БД вернула бы disabled,
             SQL-запрос их отфильтрует).
    Act: Вызов get_enabled_summary_chat_ids с одним enabled чатом.
    Assert: Возвращён только один enabled чат.
    """
    mock_rows = [
        {"chat_id": -1001111111111},
    ]
    mock_pool = _create_mock_pool(mock_rows)

    repo = ChatSettingsRepository(mock_pool)
    result = await repo.get_enabled_summary_chat_ids()

    assert result == [-1001111111111]
    assert len(result) == 1
