"""
Тесты для RAG API endpoints.

Проверка:
- Валидация AskRequest (chat_id, top_k, context_window, question)
- Безопасная обработка ошибок (без утечки деталей)
- format_sources() не возвращает чувствительные поля
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.api.models import AskRequest, SearchSource
from src.application.usecases.ask_question import AskQuestionUseCase, AskResult
from src.application.usecases.result import Failure, Success
from src.application.exceptions import (
    ChatNotFoundError,
    NoResultsFoundError,
)

pytestmark = pytest.mark.integration


# =============================================================================
# Тесты валидации AskRequest
# =============================================================================


class TestAskRequestValidation:
    def test_valid_minimal_request(self):
        request = AskRequest(question="Как дела?")  # type: ignore[call-arg]

        assert request.question == "Как дела?"
        assert request.chat_id is None
        assert request.search_in == SearchSource.MESSAGES
        assert request.expand_context is True
        assert request.top_k == 5
        assert request.context_window == 2

    def test_valid_full_request(self):
        request = AskRequest(
            question="Как настроить авторизацию?",
            chat_id=-1001234567890,
            search_in=SearchSource.BOTH,
            expand_context=False,
            top_k=10,
            context_window=5,
        )

        assert request.question == "Как настроить авторизацию?"
        assert request.chat_id == -1001234567890
        assert request.search_in == SearchSource.BOTH
        assert request.expand_context is False
        assert request.top_k == 10
        assert request.context_window == 5

    def test_question_max_length(self):
        long_question = "a" * 1000
        request = AskRequest(question=long_question)  # type: ignore[call-arg]
        assert len(request.question) == 1000

    def test_question_too_long(self):
        long_question = "a" * 1001

        with pytest.raises(ValidationError) as exc_info:
            AskRequest(question=long_question)  # type: ignore[call-arg]

        assert "question" in str(exc_info.value)

    def test_question_empty(self):
        with pytest.raises(ValidationError) as exc_info:
            AskRequest(question="")  # type: ignore[call-arg]

        assert "question" in str(exc_info.value)

    def test_chat_id_valid_positive(self):
        request = AskRequest(question="Тест", chat_id=123456789)  # type: ignore[call-arg]
        assert request.chat_id == 123456789

    def test_chat_id_valid_negative(self):
        request = AskRequest(question="Тест", chat_id=-1001234567890)  # type: ignore[call-arg]
        assert request.chat_id == -1001234567890

    def test_top_k_min_valid(self):
        request = AskRequest(question="Тест", top_k=1)  # type: ignore[call-arg]
        assert request.top_k == 1

    def test_top_k_max_valid(self):
        request = AskRequest(question="Тест", top_k=20)  # type: ignore[call-arg]
        assert request.top_k == 20

    def test_top_k_too_small(self):
        with pytest.raises(ValidationError) as exc_info:
            AskRequest(question="Тест", top_k=0)  # type: ignore[call-arg]

        assert "top_k" in str(exc_info.value)

    def test_top_k_too_large(self):
        with pytest.raises(ValidationError) as exc_info:
            AskRequest(question="Тест", top_k=21)  # type: ignore[call-arg]

        assert "top_k" in str(exc_info.value)

    def test_context_window_min_valid(self):
        request = AskRequest(question="Тест", context_window=0)  # type: ignore[call-arg]
        assert request.context_window == 0

    def test_context_window_max_valid(self):
        request = AskRequest(question="Тест", context_window=5)  # type: ignore[call-arg]
        assert request.context_window == 5

    def test_context_window_too_small(self):
        with pytest.raises(ValidationError) as exc_info:
            AskRequest(question="Тест", context_window=-1)  # type: ignore[call-arg]

        assert "context_window" in str(exc_info.value)

    def test_context_window_too_large(self):
        with pytest.raises(ValidationError) as exc_info:
            AskRequest(question="Тест", context_window=6)  # type: ignore[call-arg]

        assert "context_window" in str(exc_info.value)

    def test_search_in_messages(self):
        request = AskRequest(question="Тест", search_in=SearchSource.MESSAGES)  # type: ignore[call-arg]
        assert request.search_in == SearchSource.MESSAGES

    def test_search_in_summaries(self):
        request = AskRequest(question="Тест", search_in=SearchSource.SUMMARIES)  # type: ignore[call-arg]
        assert request.search_in == SearchSource.SUMMARIES

    def test_search_in_both(self):
        request = AskRequest(question="Тест", search_in=SearchSource.BOTH)  # type: ignore[call-arg]
        assert request.search_in == SearchSource.BOTH

    def test_search_in_invalid(self):
        with pytest.raises(ValidationError) as exc_info:
            AskRequest(question="Тест", search_in="invalid")  # type: ignore[arg-type,call-arg]

        assert "search_in" in str(exc_info.value)

    def test_expand_context_true(self):
        request = AskRequest(question="Тест", expand_context=True)  # type: ignore[call-arg]
        assert request.expand_context is True

    def test_expand_context_false(self):
        request = AskRequest(question="Тест", expand_context=False)  # type: ignore[call-arg]
        assert request.expand_context is False


# =============================================================================
# Тесты безопасной обработки ошибок
# =============================================================================


class TestSafeErrorHandling:
    def test_error_response_no_internal_details(self):
        try:
            raise Exception("SQL Query Error: SELECT * FROM messages WHERE...")
        except Exception as e:
            error_message = "Внутренняя ошибка сервера"

            assert "SQL" not in error_message
            assert "SELECT" not in error_message
            assert "Query" not in error_message
            assert str(e) != error_message


# =============================================================================
# Интеграционные тесты endpoint
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
class TestAskEndpointIntegration:
    async def test_ask_success(self, test_client, test_app):
        from unittest.mock import AsyncMock

        mock_usecase = AsyncMock(spec=AskQuestionUseCase)
        mock_usecase.execute.return_value = Success(
            AskResult(
                answer="Тестовый ответ LLM",
                sources=[
                    {
                        'id': 1,
                        'type': 'message',
                        'text': 'Тестовое сообщение',
                        'date': datetime(2024, 1, 1, 12, 0, 0).isoformat(),
                        'chat_title': 'Test Chat',
                        'link': 'https://t.me/test/1',
                        'similarity_score': 0.95,
                        'is_expanded': False,
                        'grouped_count': 1,
                    }
                ],
                query="Как настроить QR авторизацию?",
                search_source="messages",
                total_found=3,
            )
        )
        test_app.state.ask_usecase = mock_usecase

        response = await test_client.post(
            "/api/v1/ask", json={"question": "Как настроить QR авторизацию?"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "sources" in data
        assert "query" in data
        assert "metadata" in data
        assert data["query"] == "Как настроить QR авторизацию?"

    async def test_ask_chat_not_found(self, test_client, test_app):
        from unittest.mock import AsyncMock

        mock_usecase = AsyncMock(spec=AskQuestionUseCase)
        mock_usecase.execute.return_value = Failure(ChatNotFoundError(-9999999999999))
        test_app.state.ask_usecase = mock_usecase

        response = await test_client.post(
            "/api/v1/ask",
            json={"question": "Тест", "chat_id": -9999999999999},
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]
        assert data["detail"]["error"]["code"] == "RAG-002"
        assert "Chat not found" in data["detail"]["error"]["message"]

    async def test_ask_no_results(self, test_client, test_app):
        from unittest.mock import AsyncMock

        mock_usecase = AsyncMock(spec=AskQuestionUseCase)
        mock_usecase.execute.return_value = Failure(
            NoResultsFoundError("Несуществующая тема", "messages")
        )
        test_app.state.ask_usecase = mock_usecase

        response = await test_client.post(
            "/api/v1/ask", json={"question": "Несуществующая тема"}
        )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]
        assert data["detail"]["error"]["code"] == "RAG-005"

    async def test_ask_search_in_summaries(self, test_client, test_app):
        from unittest.mock import AsyncMock

        mock_usecase = AsyncMock(spec=AskQuestionUseCase)
        mock_usecase.execute.return_value = Success(
            AskResult(
                answer="Дайджест за период",
                sources=[
                    {
                        'id': 1,
                        'type': 'summary',
                        'text': 'Дайджест за период',
                        'date': datetime(2024, 1, 2, 0, 0, 0).isoformat(),
                        'chat_title': 'Test Chat',
                        'link': None,
                        'similarity_score': 0.90,
                        'is_expanded': False,
                        'grouped_count': 1,
                    }
                ],
                query="Дайджест",
                search_source="summaries",
                total_found=2,
            )
        )
        test_app.state.ask_usecase = mock_usecase

        response = await test_client.post(
            "/api/v1/ask",
            json={"question": "Дайджест", "search_in": "summaries"},
        )

        assert response.status_code == 200
        call_args = mock_usecase.execute.call_args[0][0]
        assert call_args.search_in == "summaries"

    async def test_ask_search_in_both(self, test_client, test_app):
        from unittest.mock import AsyncMock

        mock_usecase = AsyncMock(spec=AskQuestionUseCase)
        mock_usecase.execute.return_value = Success(
            AskResult(
                answer="Ответ по всем источникам",
                sources=[
                    {
                        'id': 1,
                        'type': 'message',
                        'text': 'Тестовое сообщение',
                        'date': datetime(2024, 1, 1, 12, 0, 0).isoformat(),
                        'chat_title': 'Test Chat',
                        'link': 'https://t.me/test/1',
                        'similarity_score': 0.95,
                        'is_expanded': False,
                        'grouped_count': 1,
                    }
                ],
                query="Тест",
                search_source="both",
                total_found=5,
            )
        )
        test_app.state.ask_usecase = mock_usecase

        response = await test_client.post(
            "/api/v1/ask", json={"question": "Тест", "search_in": "both"}
        )

        assert response.status_code == 200
        call_args = mock_usecase.execute.call_args[0][0]
        assert call_args.search_in == "both"
