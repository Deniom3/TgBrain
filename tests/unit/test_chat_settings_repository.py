"""
Тесты для ChatSettingsRepository.

Проверка методов репозитория для управления настройками чатов.

⚠️ SKIP: Тесты используют реальную БД. Требуют мокификации.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
import asyncpg

from src.settings import ChatSettingsRepository
from src.database import init_db_tables, close_pool


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
    await init_db_tables()
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
        if setting.chat_id >= -1009999999999:  # Тестовые ID
            await repo.delete(setting.chat_id)


@pytest.mark.asyncio
async def test_upsert_chat_setting(cleanup_chat_settings, mock_pool: MagicMock):
    """Тест сохранения/обновления настроек чата."""
    repo = ChatSettingsRepository(mock_pool)
    chat_id = -1009999999991
    
    # Создаём новую запись
    setting = await repo.upsert(
        chat_id=chat_id,
        title="Test Chat",
        is_monitored=True,
        summary_enabled=True,
        custom_prompt=None,
    )
    
    assert setting is not None
    assert setting.chat_id == chat_id
    assert setting.title == "Test Chat"
    assert setting.is_monitored is True
    assert setting.summary_enabled is True
    
    # Обновляем запись
    updated = await repo.upsert(
        chat_id=chat_id,
        title="Updated Chat",
        is_monitored=False,
        summary_enabled=False,
        custom_prompt="Custom prompt",
    )
    
    assert updated is not None
    assert updated.title == "Updated Chat"
    assert updated.is_monitored is False
    assert updated.custom_prompt == "Custom prompt"


@pytest.mark.asyncio
async def test_get_chat_setting(cleanup_chat_settings, mock_pool: MagicMock):
    """Тест получения настроек чата."""
    repo = ChatSettingsRepository(mock_pool)
    chat_id = -1009999999992
    
    # Создаём запись
    await repo.upsert(
        chat_id=chat_id,
        title="Get Test Chat",
        is_monitored=True,
        summary_enabled=True,
    )
    
    # Получаем запись
    setting = await repo.get(chat_id)
    
    assert setting is not None
    assert setting.chat_id == chat_id
    assert setting.title == "Get Test Chat"
    
    # Получаем несуществующую запись
    not_found = await repo.get(-1009999999999)
    assert not_found is None


@pytest.mark.asyncio
async def test_get_all_chat_settings(cleanup_chat_settings, mock_pool: MagicMock):
    """Тест получения всех настроек чатов."""
    repo = ChatSettingsRepository(mock_pool)
    # Создаём несколько записей
    for i in range(3):
        await repo.upsert(
            chat_id=-1009999999990 + i,
            title=f"Chat {i}",
            is_monitored=i % 2 == 0,
            summary_enabled=True,
        )
    
    settings = await repo.get_all()
    
    # Проверяем, что получили至少 3 записи (могут быть другие тесты)
    assert len(settings) >= 3


@pytest.mark.asyncio
async def test_update_chat_setting(cleanup_chat_settings, mock_pool: MagicMock):
    """Тест обновления настроек чата."""
    repo = ChatSettingsRepository(mock_pool)
    chat_id = -1009999999987
    
    # Создаём запись
    await repo.upsert(
        chat_id=chat_id,
        title="Original",
        is_monitored=True,
        summary_enabled=True,
    )
    
    # Обновляем
    updated = await repo.update(
        chat_id=chat_id,
        is_monitored=False,
        summary_enabled=False,
        custom_prompt="New prompt",
    )
    
    assert updated is not None
    assert updated.is_monitored is False
    assert updated.summary_enabled is False
    assert updated.custom_prompt == "New prompt"


@pytest.mark.asyncio
async def test_delete_chat_setting(cleanup_chat_settings, mock_pool: MagicMock):
    """Тест удаления настроек чата."""
    repo = ChatSettingsRepository(mock_pool)
    chat_id = -1009999999986
    
    # Создаём запись
    await repo.upsert(
        chat_id=chat_id,
        title="To Delete",
        is_monitored=True,
    )
    
    # Проверяем, что запись существует
    setting = await repo.get(chat_id)
    assert setting is not None
    
    # Удаляем
    success = await repo.delete(chat_id)
    assert success is True
    
    # Проверяем, что запись удалена
    deleted = await repo.get(chat_id)
    assert deleted is None


@pytest.mark.asyncio
async def test_get_monitored_chat_ids(cleanup_chat_settings, mock_pool: MagicMock):
    """Тест получения ID monitored чатов."""
    repo = ChatSettingsRepository(mock_pool)
    # Создаём записи с разными is_monitored
    await repo.upsert(
        chat_id=-1009999999985,
        title="Monitored 1",
        is_monitored=True,
    )
    await repo.upsert(
        chat_id=-1009999999984,
        title="Not Monitored",
        is_monitored=False,
    )
    await repo.upsert(
        chat_id=-1009999999983,
        title="Monitored 2",
        is_monitored=True,
    )
    
    monitored_ids = await repo.get_monitored_chat_ids()
    
    assert -1009999999985 in monitored_ids
    assert -1009999999983 in monitored_ids
    assert -1009999999984 not in monitored_ids


@pytest.mark.asyncio
async def test_bulk_upsert_chat_settings(cleanup_chat_settings, mock_pool: MagicMock):
    """Тест массового сохранения настроек чатов."""
    repo = ChatSettingsRepository(mock_pool)
    chats: list[dict[str, object]] = [
        {"chat_id": -1009999999980, "title": "Bulk 1", "is_monitored": True},
        {"chat_id": -1009999999981, "title": "Bulk 2", "is_monitored": False},
        {"chat_id": -1009999999982, "title": "Bulk 3", "is_monitored": True},
    ]
    
    saved = await repo.bulk_upsert_chat_settings(chats)
    
    assert len(saved) == 3
    
    # Проверяем сохранённые данные
    for chat in chats:
        setting = await repo.get(chat["chat_id"])  # type: ignore[arg-type]
        assert setting is not None
        assert setting.title == chat["title"]
        assert setting.is_monitored == chat["is_monitored"]


@pytest.mark.asyncio
async def test_toggle_chat_monitoring(cleanup_chat_settings, mock_pool: MagicMock):
    """Тест переключения мониторинга чата."""
    repo = ChatSettingsRepository(mock_pool)
    chat_id = -1009999999979
    
    # Создаём запись с is_monitored=True
    await repo.upsert(
        chat_id=chat_id,
        title="Toggle Test",
        is_monitored=True,
    )
    
    # Переключаем (True -> False)
    toggled = await repo.toggle_chat_monitoring(chat_id)
    assert toggled is not None
    assert toggled.is_monitored is False
    
    # Переключаем ещё раз (False -> True)
    toggled_again = await repo.toggle_chat_monitoring(chat_id)
    assert toggled_again is not None
    assert toggled_again.is_monitored is True


@pytest.mark.asyncio
async def test_enable_disable_chat(cleanup_chat_settings, mock_pool: MagicMock):
    """Тест включения/отключения чата."""
    repo = ChatSettingsRepository(mock_pool)
    chat_id = -1009999999978
    
    # Создаём запись с is_monitored=False
    await repo.upsert(
        chat_id=chat_id,
        title="Enable/Disable Test",
        is_monitored=False,
    )
    
    # Включаем
    enabled = await repo.enable_chat(chat_id)
    assert enabled is not None
    assert enabled.is_monitored is True
    
    # Отключаем
    disabled = await repo.disable_chat(chat_id)
    assert disabled is not None
    assert disabled.is_monitored is False


@pytest.mark.asyncio
async def test_initialize_from_env(cleanup_chat_settings, mock_pool: MagicMock):
    """Тест инициализации настроек из .env."""
    repo = ChatSettingsRepository(mock_pool)
    # Создаём несколько чатов
    await repo.upsert(
        chat_id=-1009999999977,
        title="Chat 1",
        is_monitored=False,
    )
    await repo.upsert(
        chat_id=-1009999999976,
        title="Chat 2",
        is_monitored=True,
    )
    
    # Инициализируем из "env"
    enable_list = [-1009999999977, -1009999999975]  # Один существует, один новый
    disable_list = [-1009999999976]
    
    stats = await repo.initialize_from_env(
        enable_list,
        disable_list
    )
    
    assert "enabled" in stats
    assert "disabled" in stats
    assert stats["enabled"] >= 1
    assert stats["disabled"] >= 1
    
    # Проверяем, что чат из enable_list включён
    setting1 = await repo.get(-1009999999977)
    assert setting1 is not None
    assert setting1.is_monitored is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
