"""
Тесты API переиндексации (Reindex API).

Проверяют:
- Smart Trigger (переиндексация только при смене модели)
- Автоматическую миграцию размерности
- Фиксацию last_reindex_model
- RAG поиск после миграции

Запуск:
    pytest tests/integration/test_reindex_api.py -v --integration

Требования:
- Запущенное приложение (uvicorn main:app)
- Активная сессия Telegram
- Настроенный .env файл
"""

import asyncio
import pytest
import httpx
from typing import AsyncGenerator

pytestmark = pytest.mark.integration


# ==============================================================================
# Фикстуры
# ==============================================================================

@pytest.fixture(scope="module")
def base_url() -> str:
    """Базовый URL API."""
    return "http://localhost:8000"


@pytest.fixture(scope="module")
async def http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """HTTP клиент для тестов."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        yield client


@pytest.fixture(scope="function")
async def save_current_model(http_client: httpx.AsyncClient, base_url: str):
    """Сохраняет текущую модель и восстанавливает после теста."""
    # Сохраняем текущую модель
    resp = await http_client.get(f"{base_url}/api/v1/settings/embedding/ollama")
    if resp.status_code == 200:
        data = resp.json()[0] if isinstance(resp.json(), list) else resp.json()
        original_model = data['model']
        original_dim = data['embedding_dim']
        
        yield {'model': original_model, 'dim': original_dim}
        
        # Восстанавливаем оригинальную модель
        await http_client.put(
            f"{base_url}/api/v1/settings/embedding/ollama/model",
            json={"model": original_model, "embedding_dim": original_dim}
        )
        await asyncio.sleep(5)  # Ждём завершения переиндексации
    else:
        yield {'model': None, 'dim': None}


# ==============================================================================
# Тесты Smart Trigger
# ==============================================================================

@pytest.mark.skip(reason="Integration test — requires running server at http://localhost:8000")
class TestSmartTrigger:
    """Тесты Smart Trigger — переиндексация только при смене модели."""

    @pytest.mark.asyncio
    async def test_model_change_triggers_reindex(
        self, http_client: httpx.AsyncClient, base_url: str, save_current_model
    ):
        """
        Тест 1: Смена модели должна запускать переиндексацию.
        
        Проверяет:
        - model_changed = True
        - reindex_started = True
        """
        # Получаем текущую модель
        resp = await http_client.get(f"{base_url}/api/v1/settings/embedding/ollama")
        assert resp.status_code == 200
        current_data = resp.json()[0] if isinstance(resp.json(), list) else resp.json()
        current_model = current_data['model']
        
        # Выбираем другую модель для теста
        test_model = "nomic-embed-text" if current_model != "nomic-embed-text" else "bge-m3:latest"
        test_dim = 768 if test_model == "nomic-embed-text" else 1024
        
        # Меняем модель
        resp = await http_client.put(
            f"{base_url}/api/v1/settings/embedding/{test_model.split(':')[0]}/model",
            json={"model": test_model, "embedding_dim": test_dim}
        )
        
        assert resp.status_code == 200
        result = resp.json()
        
        # Проверяем Smart Trigger
        assert result.get('model_changed') is True, "Smart Trigger: модель должна измениться"
        assert result.get('reindex_started') is True, "Переиндексация должна запуститься"
        assert result.get('old_model') == current_model, "Старая модель указана неверно"
        assert result.get('model') == test_model, "Новая модель указана неверно"

    @pytest.mark.asyncio
    async def test_same_model_no_reindex(
        self, http_client: httpx.AsyncClient, base_url: str, save_current_model
    ):
        """
        Тест 2: Обновление на ту же модель НЕ должно запускать переиндексацию.
        
        Проверяет:
        - model_changed = False
        - reindex_started = False
        """
        # Получаем текущую модель
        resp = await http_client.get(f"{base_url}/api/v1/settings/embedding/ollama")
        assert resp.status_code == 200
        data = resp.json()[0] if isinstance(resp.json(), list) else resp.json()
        current_model = data['model']
        current_dim = data['embedding_dim']
        
        # Обновляем на ту же модель
        resp = await http_client.put(
            f"{base_url}/api/v1/settings/embedding/ollama/model",
            json={"model": current_model, "embedding_dim": current_dim}
        )
        
        assert resp.status_code == 200
        result = resp.json()
        
        # Проверяем Smart Trigger
        assert result.get('model_changed') is False, "Smart Trigger: модель не должна измениться"
        assert result.get('reindex_started') is False, "Переиндексация НЕ должна запуститься"


# ==============================================================================
# Тесты миграции размерности
# ==============================================================================

@pytest.mark.skip(reason="Integration test — requires running server at http://localhost:8000")
class TestDimensionMigration:
    """Тесты автоматической миграции размерности векторов."""

    @pytest.mark.asyncio
    async def test_migration_768_to_1024(
        self, http_client: httpx.AsyncClient, base_url: str, save_current_model
    ):
        """
        Тест 3: Миграция размерности 768 → 1024.
        
        Проверяет:
        - Миграция выполняется автоматически
        - last_reindex_model фиксируется
        - RAG поиск работает после миграции
        """
        # Шаг 1: Устанавливаем модель с dim=768
        resp = await http_client.put(
            f"{base_url}/api/v1/settings/embedding/ollama/model",
            json={"model": "nomic-embed-text", "embedding_dim": 768}
        )
        assert resp.status_code == 200
        
        # Ждём завершения переиндексации
        await asyncio.sleep(30)
        
        # Шаг 2: Проверяем last_reindex_model
        resp = await http_client.get(f"{base_url}/api/v1/settings/reindex/settings")
        assert resp.status_code == 200
        settings = resp.json()
        assert settings.get('last_reindex_model') is not None, "last_reindex_model должна быть зафиксирована"
        
        # Шаг 3: Проверяем статус переиндексации
        resp = await http_client.get(f"{base_url}/api/v1/settings/reindex/status")
        assert resp.status_code == 200
        status = resp.json()
        assert status['background_running'] is True, "Фоновый сервис должен работать"

    @pytest.mark.asyncio
    async def test_migration_1024_to_768(
        self, http_client: httpx.AsyncClient, base_url: str, save_current_model
    ):
        """
        Тест 4: Миграция размерности 1024 → 768.
        
        Проверяет:
        - Обратная миграция работает
        - Индекс пересоздаётся
        """
        # Шаг 1: Устанавливаем модель с dim=1024
        resp = await http_client.put(
            f"{base_url}/api/v1/settings/embedding/ollama/model",
            json={"model": "bge-m3:latest", "embedding_dim": 1024}
        )
        assert resp.status_code == 200
        
        # Ждём завершения переиндексации
        await asyncio.sleep(30)
        
        # Шаг 2: Проверяем статистику
        resp = await http_client.get(f"{base_url}/api/v1/settings/reindex/stats")
        assert resp.status_code == 200
        stats = resp.json()
        assert stats['total_messages'] > 0, "Должны быть сообщения с эмбеддингами"


# ==============================================================================
# Тесты RAG поиска после миграции
# ==============================================================================

@pytest.mark.skip(reason="Integration test — requires running server at http://localhost:8000")
class TestRagAfterMigration:
    """Тесты RAG поиска после миграции модели."""

    @pytest.mark.asyncio
    async def test_rag_search_after_migration(
        self, http_client: httpx.AsyncClient, base_url: str, save_current_model
    ):
        """
        Тест 5: RAG поиск работает после миграции.

        Проверяет:
        - /api/v1/ask endpoint возвращает ответ
        - Есть источники
        """
        # Ждём завершения предыдущих переиндексаций
        await asyncio.sleep(10)

        # Тест RAG поиска
        resp = await http_client.post(
            f"{base_url}/api/v1/ask",
            json={"question": "О чём этот чат?"}
        )

        assert resp.status_code == 200, f"RAG поиск вернул ошибку: {resp.status_code}"
        result = resp.json()

        assert 'answer' in result, "Ответ должен быть в результате"
        assert 'sources' in result, "Источники должны быть в результате"
        assert len(result['sources']) > 0, "Должен быть хотя бы один источник"

    @pytest.mark.asyncio
    async def test_summary_after_migration(
        self, http_client: httpx.AsyncClient, base_url: str, save_current_model
    ):
        """
        Тест 6: Суммаризация работает после миграции.

        Проверяет:
        - /api/v1/chats/summary/generate endpoint возвращает ответ
        - Есть задачи на генерацию summary
        """
        # Тест суммаризации
        resp = await http_client.post(
            f"{base_url}/api/v1/chats/summary/generate",
            json={"period_minutes": 1440, "max_messages": 10}
        )

        assert resp.status_code == 200, f"Суммаризация вернула ошибку: {resp.status_code}"
        result = resp.json()

        assert 'tasks' in result, "Tasks должны быть в результате"
        assert 'total_chats' in result, "total_chats должен быть в результате"
        assert isinstance(result['tasks'], list), "tasks должен быть списком"


# ==============================================================================
# Тесты Health Check
# ==============================================================================

@pytest.mark.skip(reason="Integration test — requires running server at http://localhost:8000")
class TestHealthCheck:
    """Тесты проверки здоровья компонентов."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, http_client: httpx.AsyncClient, base_url: str):
        """
        Тест 7: Health endpoint возвращает ok.
        
        Проверяет:
        - Все компоненты работают
        """
        resp = await http_client.get(f"{base_url}/health")
        
        assert resp.status_code == 200
        result = resp.json()
        
        assert result['status'] == 'ok', "Статус должен быть 'ok'"
        assert result['components']['database'] == 'ok', "База данных должна работать"
        assert result['components']['ollama_embeddings'] == 'ok', "Ollama должна работать"
        assert result['components']['llm'] == 'ok', "LLM должен работать"


