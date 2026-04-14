"""
Database fixtures для тестирования TgBrain.

Содержит фикстуры для работы с БД:
- Мок пула подключений (включая helper _create_mock_pool)
- Реальное подключение (integration тесты)
- Настройки тестовой БД
"""

from __future__ import annotations

import os
import secrets
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import urlparse

import asyncpg
import pytest

__all__ = [
    "db_pool",
    "integration_tests_enabled",
    "mock_db_pool",
    "db_pool_with_session_data",
    "real_db_pool",
    "_create_mock_pool",
    "_is_production_url",
]


def _is_production_url(url: str) -> bool:
    """Строгая проверка что URL не указывает на production БД."""
    url_lower = url.lower()

    prod_keywords = ["production", "prod", "live", "main"]
    for keyword in prod_keywords:
        if keyword in url_lower:
            return True

    prod_hosts = [".production.", ".prod.", ".live.", "-prod-", "-live-"]
    for host in prod_hosts:
        if host in url_lower:
            return True

    parsed = urlparse(url)
    host = parsed.hostname or ""
    if host:
        safe_hosts = ["localhost", "127.0.0.1", "0.0.0.0", "postgres", "db"]
        if not any(safe in host for safe in safe_hosts):
            return True

    return False


def _create_mock_pool() -> MagicMock:
    """Создаёт mock asyncpg.Pool для unit тестов."""
    pool = MagicMock(spec=asyncpg.Pool)
    connection = AsyncMock()
    connection.fetch = AsyncMock(return_value=[])
    connection.fetchrow = AsyncMock(return_value=None)
    connection.execute = AsyncMock(return_value=None)

    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__.return_value = connection
    acquire_ctx.__aexit__.return_value = None
    pool.acquire = MagicMock(return_value=acquire_ctx)

    return pool


@pytest.fixture
async def db_pool() -> AsyncGenerator[MagicMock, None]:
    """
    Мок pool для БД (по умолчанию).

    Возвращает MagicMock, НЕ реальное подключение к asyncpg.
    Все тесты используют мок по умолчанию для изоляции от реальной БД.
    Для integration тестов использовать фикстуру real_db_pool.
    """
    yield _create_mock_pool()


@pytest.fixture
def mock_db_pool() -> MagicMock:
    """
    Mock пула подключений к БД для unit тестов.

    Возвращает MagicMock с настроенным async контекстным менеджером
    для acquire() и mock connection для fetch/fetchrow.
    """
    return _create_mock_pool()


@pytest.fixture
async def db_pool_with_session_data(
    db_pool: MagicMock,
) -> AsyncGenerator[MagicMock, None]:
    """
    Фикстура с мок-пулом, готовым к тестам с session_data.

    Возвращает тот же мок db_pool, но с настроенным connection
    для операций с таблицей telegram_auth.

    Примечание: параметр db_pool — это MagicMock, а не asyncpg.Pool.
    SQL-операции на моке являются no-op. Для реальных SQL-операций
    используйте фикстуру real_db_pool.
    """
    api_id = 10000 + secrets.randbelow(90000)
    api_hash = f"test_hash_{api_id}"

    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO telegram_auth (id, api_id, api_hash) VALUES (1, $1, $2) ON CONFLICT (id) DO UPDATE SET api_id = $1, api_hash = $2;",
            api_id,
            api_hash,
        )

    yield db_pool


@pytest.fixture
async def real_db_pool(
    integration_tests_enabled: bool,
) -> AsyncGenerator[asyncpg.Pool, None]:
    """
    Реальное подключение к БД (только для integration тестов).

    Подключается напрямую к TEST_DATABASE_URL, минуя get_pool() из .env.
    """
    if not integration_tests_enabled:
        raise ValueError("Integration tests disabled. Set RUN_INTEGRATION_TESTS=true to enable.")

    test_db_url = os.getenv("TEST_DATABASE_URL", "").strip()
    if not test_db_url:
        raise ValueError("TEST_DATABASE_URL environment variable is required for integration tests")

    if _is_production_url(test_db_url):
        raise ValueError("Production database URL is not allowed for tests")

    pool = await asyncpg.create_pool(dsn=test_db_url)
    try:
        yield pool
    finally:
        await pool.close()


@pytest.fixture(scope="session")
def integration_tests_enabled() -> bool:
    """Включить integration тесты (требует БД)."""
    return os.getenv("RUN_INTEGRATION_TESTS", "false").lower() == "true"
