"""
Unit тесты для POST /api/v1/ask endpoint.

Покрывают:
- Успешные сценарии поиска (с моками UseCase)
- Error scenarios (RAG-002, RAG-005..RAG-008)
- Валидация параметров
"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from src.application.exceptions import (
    ChatNotFoundError,
    DatabaseError,
    EmbeddingGenerationError,
    LLMGenerationError,
    NoResultsFoundError,
)
from src.application.usecases.ask_question import AskQuestionUseCase, AskResult
from src.application.usecases.result import Failure, Success


@pytest.fixture
def mock_ask_usecase():
    mock = AsyncMock(spec=AskQuestionUseCase)
    mock.execute.return_value = Success(
        AskResult(
            answer="Тестовый ответ на вопрос пользователя",
            sources=[
                {
                    'id': 1,
                    'type': 'message',
                    'text': 'Тестовое сообщение для проверки RAG поиска',
                    'date': datetime(2026, 3, 18, 12, 0, 0).isoformat(),
                    'chat_title': 'Test Chat',
                    'link': 'https://t.me/test/1',
                    'similarity_score': 0.9,
                    'is_expanded': False,
                    'grouped_count': 1,
                }
            ],
            query="Тестовый вопрос",
            search_source="messages",
            total_found=1,
            context_expanded=False,
        )
    )
    return mock


@pytest.fixture
def mock_empty_result_usecase():
    mock = AsyncMock(spec=AskQuestionUseCase)
    mock.execute.return_value = Failure(
        NoResultsFoundError("unique query", "messages")
    )
    return mock


class TestAskEndpointSuccess:
    @pytest.mark.asyncio
    async def test_ask_success(self, test_client, mock_ask_usecase, app):
        app.state.ask_usecase = mock_ask_usecase

        response = test_client.post(
            "/api/v1/ask",
            json={"question": "Тестовый вопрос"}
        )

        assert response.status_code == 200
        data = response.json()

        assert 'answer' in data
        assert 'sources' in data
        assert 'query' in data
        assert 'metadata' in data
        assert len(data['sources']) > 0

        source = data['sources'][0]
        assert 'id' in source
        assert 'type' in source
        assert 'text' in source

    @pytest.mark.asyncio
    async def test_ask_with_chat_id(self, test_client, mock_ask_usecase, app):
        app.state.ask_usecase = mock_ask_usecase

        response = test_client.post(
            "/api/v1/ask",
            json={
                "question": "Тестовый вопрос",
                "chat_id": -1001234567890
            }
        )

        assert response.status_code == 200
        mock_ask_usecase.execute.assert_called_once()
        call_args = mock_ask_usecase.execute.call_args[0][0]
        assert call_args.chat_id == -1001234567890

    @pytest.mark.asyncio
    async def test_ask_search_summaries(self, test_client, mock_ask_usecase, app):
        app.state.ask_usecase = mock_ask_usecase

        response = test_client.post(
            "/api/v1/ask",
            json={
                "question": "Тестовый вопрос",
                "search_in": "summaries"
            }
        )

        assert response.status_code == 200
        call_args = mock_ask_usecase.execute.call_args[0][0]
        assert call_args.search_in == "summaries"

    @pytest.mark.asyncio
    async def test_ask_search_both(self, test_client, mock_ask_usecase, app):
        app.state.ask_usecase = mock_ask_usecase

        response = test_client.post(
            "/api/v1/ask",
            json={
                "question": "Тестовый вопрос",
                "search_in": "both"
            }
        )

        assert response.status_code == 200
        call_args = mock_ask_usecase.execute.call_args[0][0]
        assert call_args.search_in == "both"

    @pytest.mark.asyncio
    async def test_ask_expand_context(self, test_client, mock_ask_usecase, app):
        app.state.ask_usecase = mock_ask_usecase

        response = test_client.post(
            "/api/v1/ask",
            json={
                "question": "Тестовый вопрос",
                "expand_context": True,
                "context_window": 3
            }
        )

        assert response.status_code == 200
        call_args = mock_ask_usecase.execute.call_args[0][0]
        assert call_args.expand_context is True
        assert call_args.context_window == 3


class TestAskEndpointValidation:
    @pytest.mark.asyncio
    async def test_ask_empty_question(self, test_client, app):
        response = test_client.post(
            "/api/v1/ask",
            json={"question": ""}
        )

        assert response.status_code == 422
        data = response.json()
        assert 'detail' in data

    @pytest.mark.asyncio
    async def test_ask_long_question(self, test_client, app):
        long_question = "Т" * 1001

        response = test_client.post(
            "/api/v1/ask",
            json={"question": long_question}
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_ask_invalid_chat_id(self, test_client, mock_ask_usecase, app):
        mock_ask_usecase.execute.return_value = Failure(ChatNotFoundError(999999))
        app.state.ask_usecase = mock_ask_usecase

        response = test_client.post(
            "/api/v1/ask",
            json={
                "question": "Тестовый вопрос",
                "chat_id": 999999
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert 'detail' in data
        assert data['detail']['error']['code'] == 'RAG-002'
        assert data['detail']['error']['message'] == 'Chat not found'

    @pytest.mark.asyncio
    async def test_ask_invalid_search_in(self, test_client, app):
        response = test_client.post(
            "/api/v1/ask",
            json={
                "question": "Тестовый вопрос",
                "search_in": "invalid"
            }
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_ask_invalid_top_k_low(self, test_client, app):
        response = test_client.post(
            "/api/v1/ask",
            json={
                "question": "Тестовый вопрос",
                "top_k": 0
            }
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_ask_invalid_top_k_high(self, test_client, app):
        response = test_client.post(
            "/api/v1/ask",
            json={
                "question": "Тестовый вопрос",
                "top_k": 21
            }
        )

        assert response.status_code == 422


class TestAskEndpointErrors:
    @pytest.mark.asyncio
    async def test_ask_no_results(self, test_client, mock_empty_result_usecase, app):
        app.state.ask_usecase = mock_empty_result_usecase

        response = test_client.post(
            "/api/v1/ask",
            json={"question": "Уникальный вопрос которого нет в БД"}
        )

        assert response.status_code == 404
        data = response.json()
        assert 'detail' in data
        assert data['detail']['error']['code'] == 'RAG-005'

    @pytest.mark.asyncio
    async def test_ask_embedding_error(self, test_client, app):
        mock_usecase = AsyncMock(spec=AskQuestionUseCase)
        mock_usecase.execute.return_value = Failure(
            EmbeddingGenerationError("Embedding service down")
        )
        app.state.ask_usecase = mock_usecase

        response = test_client.post(
            "/api/v1/ask",
            json={"question": "Тестовый вопрос"}
        )

        assert response.status_code == 500
        data = response.json()
        assert 'detail' in data
        assert data['detail']['error']['code'] == 'RAG-006'

    @pytest.mark.asyncio
    async def test_ask_llm_error(self, test_client, app):
        mock_usecase = AsyncMock(spec=AskQuestionUseCase)
        mock_usecase.execute.return_value = Failure(
            LLMGenerationError("LLM generation failed")
        )
        app.state.ask_usecase = mock_usecase

        response = test_client.post(
            "/api/v1/ask",
            json={"question": "Тестовый вопрос"}
        )

        assert response.status_code == 500
        data = response.json()
        assert 'detail' in data
        assert data['detail']['error']['code'] == 'RAG-007'

    @pytest.mark.asyncio
    async def test_ask_database_error(self, test_client, app):
        mock_usecase = AsyncMock(spec=AskQuestionUseCase)
        mock_usecase.execute.return_value = Failure(
            DatabaseError("Connection refused")
        )
        app.state.ask_usecase = mock_usecase

        response = test_client.post(
            "/api/v1/ask",
            json={"question": "Тестовый вопрос"}
        )

        assert response.status_code == 500
        data = response.json()
        assert 'detail' in data
        assert data['detail']['error']['code'] == 'RAG-008'


class TestAskEndpointMetadata:
    @pytest.mark.asyncio
    async def test_ask_response_metadata(self, test_client, mock_ask_usecase, app):
        app.state.ask_usecase = mock_ask_usecase

        response = test_client.post(
            "/api/v1/ask",
            json={"question": "Тестовый вопрос"}
        )

        assert response.status_code == 200
        data = response.json()

        assert 'metadata' in data
        assert data['metadata']['search_source'] == 'messages'
        assert data['metadata']['total_found'] > 0
        assert 'context_expanded' in data['metadata']

    @pytest.mark.asyncio
    async def test_ask_response_source_fields(self, test_client, mock_ask_usecase, app):
        app.state.ask_usecase = mock_ask_usecase

        response = test_client.post(
            "/api/v1/ask",
            json={"question": "Тестовый вопрос"}
        )

        assert response.status_code == 200
        data = response.json()

        source = data['sources'][0]

        assert 'id' in source
        assert 'type' in source
        assert 'text' in source
        assert 'date' in source
        assert 'chat_title' in source
        assert 'link' in source or source.get('link') is None
        assert 'similarity_score' in source
        assert 'is_expanded' in source
        assert 'grouped_count' in source
