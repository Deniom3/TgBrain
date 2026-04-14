"""Тесты для AskResult dataclass."""

from src.application.usecases.ask_question import AskResult


class TestAskResultMinimalFields:
    def test_ask_result_minimal_fields(self) -> None:
        result = AskResult(
            answer="test answer",
            sources=[],
            query="test query",
            search_source="messages",
            total_found=0,
        )

        assert result.answer == "test answer"

    def test_ask_result_all_fields(self) -> None:
        sources = [{"id": 1, "type": "message", "text": "Test"}]
        result = AskResult(
            answer="full answer",
            sources=sources,
            query="test query",
            search_source="both",
            total_found=5,
            context_expanded=True,
        )

        assert result.answer == "full answer"
        assert result.sources == sources
        assert result.query == "test query"
        assert result.search_source == "both"
        assert result.total_found == 5
        assert result.context_expanded is True

    def test_ask_result_default_context_expanded(self) -> None:
        result = AskResult(
            answer="test",
            sources=[],
            query="test",
            search_source="messages",
            total_found=0,
        )

        assert result.context_expanded is False
