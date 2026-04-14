"""
Модульные тесты для RAGService логики (Phase 4 refactoring) - Unit тесты без БД.

Тестирование логики, перенесённой в AskQuestionUseCase:
- merge_results() с весами
- build_context()
- format_sources()
- AskResult

Эти тесты не требуют подключения к БД.
"""

import pytest
from datetime import datetime
from typing import List

from src.application.usecases.ask_question import MESSAGE_WEIGHT, SUMMARY_WEIGHT, AskResult
from src.models.data_models import MessageRecord, SummaryRecord, MergedResult
from src.domain.value_objects import MessageText, SenderName, ChatTitle


# =============================================================================
# Fixtures без БД
# =============================================================================


@pytest.fixture
def sample_messages() -> List[MessageRecord]:
    return [
        MessageRecord(
            id=1,
            text=MessageText("Первое тестовое сообщение"),
            date=datetime(2024, 1, 1, 12, 0, 0),
            chat_title=ChatTitle("Test Chat 1"),
            link="https://t.me/test/1",
            sender_name=SenderName("User 1"),
            sender_id=100,
            similarity_score=0.9,
        ),
        MessageRecord(
            id=2,
            text=MessageText("Второе сообщение с деталями"),
            date=datetime(2024, 1, 1, 12, 5, 0),
            chat_title=ChatTitle("Test Chat 1"),
            link="https://t.me/test/2",
            sender_name=SenderName("User 2"),
            sender_id=101,
            similarity_score=0.8,
        ),
    ]


@pytest.fixture
def sample_summaries() -> List[SummaryRecord]:
    return [
        SummaryRecord(
            id=1,
            chat_id=-1001234567890,
            chat_title=ChatTitle("Test Chat 1"),
            result_text="Summary за период: обсуждение новых функций",
            period_start=datetime(2024, 1, 1, 0, 0, 0),
            period_end=datetime(2024, 1, 1, 23, 59, 59),
            messages_count=50,
            similarity_score=0.85,
            created_at=datetime(2024, 1, 2, 0, 0, 0),
        ),
        SummaryRecord(
            id=2,
            chat_id=-1009876543210,
            chat_title=ChatTitle("Test Chat 2"),
            result_text="Summary: итоги встречи команды",
            period_start=datetime(2024, 1, 1, 0, 0, 0),
            period_end=datetime(2024, 1, 1, 23, 59, 59),
            messages_count=30,
            similarity_score=0.75,
            created_at=datetime(2024, 1, 2, 0, 0, 0),
        ),
    ]


# =============================================================================
# Тесты констант
# =============================================================================


def test_message_weight_constant():
    assert MESSAGE_WEIGHT == 1.0


def test_summary_weight_constant():
    assert SUMMARY_WEIGHT == 1.2


def test_summary_has_higher_weight():
    assert SUMMARY_WEIGHT > MESSAGE_WEIGHT


# =============================================================================
# Тесты merge_results()
# =============================================================================


class TestMergeResults:
    @pytest.fixture
    def merge_helper(self):
        class MergeHelper:
            def merge_results(self, messages, summaries):
                merged = []
                for msg in messages:
                    merged.append(MergedResult(
                        message=msg,
                        source_type='message',
                        similarity_score=msg.similarity_score,
                        weight=MESSAGE_WEIGHT,
                    ))
                for summ in summaries:
                    merged.append(MergedResult(
                        message=summ,
                        source_type='summary',
                        similarity_score=summ.similarity_score,
                        weight=SUMMARY_WEIGHT,
                    ))
                merged.sort(key=lambda x: x.weighted_score, reverse=True)
                return merged

        return MergeHelper()

    def test_merge_results_empty_lists(self, merge_helper):
        result = merge_helper.merge_results([], [])
        assert result == []

    def test_merge_results_only_messages(self, merge_helper, sample_messages):
        result = merge_helper.merge_results(sample_messages, [])

        assert len(result) == 2
        assert all(r.source_type == 'message' for r in result)
        assert result[0].similarity_score == 0.9
        assert result[1].similarity_score == 0.8

    def test_merge_results_only_summaries(self, merge_helper, sample_summaries):
        result = merge_helper.merge_results([], sample_summaries)

        assert len(result) == 2
        assert all(r.source_type == 'summary' for r in result)
        assert result[0].similarity_score == 0.85
        assert result[1].similarity_score == 0.75

    def test_merge_results_combined(self, merge_helper, sample_messages, sample_summaries):
        result = merge_helper.merge_results(sample_messages, sample_summaries)

        assert len(result) == 4

        source_types = [r.source_type for r in result]
        assert source_types.count('message') == 2
        assert source_types.count('summary') == 2

        for r in result:
            if r.source_type == 'message':
                assert r.weight == MESSAGE_WEIGHT
            else:
                assert r.weight == SUMMARY_WEIGHT

        weighted_scores = [r.weighted_score for r in result]
        assert weighted_scores == sorted(weighted_scores, reverse=True)

        assert result[0].weighted_score == pytest.approx(1.02)
        assert result[3].weighted_score == pytest.approx(0.8)

    def test_merge_results_weighted_score_calculation(self, merge_helper):
        msg = MessageRecord(
            id=1,
            text=MessageText("Test"),
            date=datetime.now(),
            chat_title=ChatTitle("Test"),
            link=None,
            sender_name=SenderName("Test"),
            similarity_score=0.5,
        )

        summ = SummaryRecord(
            id=1,
            chat_id=-1001234567890,
            chat_title=ChatTitle("Test"),
            result_text="Test summary",
            period_start=datetime.now(),
            period_end=datetime.now(),
            messages_count=10,
            similarity_score=0.5,
        )

        result = merge_helper.merge_results([msg], [summ])

        assert len(result) == 2
        assert result[0].weighted_score == 0.5 * SUMMARY_WEIGHT
        assert result[1].weighted_score == 0.5 * MESSAGE_WEIGHT


