"""
Тесты для Chat Settings API endpoints.

⚠️ SKIP: Тесты используют реальную БД. Требуют мокификации.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import MagicMock, AsyncMock
import asyncpg
from src.database import init_db, close_pool
from src.settings import ChatSettingsRepository


pytestmark = pytest.mark.skip(reason="Требует мокификации — использует реальную БД")


def _make_mock_pool() -> MagicMock:
    """Создать мок asyncpg.Pool для тестов."""
    pool = MagicMock(spec=asyncpg.Pool)
    connection = AsyncMock()
    connection.fetchrow = AsyncMock(return_value=None)
    connection.fetch = AsyncMock(return_value=[])
    connection.execute = AsyncMock(return_value="UPDATE")

    class MockAcquireCtx:
        async def __aenter__(self) -> AsyncMock:
            return connection

        async def __aexit__(self, *args: object) -> None:
            return None

    pool.acquire = MagicMock(return_value=MockAcquireCtx())
    return pool


@pytest.fixture
def mock_pool() -> MagicMock:
    """Фикстура мок-пула."""
    return _make_mock_pool()


@pytest.fixture(scope="module", autouse=True)
async def setup_database():
    """Инициализация БД перед тестами."""
    await init_db()
    yield
    await close_pool()


@pytest.fixture
async def cleanup_chat_settings(mock_pool: MagicMock):
    """Очистка настроек чатов после каждого теста."""
    repo = ChatSettingsRepository(mock_pool)
    yield
    # Очищаем тестовые данные
    settings = await repo.get_all()
    for setting in settings:
        if setting.chat_id >= -1009999999000:  # Тестовые ID
            await repo.delete(setting.chat_id)


@pytest.fixture
async def client():
    """HTTP клиент для тестирования API."""
    from main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_get_all_chat_settings(client, cleanup_chat_settings, mock_pool: MagicMock):
    """Тест получения всех настроек чатов."""
    repo = ChatSettingsRepository(mock_pool)
    # Создаём тестовые данные
    await repo.upsert(
        chat_id=-1009999999001,
        title="API Test Chat 1",
        is_monitored=True,
    )
    await repo.upsert(
        chat_id=-1009999999002,
        title="API Test Chat 2",
        is_monitored=False,
    )
    
    response = await client.get("/api/v1/settings/chats")
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2


@pytest.mark.asyncio
async def test_get_chat_setting(client, cleanup_chat_settings, mock_pool: MagicMock):
    """Тест получения настроек конкретного чата."""
    repo = ChatSettingsRepository(mock_pool)
    chat_id = -1009999999003
    
    await repo.upsert(
        chat_id=chat_id,
        title="Single Chat",
        is_monitored=True,
    )
    
    response = await client.get(f"/api/v1/settings/chats/{chat_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["chat_id"] == chat_id
    assert data["title"] == "Single Chat"


@pytest.mark.asyncio
async def test_get_chat_setting_not_found(client, cleanup_chat_settings):
    """Тест получения несуществующего чата."""
    response = await client.get("/api/v1/settings/chats/-1009999999999")
    
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_chat_setting(client, cleanup_chat_settings, mock_pool: MagicMock):
    """Тест обновления настроек чата."""
    repo = ChatSettingsRepository(mock_pool)
    chat_id = -1009999999004
    
    await repo.upsert(
        chat_id=chat_id,
        title="Original",
        is_monitored=True,
    )
    
    response = await client.put(
        f"/api/v1/settings/chats/{chat_id}",
        json={
            "is_monitored": False,
            "summary_enabled": False,
            "custom_prompt": "New prompt",
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["is_monitored"] is False
    assert data["custom_prompt"] == "New prompt"


@pytest.mark.asyncio
async def test_toggle_chat_monitoring(client, cleanup_chat_settings, mock_pool: MagicMock):
    """Тест переключения мониторинга чата."""
    repo = ChatSettingsRepository(mock_pool)
    chat_id = -1009999999005
    
    await repo.upsert(
        chat_id=chat_id,
        title="Toggle Chat",
        is_monitored=True,
    )
    
    # Переключаем (True -> False)
    response = await client.post(f"/api/v1/settings/chats/{chat_id}/toggle")
    
    assert response.status_code == 200
    data = response.json()
    assert data["chat_id"] == chat_id
    assert data["is_monitored"] is False
    assert "message" in data


@pytest.mark.asyncio
async def test_enable_chat_monitoring(client, cleanup_chat_settings, mock_pool: MagicMock):
    """Тест включения мониторинга чата."""
    repo = ChatSettingsRepository(mock_pool)
    chat_id = -1009999999006
    
    await repo.upsert(
        chat_id=chat_id,
        title="Enable Chat",
        is_monitored=False,
    )
    
    response = await client.post(f"/api/v1/settings/chats/{chat_id}/enable")
    
    assert response.status_code == 200
    data = response.json()
    assert data["is_monitored"] is True


@pytest.mark.asyncio
async def test_disable_chat_monitoring(client, cleanup_chat_settings, mock_pool: MagicMock):
    """Тест отключения мониторинга чата."""
    repo = ChatSettingsRepository(mock_pool)
    chat_id = -1009999999007
    
    await repo.upsert(
        chat_id=chat_id,
        title="Disable Chat",
        is_monitored=True,
    )
    
    response = await client.post(f"/api/v1/settings/chats/{chat_id}/disable")
    
    assert response.status_code == 200
    data = response.json()
    assert data["is_monitored"] is False


@pytest.mark.asyncio
async def test_get_monitored_chat_settings(client, cleanup_chat_settings, mock_pool: MagicMock):
    """Тест получения только monitored чатов."""
    repo = ChatSettingsRepository(mock_pool)
    # Создаём чаты с разными настройками
    await repo.upsert(
        chat_id=-1009999999008,
        title="Monitored 1",
        is_monitored=True,
    )
    await repo.upsert(
        chat_id=-1009999999009,
        title="Not Monitored",
        is_monitored=False,
    )
    await repo.upsert(
        chat_id=-1009999999010,
        title="Monitored 2",
        is_monitored=True,
    )
    
    response = await client.get("/api/v1/settings/chats/monitored")
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    
    # Все чаты должны быть monitored
    for chat in data:
        assert chat["is_monitored"] is True


@pytest.mark.asyncio
async def test_bulk_update_chat_settings(client, cleanup_chat_settings, mock_pool: MagicMock):
    """Тест массового обновления настроек."""
    repo = ChatSettingsRepository(mock_pool)
    # Создаём тестовые чаты
    chat_ids = [-1009999999011, -1009999999012, -1009999999013]
    for chat_id in chat_ids:
        await repo.upsert(
            chat_id=chat_id,
            title=f"Bulk {chat_id}",
            is_monitored=True,
        )
    
    response = await client.post(
        "/api/v1/settings/chats/bulk-update",
        json={
            "chat_ids": chat_ids,
            "is_monitored": False,
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["updated_count"] == 3
    assert data["chat_ids"] == chat_ids


@pytest.mark.asyncio
async def test_delete_chat_setting(client, cleanup_chat_settings, mock_pool: MagicMock):
    """Тест удаления настроек чата."""
    repo = ChatSettingsRepository(mock_pool)
    chat_id = -1009999999014
    
    await repo.upsert(
        chat_id=chat_id,
        title="To Delete",
        is_monitored=True,
    )
    
    response = await client.delete(f"/api/v1/settings/chats/{chat_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    
    # Проверяем, что чат удалён
    get_response = await client.get(f"/api/v1/settings/chats/{chat_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_get_chat_settings_with_meta(client, cleanup_chat_settings, mock_pool: MagicMock):
    """Тест получения настроек чатов с мета-информацией."""
    repo = ChatSettingsRepository(mock_pool)
    # Создаём тестовые данные
    await repo.upsert(
        chat_id=-1009999999015,
        title="Meta 1",
        is_monitored=True,
    )
    await repo.upsert(
        chat_id=-1009999999016,
        title="Meta 2",
        is_monitored=False,
    )
    
    response = await client.get("/api/v1/settings/chats/list")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "chats" in data
    assert "meta" in data
    assert data["meta"]["total"] >= 2
    assert "monitored" in data["meta"]
    assert "not_monitored" in data["meta"]


@pytest.mark.asyncio
async def test_add_user_for_monitoring_by_id(client, cleanup_chat_settings, mock_pool: MagicMock):
    """Тест добавления пользователя по ID (интеграционный, требует Telegram)."""
    # Этот тест требует авторизованной сессии Telegram
    # Пропускаем если сессия не настроена
    from src.settings import TelegramAuthRepository
    repo = TelegramAuthRepository(mock_pool)
    auth = await repo.get()
    
    if not auth or not auth.session_name:
        pytest.skip("Сессия Telegram не настроена")
    
    pytest.skip("Интеграционный тест - требует реального ID пользователя")


@pytest.mark.asyncio
async def test_add_user_for_monitoring_by_username(client, cleanup_chat_settings, mock_pool: MagicMock):
    """Тест добавления пользователя по username (интеграционный, требует Telegram)."""
    # Этот тест требует авторизованной сессии Telegram
    from src.settings import TelegramAuthRepository
    repo = TelegramAuthRepository(mock_pool)
    auth = await repo.get()
    
    if not auth or not auth.session_name:
        pytest.skip("Сессия Telegram не настроена")
    
    pytest.skip("Интеграционный тест - требует реального username")


@pytest.mark.asyncio
async def test_remove_user_from_monitoring_by_id(client, cleanup_chat_settings, mock_pool: MagicMock):
    """Тест отключения пользователя по ID (интеграционный, требует Telegram)."""
    from src.settings import TelegramAuthRepository
    repo = TelegramAuthRepository(mock_pool)
    auth = await repo.get()
    
    if not auth or not auth.session_name:
        pytest.skip("Сессия Telegram не настроена")
    
    pytest.skip("Интеграционный тест - требует реального ID пользователя")


@pytest.mark.asyncio
async def test_remove_user_from_monitoring_by_username(client, cleanup_chat_settings, mock_pool: MagicMock):
    """Тест отключения пользователя по username (интеграционный, требует Telegram)."""
    from src.settings import TelegramAuthRepository
    repo = TelegramAuthRepository(mock_pool)
    auth = await repo.get()
    
    if not auth or not auth.session_name:
        pytest.skip("Сессия Telegram не настроена")
    
    pytest.skip("Интеграционный тест - требует реального username")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
