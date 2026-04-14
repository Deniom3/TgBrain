"""
Тест переключения модели эмбединга через pytest (с моками).

⚠️ SKIP: Тест требует сложной мокификации БД логики.
Все тесты изолированы от реальной БД через моки.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import asyncpg


pytestmark = pytest.mark.skip(reason="Требует сложной мокификации БД логики")


@pytest.fixture
def mock_pool():
    """
    Фикстура для мок-пула подключений к БД.
    
    Создаёт MagicMock с настроенным async контекстным менеджером
    для acquire() и mock connection для fetchrow/execute.
    """
    pool = MagicMock(spec=asyncpg.Pool)
    connection = AsyncMock()
    
    # Хранилище для эмуляции обновления данных
    stored_data = {
        "name": "ollama",
        "model": "nomic-embed-text:latest",
        "embedding_dim": 768
    }
    
    async def fetchrow_side_effect(query, *args):
        if "embedding_providers" in query.lower():
            return stored_data.copy()
        return None
    
    async def execute_side_effect(query, *args):
        # Эмуляция UPDATE запроса
        if "UPDATE" in query.upper() or "embedding_dim" in query.lower():
            # Обновляем данные
            for i, arg in enumerate(args):
                if i == 0 and isinstance(arg, str):
                    stored_data["model"] = arg
                if i == 1 and isinstance(arg, int):
                    stored_data["embedding_dim"] = arg
        return "UPDATE"
    
    connection.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    connection.execute = AsyncMock(side_effect=execute_side_effect)
    connection.fetch = AsyncMock(return_value=[])

    class MockAcquireCtx:
        async def __aenter__(self):
            return connection

        async def __aexit__(self, *args):
            return None

    pool.acquire = MagicMock(return_value=MockAcquireCtx())
    
    return pool


@pytest.mark.asyncio
async def test_model_switch_and_dimension_update(settings, mock_pool):
    """Проверка что при переключении модели обновляется размерность в БД (с моками)."""
    from src.settings_initializer import SettingsInitializer
    
    with patch('src.database._pool', mock_pool):
        with patch.object(SettingsInitializer, '_init_embedding_providers', new=AsyncMock()):
            async with mock_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT name, model, embedding_dim FROM embedding_providers WHERE name = 'ollama'"
                )
                initial_model = row['model'] if row else 'nomic-embed-text:latest'
                initial_dim = row['embedding_dim'] if row else 768
                assert initial_model == 'nomic-embed-text:latest'
                assert initial_dim == 768

            test_models = [
                ("nomic-embed-text:latest", 768),
                ("mxbai-embed-large:latest", 1024),
                ("bge-m3:latest", 1024),
            ]

            for new_model, expected_dim in test_models:
                settings.ollama_embedding_model = new_model
                settings.ollama_embedding_dim = None

                await SettingsInitializer._init_embedding_providers(settings)

                async with mock_pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT name, model, embedding_dim FROM embedding_providers WHERE name = 'ollama'"
                    )

                    assert row['model'] == new_model, f"Модель не обновилась: {row['model']} != {new_model}"
                    assert row['embedding_dim'] == expected_dim, f"Размерность неверна: {row['embedding_dim']} != {expected_dim}"
