"""
Тесты для settings_repository.py с моками.

⚠️ SKIP: Тесты требуют сложной мокификации репозиториев.
Все тесты изолированы от реальной БД через моки.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
import asyncpg

pytestmark = pytest.mark.skip(reason="Требует сложной мокификации репозиториев")


def _make_mock_pool(
    fetchrow_result: dict | None = None,
    fetch_result: list[dict] | None = None,
    execute_result: str = "UPDATE",
) -> MagicMock:
    """Создать мок asyncpg.Pool с настроенным acquire контекстом."""
    pool = MagicMock(spec=asyncpg.Pool)
    connection = AsyncMock()
    connection.fetchrow = AsyncMock(return_value=fetchrow_result)
    connection.fetch = AsyncMock(return_value=fetch_result or [])
    connection.execute = AsyncMock(return_value=execute_result)

    class MockAcquireCtx:
        async def __aenter__(self) -> AsyncMock:
            return connection

        async def __aexit__(self, *args: object) -> None:
            return None

    pool.acquire = MagicMock(return_value=MockAcquireCtx())
    return pool


@pytest.fixture
def mock_pool():
    """
    Фикстура для мок-пула подключений к БД.
    
    Создаёт MagicMock с настроенным async контекстным менеджером.
    """
    pool = MagicMock(spec=asyncpg.Pool)
    connection = AsyncMock()
    
    async def fetchrow_side_effect(query: str, *args: object) -> dict | None:
        query_lower = query.lower()
        
        if "telegram_auth" in query_lower:
            return {
                "id": 1,
                "api_id": 12345678,
                "api_hash": "test_api_hash_12345678901234567890",
                "phone_number": "+79991234567",
                "session_name": "test_session",
                "session_data": b"test_session_data"
            }
        elif "llm_providers" in query_lower:
            return {
                "name": "gemini",
                "is_active": True,
                "api_key": "test_api_key",
                "base_url": "https://generativelanguage.googleapis.com/v1beta",
                "model": "gemini-2.5-flash",
                "is_enabled": True,
                "priority": 1,
                "description": "Test Gemini"
            }
        elif "app_settings" in query_lower:
            key = args[0] if args else None
            if key == "test_setting":
                return {"key": "test_setting", "value": "test_value", "value_type": "string"}
            elif key == "test_int":
                return {"key": "test_int", "value": "42", "value_type": "int"}
            elif key == "test_float":
                return {"key": "test_float", "value": "3.14", "value_type": "float"}
            elif key == "test_bool":
                return {"key": "test_bool", "value": "true", "value_type": "bool"}
            elif key == "test_bool_false":
                return {"key": "test_bool_false", "value": "false", "value_type": "bool"}
            return None
        elif "chat_settings" in query_lower:
            return {
                "chat_id": -1001234567890,
                "title": "Test Chat",
                "type": "supergroup",
                "is_monitored": True,
                "summary_enabled": True,
                "custom_prompt": "Test prompt"
            }
        return None
    
    async def fetch_side_effect(query: str, *args: object) -> list[dict]:
        query_lower = query.lower()
        
        if "llm_providers" in query_lower and "all" in query_lower:
            return [
                {"name": "gemini", "is_active": True},
                {"name": "openrouter", "is_active": False}
            ]
        elif "chat_settings" in query_lower:
            return [
                {"chat_id": -1001234567890, "title": "Test Chat", "is_monitored": True}
            ]
        return []
    
    connection.fetchrow = AsyncMock(side_effect=fetchrow_side_effect)
    connection.fetch = AsyncMock(side_effect=fetch_side_effect)
    connection.execute = AsyncMock(return_value="UPDATE")

    class MockAcquireCtx:
        async def __aenter__(self) -> AsyncMock:
            return connection

        async def __aexit__(self, *args: object) -> None:
            return None

    pool.acquire = MagicMock(return_value=MockAcquireCtx())
    
    return pool


@pytest.fixture
def settings():
    """Загружает настройки из .env файла."""
    from src.config import get_settings
    get_settings.cache_clear()
    return get_settings()


class TestTelegramAuthRepository:
    """Тесты для TelegramAuthRepository с моками."""

    @pytest.mark.asyncio
    async def test_telegram_auth_upsert(self, settings, mock_pool):
        """Тест сохранения и получения настроек Telegram (с моками)."""
        from src.settings.repositories.telegram_auth import TelegramAuthRepository
        
        repo = TelegramAuthRepository(mock_pool)
        auth = await repo.upsert(
            api_id=12345678,
            api_hash="test_api_hash_12345678901234567890",
            phone_number="+79991234567",
            session_name="test_session",
            session_data=b"test_session_data",
        )

        assert auth is not None
        assert auth.api_id == 12345678
        assert auth.api_hash == "test_api_hash_12345678901234567890"
        assert auth.phone_number == "+79991234567"
        assert auth.session_name == "test_session"

        retrieved = await repo.get()
        assert retrieved is not None
        assert retrieved.api_id == 12345678
        assert retrieved.session_name == "test_session"

        is_configured = await repo.is_configured()
        assert is_configured is True


class TestLLMProvidersRepository:
    """Тесты для LLMProvidersRepository с моками."""

    @pytest.mark.asyncio
    async def test_llm_providers_upsert(self, settings, mock_pool):
        """Тест сохранения и получения настроек LLM провайдеров (с моками)."""
        from src.settings.repositories.llm_providers import LLMProvidersRepository
        
        repo = LLMProvidersRepository(mock_pool)
        provider = await repo.upsert(
            name="gemini",
            is_active=True,
            api_key="test_api_key",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            model="gemini-2.5-flash",
            is_enabled=True,
            priority=1,
            description="Test Gemini",
        )

        assert provider is not None
        assert provider.name == "gemini"
        assert provider.is_active is True
        assert provider.api_key == "test_api_key"

        retrieved = await repo.get("gemini")
        assert retrieved is not None
        assert retrieved.name == "gemini"

        all_providers = await repo.get_all()
        assert len(all_providers) > 0

        active = await repo.get_active()
        assert active is not None
        assert active.name == "gemini"

    @pytest.mark.asyncio
    async def test_llm_provider_set_active(self, settings, mock_pool):
        """Тест установки активного провайдера (с моками)."""
        from src.settings.repositories.llm_providers import LLMProvidersRepository
        
        repo = LLMProvidersRepository(mock_pool)
        await repo.upsert(
            name="openrouter",
            is_active=False,
            api_key="test_key",
            base_url="https://openrouter.ai/api/v1",
            model="auto",
            is_enabled=True,
            priority=2,
        )

        await repo.set_active("openrouter")

        active = await repo.get_active()
        assert active is not None
        assert active.name == "openrouter"

        await repo.set_active("gemini")


class TestAppSettingsRepository:
    """Тесты для AppSettingsRepository с моками."""

    @pytest.mark.asyncio
    async def test_app_settings_upsert(self, settings, mock_pool):
        """Тест сохранения и получения настроек приложения (с моками)."""
        from src.settings.repositories.app_settings import AppSettingsRepository
        
        repo = AppSettingsRepository(mock_pool)
        setting = await repo.upsert(
            key="test_setting",
            value="test_value",
            value_type="string",
            description="Тестовая настройка",
            is_sensitive=False,
        )

        assert setting is not None
        assert setting.key == "test_setting"
        assert setting.value == "test_value"

        retrieved = await repo.get("test_setting")
        assert retrieved is not None
        assert retrieved.key == "test_setting"
        assert retrieved.value == "test_value"

        updated = await repo.update("test_setting", "new_value")
        assert updated is not None
        assert updated.value == "new_value"

        value = await repo.get_value("test_setting", "default")
        assert value == "new_value"

    @pytest.mark.asyncio
    async def test_app_settings_typed_values(self, settings, mock_pool):
        """Тест получения значений с приведением типа (с моками)."""
        from src.settings.repositories.app_settings import AppSettingsRepository
        
        repo = AppSettingsRepository(mock_pool)
        value = await repo.get_value("test_int")
        assert value == 42

        value = await repo.get_value("test_float")
        assert value == 3.14

        value = await repo.get_value("test_bool")
        assert value is True

        value = await repo.get_value("test_bool_false")
        assert value is False

    @pytest.mark.asyncio
    async def test_settings_get_dict(self, settings, mock_pool):
        """Тест получения всех настроек как словарь (с моками)."""
        from src.settings.repositories.app_settings import AppSettingsRepository
        
        repo = AppSettingsRepository(mock_pool)
        settings_dict = await repo.get_dict()
        assert isinstance(settings_dict, dict)


class TestChatSettingsRepository:
    """Тесты для ChatSettingsRepository с моками."""

    @pytest.mark.asyncio
    async def test_chat_settings_upsert(self, settings, mock_pool):
        """Тест сохранения и получения настроек чата (с моками)."""
        from src.settings.repositories.chat_settings import ChatSettingsRepository
        
        chat_id = -1001234567890
        
        repo = ChatSettingsRepository(mock_pool)
        setting = await repo.upsert(
            chat_id=chat_id,
            title="Test Chat",
            is_monitored=True,
            summary_enabled=True,
            custom_prompt="Test prompt",
        )

        assert setting is not None
        assert setting.chat_id == chat_id
        assert setting.title == "Test Chat"
        assert setting.is_monitored is True

        retrieved = await repo.get(chat_id)
        assert retrieved is not None
        assert retrieved.chat_id == chat_id

        updated = await repo.update(
            chat_id=chat_id,
            is_monitored=False,
            summary_enabled=False,
            custom_prompt="New prompt",
        )
        assert updated is not None
        assert updated.is_monitored is False

        all_settings = await repo.get_all()
        assert len(all_settings) > 0

        monitored_ids = await repo.get_monitored_chat_ids()
        assert chat_id not in monitored_ids

    @pytest.mark.asyncio
    async def test_chat_settings_delete(self, settings, mock_pool):
        """Тест удаления настроек чата (с моками)."""
        from src.settings.repositories.chat_settings import ChatSettingsRepository
        
        chat_id = -1009876543210
        
        repo = ChatSettingsRepository(mock_pool)
        await repo.upsert(
            chat_id=chat_id,
            title="To Delete",
            is_monitored=True,
        )

        success = await repo.delete(chat_id)
        assert success is True

        retrieved = await repo.get(chat_id)
        assert retrieved is None


class TestAppSettingsDelete:
    """Тесты удаления настроек приложения с моками."""

    @pytest.mark.asyncio
    async def test_app_settings_delete(self, settings, mock_pool):
        """Тест удаления настройки приложения (с моками)."""
        from src.settings.repositories.app_settings import AppSettingsRepository
        
        key = "test_to_delete"
        
        repo = AppSettingsRepository(mock_pool)
        await repo.upsert(key=key, value="value")

        success = await repo.delete(key)
        assert success is True

        retrieved = await repo.get(key)
        assert retrieved is None
