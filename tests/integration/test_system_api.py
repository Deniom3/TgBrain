"""
Тесты для System API endpoints.

Проверка endpoints:
- GET /api/v1/system/throughput
- GET /api/v1/system/stats
- GET /api/v1/system/flood-history
- GET /api/v1/system/request-history
"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.rate_limiter import TelegramRateLimiter, RateLimitConfig, RequestPriority

pytestmark = pytest.mark.integration


@pytest.fixture
def rate_limiter():
    """Mock Rate Limiter для тестов."""
    config = RateLimitConfig()
    limiter = TelegramRateLimiter(config)
    return limiter


@pytest.fixture
async def test_client():
    """Создать тестовый FastAPI клиент."""
    from main import app
    
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def client(rate_limiter, test_client):
    """Тестовый клиент с Rate Limiter."""
    from main import app
    app.state.rate_limiter = rate_limiter
    return test_client


class TestSystemEndpoints:

    @pytest.mark.asyncio
    async def test_get_throughput(self, client):
        """Тест endpoint /api/v1/system/throughput."""
        response = await client.get("/api/v1/system/throughput")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "requests_per_minute" in data
        assert "requests_per_hour" in data
        assert "success_count" in data
        assert "error_count" in data
        assert "avg_execution_time_ms" in data
        assert "flood_wait_count" in data
        
    @pytest.mark.asyncio
    async def test_get_system_stats(self, client, rate_limiter):
        """Тест endpoint /api/v1/system/stats."""
        # Выполняем несколько запросов для статистики
        async def dummy():
            return "ok"
        
        await rate_limiter.execute(RequestPriority.NORMAL, dummy)
        
        response = await client.get("/api/v1/system/stats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total_requests" in data
        assert "success_requests" in data
        assert "failed_requests" in data
        assert "flood_wait_incidents" in data
        assert "current_batch_size" in data
        assert "is_throttled" in data
        assert "throttle_remaining_seconds" in data
        
    @pytest.mark.asyncio
    async def test_get_flood_history(self, client):
        """Тест endpoint /api/v1/system/flood-history."""
        response = await client.get("/api/v1/system/flood-history")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "incidents" in data
        assert "total" in data
        assert "stats" in data
        
    @pytest.mark.asyncio
    async def test_get_flood_history_with_params(self, client):
        """Тест endpoint /api/v1/system/flood-history с параметрами."""
        response = await client.get("/api/v1/system/flood-history?limit=10&include_stats=false")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["incidents"]) <= 10
        assert data["stats"] == {}
        
    @pytest.mark.asyncio
    async def test_get_request_history(self, client):
        """Тест endpoint /api/v1/system/request-history."""
        response = await client.get("/api/v1/system/request-history")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "requests" in data
        assert "total" in data
        
    @pytest.mark.asyncio
    async def test_get_request_history_with_limit(self, client):
        """Тест endpoint /api/v1/system/request-history с limit."""
        response = await client.get("/api/v1/system/request-history?limit=5")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["requests"]) <= 5


class TestReindexSpeedEndpoints:

    @pytest.mark.asyncio
    async def test_get_reindex_speed(self, client):
        """Тест endpoint /api/v1/settings/reindex/speed."""
        response = await client.get("/api/v1/settings/reindex/speed")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "speed_mode" in data
        assert "batch_size" in data
        assert "delay_between_batches" in data
        assert "description" in data
        
    @pytest.mark.asyncio
    async def test_update_reindex_speed_low(self, client):
        """Тест обновления режима на low."""
        # Сначала установим medium чтобы сбросить любое предыдущее состояние
        await client.patch(
            "/api/v1/settings/reindex/speed",
            json={"speed_mode": "medium"}
        )
        
        # Теперь устанавливаем low
        response = await client.patch(
            "/api/v1/settings/reindex/speed",
            json={"speed_mode": "low"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["speed_mode"] == "low"
        assert data["batch_size"] == 20
        assert data["delay_between_batches"] == 3.0
        
    @pytest.mark.asyncio
    async def test_update_reindex_speed_medium(self, client):
        """Тест обновления режима на medium."""
        response = await client.patch(
            "/api/v1/settings/reindex/speed",
            json={"speed_mode": "medium"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["speed_mode"] == "medium"
        assert data["batch_size"] == 50
        assert data["delay_between_batches"] == 1.0
        
    @pytest.mark.asyncio
    async def test_update_reindex_speed_aggressive(self, client):
        """Тест обновления режима на aggressive."""
        # Сначала установим medium чтобы сбросить любое предыдущее состояние
        await client.patch(
            "/api/v1/settings/reindex/speed",
            json={"speed_mode": "medium"}
        )
        
        # Теперь устанавливаем aggressive
        response = await client.patch(
            "/api/v1/settings/reindex/speed",
            json={"speed_mode": "aggressive"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["speed_mode"] == "aggressive"
        assert data["batch_size"] == 100
        assert data["delay_between_batches"] == 0.5
        
    @pytest.mark.asyncio
    async def test_update_reindex_speed_invalid(self, client):
        """Тест обновления с невалидным режимом."""
        response = await client.patch(
            "/api/v1/settings/reindex/speed",
            json={"speed_mode": "invalid"}
        )
        
        assert response.status_code == 422  # Validation error