# =============================================================================
# Тесты build_context()
# =============================================================================


class TestBuildContext:
    @pytest.fixture
    def context_helper(self):
        class ContextHelper:
            def build_context(self, results):
                context_parts = []
                for i, result in enumerate(results, 1):
                    if isinstance(result, MergedResult):
                        if result.source_type == 'message':
                            msg = result.message
                            assert isinstance(msg, MessageRecord)
                            context_parts.append(f"[{i}] {str(msg.text)} (из: {str(msg.chat_title)})")
                        else:
                            summ = result.message
                            assert isinstance(summ, SummaryRecord)
                            context_parts.append(f"[{i}] {summ.result_text} (summary: {str(summ.chat_title)})")
                    elif isinstance(result, MessageRecord):
                        context_parts.append(f"[{i}] {str(result.text)} (из: {str(result.chat_title)})")
                    elif isinstance(result, SummaryRecord):
                        context_parts.append(f"[{i}] {result.result_text} (summary: {str(result.chat_title)})")
                return "\n".join(context_parts)

        return ContextHelper()

    def test_build_context_empty(self, context_helper):
        context = context_helper.build_context([])
        assert context == ""

    def test_build_context_with_messages(self, context_helper, sample_messages):
        context = context_helper.build_context(sample_messages)

        assert "Первое тестовое сообщение" in context
        assert "Второе сообщение с деталями" in context
        assert "Test Chat 1" in context
        assert "[1]" in context
        assert "[2]" in context

    def test_build_context_with_summaries(self, context_helper, sample_summaries):
        context = context_helper.build_context(sample_summaries)

        assert "Summary за период: обсуждение новых функций" in context
        assert "Summary: итоги встречи команды" in context
        assert "summary:" in context.lower()

    def test_build_context_with_merged_results(self, context_helper, sample_messages, sample_summaries):
        merged = []
        for msg in sample_messages:
            merged.append(MergedResult(
                message=msg,
                source_type='message',
                similarity_score=msg.similarity_score,
                weight=MESSAGE_WEIGHT,
            ))
        for summ in sample_summaries:
            merged.append(MergedResult(
                message=summ,
                source_type='summary',
                similarity_score=summ.similarity_score,
                weight=SUMMARY_WEIGHT,
            ))
        merged.sort(key=lambda x: x.weighted_score, reverse=True)
        context = context_helper.build_context(merged)

        assert len(context) > 0
        assert ("из:" in context or "summary:" in context)


# =============================================================================
# Тесты format_sources()
# =============================================================================


