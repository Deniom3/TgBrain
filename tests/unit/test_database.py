"""
Модульные тесты базы данных с моками.

Все тесты изолированы от реальной БД через моки.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import asyncpg


@pytest.fixture
def mock_pool():
    """
    Фикстура для мок-пула подключений к БД.
    
    Создаёт MagicMock с настроенным async контекстным менеджером
    для acquire() и mock connection для fetch/fetchrow/fetchval.
    """
    pool = MagicMock(spec=asyncpg.Pool)
    connection = AsyncMock()
    
    connection.fetchval = AsyncMock(return_value=1)
    connection.fetch = AsyncMock(return_value=[
        {"table_name": "messages"},
        {"table_name": "chats"},
        {"table_name": "pending_messages"}
    ])
    connection.fetchrow = AsyncMock(return_value={
        "extname": "vector",
        "extversion": "0.9.0"
    })

    class MockAcquireCtx:
        async def __aenter__(self):
            return connection

        async def __aexit__(self, *args):
            return None

    pool.acquire = MagicMock(return_value=MockAcquireCtx())
    
    return pool


@pytest.fixture
def mock_pool_extended():
    """
    Расширенная фикстура для тестов структуры таблиц.
    
    Возвращает разные данные для разных SQL запросов.
    """
    pool = MagicMock(spec=asyncpg.Pool)
    connection = AsyncMock()
    
    async def fetch_side_effect(query, *args):
        query_lower = query.lower()
        
        if "information_schema.tables" in query_lower:
            return [
                {"table_name": "messages"},
                {"table_name": "chats"},
                {"table_name": "pending_messages"},
                {"table_name": "chat_settings"}
            ]
        elif "pg_extension" in query_lower:
            return [
                {"extname": "vector", "extversion": "0.9.0"}
            ]
        elif "information_schema.columns" in query_lower and "messages" in query_lower:
            return [
                {"column_name": "id", "data_type": "bigint"},
                {"column_name": "chat_id", "data_type": "bigint"},
                {"column_name": "message_text", "data_type": "text"},
                {"column_name": "message_date", "data_type": "timestamp with time zone"},
                {"column_name": "embedding", "data_type": "vector"},
                {"column_name": "sender_id", "data_type": "bigint"},
                {"column_name": "sender_name", "data_type": "text"},
            ]
        return []
    
    connection.fetch = AsyncMock(side_effect=fetch_side_effect)
    connection.fetchval = AsyncMock(return_value=1)
    connection.fetchrow = AsyncMock(return_value=None)

    class MockAcquireCtxExtended:
        async def __aenter__(self):
            return connection

        async def __aexit__(self, *args):
            return None

    pool.acquire = MagicMock(return_value=MockAcquireCtxExtended())
    
    return pool


@pytest.mark.asyncio
async def test_db_connection(settings, mock_pool):
    """Проверка подключения к БД (с моками)."""
    with patch('src.database._pool', mock_pool):
        from src.database import get_pool
        
        pool = await get_pool()
        assert pool is not None
        
        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT 1")
            assert result == 1


@pytest.mark.asyncio
async def test_db_health(settings, mock_pool):
    """Проверка здоровья БД (с моками)."""
    from src.database import check_db_health
    
    with patch('src.database._pool', mock_pool):
        health = await check_db_health()
        assert health is True


@pytest.mark.asyncio
async def test_tables_exist(settings, mock_pool_extended):
    """Проверка существования таблиц (с моками)."""
    with patch('src.database._pool', mock_pool_extended):
        from src.database import get_pool
        
        pool = await get_pool()
        
        async with pool.acquire() as conn:
            tables = await conn.fetch("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('messages', 'chats', 'pending_messages')
            """)
            table_names = [t['table_name'] for t in tables]
            assert 'messages' in table_names
            assert 'chats' in table_names


@pytest.mark.asyncio
async def test_pgvector_extension(settings, mock_pool_extended):
    """Проверка установки расширения pgvector (с моками)."""
    with patch('src.database._pool', mock_pool_extended):
        from src.database import get_pool
        
        pool = await get_pool()
        
        async with pool.acquire() as conn:
            extensions = await conn.fetch("""
                SELECT extname, extversion
                FROM pg_extension
                WHERE extname = 'vector'
            """)
            assert len(extensions) > 0
            assert extensions[0]['extname'] == 'vector'


@pytest.mark.asyncio
async def test_messages_table_structure(settings, mock_pool_extended):
    """Проверка структуры таблицы messages (с моками)."""
    with patch('src.database._pool', mock_pool_extended):
        from src.database import get_pool
        
        pool = await get_pool()
        
        async with pool.acquire() as conn:
            columns = await conn.fetch("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'messages'
                ORDER BY ordinal_position
            """)
            column_names = [c['column_name'] for c in columns]
            
            assert 'id' in column_names
            assert 'chat_id' in column_names
            assert 'message_text' in column_names
            assert 'message_date' in column_names
            assert 'embedding' in column_names
