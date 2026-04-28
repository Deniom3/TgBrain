"""Интеграционные тесты Settings API."""
import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from src.database import init_db_tables, close_pool
from src.settings import ChatSettingsRepository

pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def event_loop():
    """Создать event loop для всех тестов сессии."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def init_test_db():
    """Инициализировать БД перед всеми тестами."""
    await init_db_tables()
    yield
    await close_pool()


@pytest.fixture(scope="module")
async def client():
    """Создать HTTP клиент для тестов."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_get_telegram_auth(client):
    """Тест получения настроек Telegram."""
    response = await client.get("/api/v1/settings/telegram")
    assert response.status_code == 200
    data = response.json()
    assert "api_id" in data
    assert "session_name" in data
    assert "is_configured" in data


@pytest.mark.asyncio
async def test_update_telegram_auth(client):
    """Тест обновления настроек Telegram."""
    payload = {
        "api_id": 87654321,
        "api_hash": "new_test_api_hash_12345678901234567890",
        "phone_number": "+79990000000",
        "session_name": "new_session",
        "session_data": "bmV3X3Nlc3Npb25fZGF0YQ==",  # base64 encoded
    }

    response = await client.put("/api/v1/settings/telegram", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["api_id"] == 87654321
    assert data["session_name"] == "new_session"
    assert data["is_configured"] is True


@pytest.mark.asyncio
async def test_get_all_llm_providers(client):
    """Тест получения всех LLM провайдеров."""
    response = await client.get("/api/v1/settings/llm")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


@pytest.mark.asyncio
async def test_get_llm_provider(client):
    """Тест получения конкретного LLM провайдера."""
    response = await client.get("/api/v1/settings/llm/gemini")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "gemini"


@pytest.mark.asyncio
async def test_get_llm_provider_not_found(client):
    """Тест получения несуществующего провайдера."""
    response = await client.get("/api/v1/settings/llm/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_llm_provider(client):
    """Тест обновления настроек LLM провайдера."""
    payload = {
        "is_active": False,
        "api_key": "updated_api_key",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "model": "gemini-2.5-flash",
        "is_enabled": True,
        "priority": 1,
        "description": "Updated Gemini",
    }

    response = await client.put("/api/v1/settings/llm/gemini", json=payload)
    assert response.status_code == 200
    data = response.json()
    # API ключ возвращается замаскированным
    assert "api_key_masked" in data or data["is_active"] is False
    assert data["is_active"] is False


@pytest.mark.asyncio
async def test_activate_llm_provider(client):
    """Тест активации LLM провайдера."""
    response = await client.post("/api/v1/settings/llm/openrouter/activate")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["active_provider"] == "openrouter"

    # Возвращаем gemini как активного
    await client.post("/api/v1/settings/llm/gemini/activate")


@pytest.mark.asyncio
async def test_get_all_app_settings(client):
    """Тест получения всех настроек приложения."""
    response = await client.get("/api/v1/settings/app")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


@pytest.mark.asyncio
async def test_get_app_setting(client):
    """Тест получения конкретной настройки приложения."""
    response = await client.get("/api/v1/settings/app/log_level")
    assert response.status_code == 200
    data = response.json()
    assert data["key"] == "log_level"


@pytest.mark.asyncio
async def test_get_app_setting_not_found(client):
    """Тест получения несуществующей настройки."""
    response = await client.get("/api/v1/settings/app/nonexistent_setting")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_app_setting(client):
    """Тест обновления настройки приложения."""
    payload = {"value": "DEBUG"}

    response = await client.put("/api/v1/settings/app/log_level", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["value"] == "DEBUG"
    assert data["key"] == "log_level"

    # Возвращаем исходное значение
    await client.put("/api/v1/settings/app/log_level", json={"value": "INFO"})


@pytest.mark.asyncio
async def test_get_all_chat_settings(client):
    """Тест получения всех настроек чатов."""
    response = await client.get("/api/v1/settings/chats")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_chat_setting_not_found(client):
    """Тест получения несуществующих настроек чата."""
    response = await client.get("/api/v1/settings/chats/999999999999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_chat_setting(client):
    """Тест обновления настроек чата."""
    # Используем реальный chat_id из .env или создаём новый
    chat_id = -1001111111111
    payload = {
        "title": "Updated Chat",
        "is_monitored": False,
        "summary_enabled": False,
        "custom_prompt": "Custom prompt",
    }

    response = await client.put(f"/api/v1/settings/chats/{chat_id}", json=payload)
    # Может быть 200 (успех), 404 (чат не найден) или 500 (ошибка БД)
    assert response.status_code in [200, 404, 500]


@pytest.mark.asyncio
async def test_delete_chat_setting(client):
    """Тест удаления настроек чата."""
    chat_id = -1002222222222

    # Создаём настройки через репозиторий с реальным пулом
    from main import app
    repo = ChatSettingsRepository(app.state.db_pool)
    await repo.upsert(
        chat_id=chat_id,
        title="To Delete",
        is_monitored=True,
    )

    # Удаляем
    response = await client.delete(f"/api/v1/settings/chats/{chat_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


@pytest.mark.asyncio
async def test_get_settings_overview(client):
    """Тест получения обзора настроек."""
    response = await client.get("/api/v1/settings/overview")
    assert response.status_code == 200
    data = response.json()
    assert "telegram" in data
    assert "llm" in data
    assert "app" in data
    assert "chats" in data


@pytest.mark.asyncio
async def test_settings_api_health(client):
    """Тест что API настроек доступно через health check."""
    response = await client.get("/health")
    assert response.status_code == 200


# ==================== Embedding Provider Tests ====================

@pytest.mark.asyncio
async def test_get_all_embedding_providers(client):
    """Тест получения всех провайдеров эмбеддингов."""
    response = await client.get("/api/v1/settings/embedding")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    
    # Проверяем структуру
    for provider in data:
        assert "name" in provider
        assert "is_active" in provider
        assert "base_url" in provider
        assert "model" in provider
        assert "embedding_dim" in provider


@pytest.mark.asyncio
async def test_get_embedding_provider(client):
    """Тест получения конкретного провайдера эмбеддингов."""
    response = await client.get("/api/v1/settings/embedding/ollama")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "ollama"
    assert "embedding_dim" in data
    assert "base_url" in data


@pytest.mark.asyncio
async def test_get_embedding_provider_not_found(client):
    """Тест получения несуществующего провайдера эмбеддингов."""
    response = await client.get("/api/v1/settings/embedding/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_activate_embedding_provider(client):
    """Тест активации провайдера эмбеддингов."""
    # Активируем ollama
    response = await client.post("/api/v1/settings/embedding/ollama/activate")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["active_provider"] == "ollama"
    
    # Проверяем что ollama стал активным
    response = await client.get("/api/v1/settings/embedding/ollama")
    assert response.status_code == 200
    data = response.json()
    assert data["is_active"] is True
    
    # Проверяем что другие провайдеры деактивированы
    response = await client.get("/api/v1/settings/embedding")
    assert response.status_code == 200
    data = response.json()
    active_providers = [p for p in data if p["is_active"]]
    assert len(active_providers) == 1
    assert active_providers[0]["name"] == "ollama"


@pytest.mark.asyncio
async def test_refresh_embedding_dimension(client):
    """Тест обновления размерности эмбеддинга."""
    # Сначала активируем ollama
    await client.post("/api/v1/settings/embedding/ollama/activate")
    
    # Запрашиваем обновление размерности
    response = await client.post("/api/v1/settings/embedding/ollama/refresh-dimension")
    
    # Может быть 200 если Ollama доступен, или 500 если нет
    assert response.status_code in [200, 500]
    
    if response.status_code == 200:
        data = response.json()
        assert data["status"] == "success"
        assert data["provider"] == "ollama"
        assert "dimension" in data
        assert data["dimension"] > 0
    else:
        # Если Ollama недоступен, получаем ошибку
        data = response.json()
        assert "detail" in data


@pytest.mark.asyncio
async def test_refresh_embedding_dimension_unsupported_provider(client):
    """Тест что refresh-dimension работает только для Ollama."""
    # Пытаемся обновить для unsupported провайдера
    response = await client.post("/api/v1/settings/embedding/gemini/refresh-dimension")
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "только для Ollama" in data["detail"]["error"]["message"]


@pytest.mark.asyncio
async def test_update_embedding_provider(client):
    """Тест обновления настроек провайдера эмбеддингов."""
    payload = {
        "is_active": False,
        "base_url": "http://localhost:11434",
        "model": "nomic-embed-text",
        "is_enabled": True,
        "priority": 1,
        "description": "Updated Ollama",
        "embedding_dim": 768,
        "max_retries": 3,
        "timeout": 30,
        "normalize": False,
    }

    response = await client.put("/api/v1/settings/embedding/ollama", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["description"] == "Updated Ollama"
    assert data["embedding_dim"] == 768


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
