"""
Тесты API endpoints.
"""


def test_root_endpoint(test_client):
    """Проверка корневого endpoint."""
    response = test_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert data["name"] == "TgBrain API"


def test_health_endpoint(test_client):
    """Проверка /health endpoint."""
    response = test_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "components" in data
    assert "timestamp" in data


def test_health_components(test_client):
    """Проверка компонентов health."""
    response = test_client.get("/health")
    data = response.json()

    components = data["components"]
    assert "database" in components
    assert "ollama_embeddings" in components
    assert "llm" in components
    assert "telegram" in components
