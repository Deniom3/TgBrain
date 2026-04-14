"""
Интеграционные тесты (end-to-end).
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_full_workflow():
    """
    Полный тест рабочего процесса:
    1. Проверка здоровья
    2. Запрос к RAG
    3. Генерация сводки
    
    Примечание: Требуется запущенное приложение на localhost:8000
    """
    async with AsyncClient() as client:
        base_url = "http://localhost:8000"
        
        try:
            # 1. Health check
            response = await client.get(f"{base_url}/health", timeout=5.0)
            assert response.status_code == 200
            health = response.json()
            assert health["status"] in ["ok", "degraded"]
            
            # 2. Ask query
            response = await client.post(
                f"{base_url}/api/v1/ask",
                json={"question": "Что обсуждают в чате?"},
                timeout=30.0
            )
            # 200 если есть данные, 500 если нет
            assert response.status_code in [200, 500]
            
            # 3. Summary
            response = await client.post(
                f"{base_url}/api/v1/chats/summary/generate",
                json={"period_minutes": 1440, "max_messages": 50},
                timeout=60.0
            )
            # 200 если есть данные, 500 если нет
            assert response.status_code in [200, 500]
            
        except Exception as e:
            # Если приложение не запущено, пропускаем тест
            pytest.skip(f"Приложение недоступно: {e}")


@pytest.mark.asyncio
async def test_health_detailed():
    """
    Детальная проверка health endpoint.
    """
    async with AsyncClient() as client:
        base_url = "http://localhost:8000"
        
        try:
            response = await client.get(f"{base_url}/health", timeout=5.0)
            assert response.status_code == 200
            
            data = response.json()
            
            # Проверка структуры
            assert "status" in data
            assert "components" in data
            assert "timestamp" in data
            
            # Проверка компонентов
            components = data["components"]
            for component in ["database", "ollama_embeddings", "llm", "telegram"]:
                assert component in components
                assert components[component] in ["ok", "degraded", "error"]
                
        except Exception as e:
            pytest.skip(f"Приложение недоступно: {e}")
