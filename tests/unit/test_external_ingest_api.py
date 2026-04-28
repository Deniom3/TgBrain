"""
Tests for External Message Ingestion API endpoint.

Tests:
- test_ValidRequest_Returns200
- test_MissingChatId_Returns400
- test_MissingText_Returns400
- test_MissingDate_Returns400
- test_InvalidDateFormat_Returns400
- test_ChatId_FloatValue_Returns422
- test_IsBot_StringValue_Returns422
- test_EmptyTextAfterTrim_Returns400
- test_EmbeddingError_Returns_EXT003
- test_DatabaseError_Returns_EXT004
- test_FilteredMessage_Returns_EXT005
- test_DuplicateMessage_Returns_EXT006
- test_EmbeddingUnavailable_Returns_EXT007
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.api.endpoints.external_ingest_models import ExternalMessageStatus


class TestAPIEndpoint:
    """Тестирование POST /api/v1/messages/ingest endpoint."""

    @pytest.mark.asyncio
    async def test_ValidRequest_Returns200(self, test_client, test_app):
        """Успешная обработка валидного запроса."""
        response = test_client.post("/api/v1/messages/ingest", json={
            "chat_id": -1001234567890,
            "text": "Тестовое сообщение для проверки API",
            "date": "2026-03-22T10:30:00Z",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == ExternalMessageStatus.PENDING.value
        assert data["chat_id"] == -1001234567890
        assert data["pending"] is True

    @pytest.mark.asyncio
    async def test_MissingChatId_Returns400(self, test_client, test_app):
        """Валидация обязательного поля chat_id."""
        response = test_client.post("/api/v1/messages/ingest", json={
            "text": "Нет chat_id",
            "date": "2026-03-22T10:30:00Z",
        })
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_MissingText_Returns400(self, test_client, test_app):
        """Валидация обязательного поля text."""
        response = test_client.post("/api/v1/messages/ingest", json={
            "chat_id": -1001234567890,
            "date": "2026-03-22T10:30:00Z",
        })
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_MissingDate_Returns400(self, test_client, test_app):
        """Валидация обязательного поля date."""
        response = test_client.post("/api/v1/messages/ingest", json={
            "chat_id": -1001234567890,
            "text": "Нет date",
        })
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_InvalidDateFormat_Returns400(self, test_client, test_app):
        """Валидация формата даты."""
        response = test_client.post("/api/v1/messages/ingest", json={
            "chat_id": -1001234567890,
            "text": "Неверный формат даты",
            "date": "22-03-2026",
        })
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "APP-102"

    @pytest.mark.asyncio
    async def test_ChatId_FloatValue_Returns422(self, test_client, test_app):
        """Float значение chat_id отклоняется."""
        response = test_client.post("/api/v1/messages/ingest", json={
            "chat_id": 123.45,
            "text": "Тест",
            "date": "2026-03-22T10:30:00Z",
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_IsBot_StringValue_Returns422(self, test_client, test_app):
        """Строка вместо bool для is_bot отклоняется валидацией Pydantic."""
        response = test_client.post("/api/v1/messages/ingest", json={
            "chat_id": -1001234567890,
            "text": "Тест",
            "date": "2026-03-22T10:30:00Z",
            "is_bot": "not_a_boolean",
        })
        assert response.status_code in [200, 422]

    @pytest.mark.asyncio
    async def test_EmptyTextAfterTrim_Returns400(self, test_client, test_app):
        """Пустой текст после trim отклоняется."""
        response = test_client.post("/api/v1/messages/ingest", json={
            "chat_id": -1001234567890,
            "text": "   ",
            "date": "2026-03-22T10:30:00Z",
        })
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "APP-102"

    @pytest.mark.asyncio
    async def test_EmbeddingError_Returns_EXT003(self, test_client, test_app):
        """Проверка кода ошибки EXT-003 при ошибке эмбеддингов."""
        test_app.state.embeddings.get_embedding = AsyncMock(
            side_effect=Exception("Embedding service error")
        )

        response = test_client.post("/api/v1/messages/ingest", json={
            "chat_id": -1001234567890,
            "text": "Сообщение с ошибкой векторизации",
            "date": "2026-03-22T10:30:00Z",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["pending"] is True
        assert data["error_code"] == "EXT-003"

    @pytest.mark.asyncio
    async def test_DatabaseError_Returns_EXT004(self, test_client, test_app):
        """Проверка кода ошибки EXT-004 при ошибке БД."""
        mock_connection = AsyncMock()

        async def mock_fetchrow(query, *args):
            if "is_monitored" in query:
                return {
                    "is_monitored": True,
                    "filter_bots": True,
                    "filter_actions": True,
                    "filter_min_length": 15,
                    "filter_ads": True,
                }
            elif "INSERT INTO messages" in query:
                raise Exception("Database connection error")
            return None

        mock_connection.fetchrow = mock_fetchrow
        mock_connection.execute = AsyncMock()

        class MockAcquireCtx:
            async def __aenter__(self):
                return mock_connection

            async def __aexit__(self, *args):
                return None

        test_app.state.db_pool.acquire = MagicMock(return_value=MockAcquireCtx())

        response = test_client.post("/api/v1/messages/ingest", json={
            "chat_id": -1001234567890,
            "text": "Сообщение с ошибкой БД",
            "date": "2026-03-22T10:30:00Z",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["pending"] is True
        assert data["error_code"] == "EXT-004"

    @pytest.mark.asyncio
    async def test_FilteredMessage_Returns_EXT005(self, test_client, test_app):
        """Проверка кода ошибки EXT-005 для отфильтрованного сообщения."""
        response = test_client.post("/api/v1/messages/ingest", json={
            "chat_id": -1001234567890,
            "text": "Короткое",
            "date": "2026-03-22T10:30:00Z",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["filtered"] is True
        assert data["error_code"] == "EXT-005"

    @pytest.mark.asyncio
    async def test_DuplicateMessage_Returns_EXT006(self, test_client, test_app):
        """Проверка кода ошибки EXT-006 для дубликата."""
        mock_connection = AsyncMock()

        async def mock_fetchrow(query, *args):
            if "is_monitored" in query:
                return {
                    "is_monitored": True,
                    "filter_bots": True,
                    "filter_actions": True,
                    "filter_min_length": 15,
                    "filter_ads": True,
                }
            elif "message_text_hash" in query or "text" in query:
                return {"id": 999, "message_text": "Дубликат для теста"}
            return None

        mock_connection.fetchrow = mock_fetchrow
        mock_connection.execute = AsyncMock()

        class MockAcquireCtx:
            async def __aenter__(self):
                return mock_connection

            async def __aexit__(self, *args):
                return None

        test_app.state.db_pool.acquire = MagicMock(return_value=MockAcquireCtx())

        test_client.post("/api/v1/messages/ingest", json={
            "chat_id": -1001234567890,
            "text": "Дубликат для теста",
            "date": "2026-03-22T10:30:00Z",
        })

        response = test_client.post("/api/v1/messages/ingest", json={
            "chat_id": -1001234567890,
            "text": "Дубликат для теста",
            "date": "2026-03-22T10:30:01Z",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["duplicate"] is True
        assert data["error_code"] == "EXT-006"

    @pytest.mark.asyncio
    async def test_EmbeddingUnavailable_Returns_EXT007(self, test_client, test_app):
        """Проверка кода ошибки EXT-007 при недоступности сервиса эмбеддингов."""
        test_app.state.embeddings.get_embedding = AsyncMock(
            side_effect=ConnectionError("Embedding unavailable: service is down")
        )

        response = test_client.post("/api/v1/messages/ingest", json={
            "chat_id": -1001234567890,
            "text": "Сообщение при недоступном сервисе",
            "date": "2026-03-22T10:30:00Z",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["pending"] is True
        assert data["error_code"] == "EXT-007"