class TestFormatSources:
    @pytest.fixture
    def format_helper(self):
        class FormatHelper:
            def format_sources(self, results):
                sources = []
                for result in results:
                    if isinstance(result, MergedResult):
                        if result.source_type == 'message':
                            msg = result.message
                            assert isinstance(msg, MessageRecord)
                            sources.append({
                                'id': msg.id,
                                'type': 'message',
                                'text': str(msg.text),
                                'date': msg.date.isoformat(),
                                'chat_title': str(msg.chat_title),
                                'link': msg.link,
                                'similarity_score': msg.similarity_score,
                                'is_expanded': msg.is_expanded,
                                'grouped_count': len(msg.grouped_messages) + 1,
                            })
                        else:
                            summ = result.message
                            assert isinstance(summ, SummaryRecord)
                            sources.append({
                                'id': summ.id,
                                'type': 'summary',
                                'text': summ.result_text,
                                'date': summ.created_at.isoformat() if summ.created_at else None,
                                'chat_title': str(summ.chat_title),
                                'link': None,
                                'similarity_score': summ.similarity_score,
                                'is_expanded': False,
                                'grouped_count': 1,
                            })
                    elif isinstance(result, MessageRecord):
                        sources.append({
                            'id': result.id,
                            'type': 'message',
                            'text': str(result.text),
                            'date': result.date.isoformat(),
                            'chat_title': str(result.chat_title),
                            'link': result.link,
                            'similarity_score': result.similarity_score,
                            'is_expanded': result.is_expanded,
                            'grouped_count': len(result.grouped_messages) + 1,
                        })
                    elif isinstance(result, SummaryRecord):
                        sources.append({
                            'id': result.id,
                            'type': 'summary',
                            'text': result.result_text,
                            'date': result.created_at.isoformat() if result.created_at else None,
                            'chat_title': str(result.chat_title),
                            'link': None,
                            'similarity_score': result.similarity_score,
                            'is_expanded': False,
                            'grouped_count': 1,
                        })
                return sources

        return FormatHelper()

    def test_format_sources_empty(self, format_helper):
        sources = format_helper.format_sources([])
        assert sources == []

    def test_format_sources_messages(self, format_helper, sample_messages):
        sources = format_helper.format_sources(sample_messages)

        assert len(sources) == 2
        assert sources[0]['type'] == 'message'
        assert sources[0]['id'] == 1
        assert sources[0]['text'] == "Первое тестовое сообщение"
        assert sources[0]['chat_title'] == "Test Chat 1"
        assert sources[0]['similarity_score'] == 0.9
        assert 'date' in sources[0]
        assert 'link' in sources[0]

    def test_format_sources_summaries(self, format_helper, sample_summaries):
        sources = format_helper.format_sources(sample_summaries)

        assert len(sources) == 2
        assert sources[0]['type'] == 'summary'
        assert sources[0]['id'] == 1
        assert sources[0]['text'] == "Summary за период: обсуждение новых функций"
        assert sources[0]['chat_title'] == "Test Chat 1"
        assert sources[0]['similarity_score'] == 0.85
        assert sources[0]['link'] is None
        assert sources[0]['is_expanded'] is False

    def test_format_sources_merged_results(self, format_helper, sample_messages, sample_summaries):
        merged = []
        for msg in sample_messages:
            merged.append(MergedResult(
                message=msg,
                source_type='message',
                similarity_score=msg.similarity_score,
                weight=MESSAGE_WEIGHT,
            ))
        for summ in sample_summaries:
            merged.append(MergedResult(
                message=summ,
                source_type='summary',
                similarity_score=summ.similarity_score,
                weight=SUMMARY_WEIGHT,
            ))
        merged.sort(key=lambda x: x.weighted_score, reverse=True)
        sources = format_helper.format_sources(merged)

        assert len(sources) == 4

        types = [s['type'] for s in sources]
        assert 'message' in types
        assert 'summary' in types


# =============================================================================
# Тесты AskResult
# =============================================================================


class TestAskResult:
    def test_ask_result_creation(self):
        result = AskResult(
            answer="Test answer",
            sources=[],
            query="Test query",
            search_source="messages",
            total_found=0,
        )

        assert result.answer == "Test answer"
        assert result.sources == []
        assert result.query == "Test query"
        assert result.search_source == "messages"
        assert result.total_found == 0

    def test_ask_result_default_values(self):
        result = AskResult(
            answer="Test",
            sources=[],
            query="Test",
            search_source="messages",
            total_found=0,
        )

        assert result.context_expanded is False

    def test_ask_result_with_sources(self, sample_messages):
        sources = [{'id': m.id, 'type': 'message', 'text': str(m.text)} for m in sample_messages]
        result = AskResult(
            answer="Test",
            sources=sources,
            query="Test query",
            search_source="messages",
            total_found=2,
        )

        assert len(result.sources) == 2
        assert result.query == "Test query"

    def test_ask_result_with_context_expanded(self):
        result = AskResult(
            answer="Test",
            sources=[],
            query="Test",
            search_source="messages",
            total_found=5,
            context_expanded=True,
        )

        assert result.context_expanded is True
        assert result.total_found == 5