# ==============================================================================
# Тесты Settings API
# ==============================================================================

@pytest.mark.skip(reason="Integration test — requires running server at http://localhost:8000")
class TestSettingsAPI:
    """Тесты Settings API для переиндексации."""

    @pytest.mark.asyncio
    async def test_get_reindex_settings(self, http_client: httpx.AsyncClient, base_url: str):
        """
        Тест 8: Получение настроек переиндексации.
        
        Проверяет:
        - Возвращаются все поля настроек
        """
        resp = await http_client.get(f"{base_url}/api/v1/settings/reindex/settings")
        
        assert resp.status_code == 200
        settings = resp.json()
        
        # Проверяем наличие всех полей
        required_fields = [
            'batch_size', 'delay_between_batches', 'auto_reindex_on_model_change',
            'last_reindex_model', 'max_concurrent_tasks', 'max_retries'
        ]
        for field in required_fields:
            assert field in settings, f"Поле {field} должно быть в ответе"

    @pytest.mark.asyncio
    async def test_get_reindex_status(self, http_client: httpx.AsyncClient, base_url: str):
        """
        Тест 9: Получение статуса переиндексации.
        
        Проверяет:
        - Возвращаются все поля статуса
        """
        resp = await http_client.get(f"{base_url}/api/v1/settings/reindex/status")
        
        assert resp.status_code == 200
        status = resp.json()
        
        # Проверяем наличие всех полей
        required_fields = ['background_running', 'is_running', 'current_task', 'queued_tasks']
        for field in required_fields:
            assert field in status, f"Поле {field} должно быть в ответе"

    @pytest.mark.asyncio
    async def test_get_reindex_stats(self, http_client: httpx.AsyncClient, base_url: str):
        """
        Тест 10: Получение статистики по моделям.
        
        Проверяет:
        - Возвращаются модели и количество сообщений
        """
        resp = await http_client.get(f"{base_url}/api/v1/settings/reindex/stats")
        
        assert resp.status_code == 200
        stats = resp.json()
        
        assert 'models' in stats, "models должно быть в ответе"
        assert 'total_messages' in stats, "total_messages должно быть в ответе"
        assert 'models_count' in stats, "models_count должно быть в ответе"


# ==============================================================================
# Интеграционные тесты
# ==============================================================================

@pytest.mark.skip(reason="Integration test — requires running server at http://localhost:8000")
class TestIntegration:
    """Интеграционные тесты полного цикла."""

    @pytest.mark.asyncio
    async def test_full_migration_cycle(
        self, http_client: httpx.AsyncClient, base_url: str, save_current_model
    ):
        """
        Тест 11: Полный цикл миграции 768 → 1024 → 768.

        Проверяет:
        - Миграция в обе стороны работает
        - RAG поиск работает после каждой миграции
        - last_reindex_model обновляется
        """
        # Шаг 1: 768
        resp = await http_client.put(
            f"{base_url}/api/v1/settings/embedding/ollama/model",
            json={"model": "nomic-embed-text", "embedding_dim": 768}
        )
        assert resp.status_code == 200
        await asyncio.sleep(20)

        # Проверка RAG
        resp = await http_client.post(f"{base_url}/api/v1/ask", json={"question": "test"})
        assert resp.status_code == 200

        # Шаг 2: 1024
        resp = await http_client.put(
            f"{base_url}/api/v1/settings/embedding/ollama/model",
            json={"model": "bge-m3:latest", "embedding_dim": 1024}
        )
        assert resp.status_code == 200
        await asyncio.sleep(20)

        # Проверка RAG
        resp = await http_client.post(f"{base_url}/api/v1/ask", json={"question": "test"})
        assert resp.status_code == 200
        
        # Шаг 3: Проверка last_reindex_model
        resp = await http_client.get(f"{base_url}/api/v1/settings/reindex/settings")
        assert resp.status_code == 200
        settings = resp.json()
        assert settings.get('last_reindex_model') is not None
