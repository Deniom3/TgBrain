"""
Unit тесты для валидации моделей данных.
"""

import pytest
import re
from datetime import datetime

from src.models.data_models import (
    MessageRecord,
    SummaryRecord,
    MergedResult,
    MessageGroup,
)
from src.models.sql import (
    SQL_GET_MESSAGE_NEIGHBORS,
    SQL_GET_CONSECUTIVE_MESSAGES,
    SQL_GET_MESSAGES_IN_TIME_WINDOW,
    SQL_CHECK_CHAT_EXISTS,
)
from src.domain.value_objects import MessageText, ChatTitle, SenderName

pytestmark = pytest.mark.integration


class TestMessageRecordValidation:
    """Тесты валидации MessageRecord."""

    def test_valid_similarity_score_zero(self):
        """Допустимое значение: 0.0."""
        msg = MessageRecord(
            id=1,
            text=MessageText("Test"),
            date=datetime.now(),
            chat_title=ChatTitle("Test Chat"),
            link=None,
            sender_name=SenderName("User"),
            similarity_score=0.0
        )
        assert msg.similarity_score == 0.0

    def test_valid_similarity_score_one(self):
        """Допустимое значение: 1.0."""
        msg = MessageRecord(
            id=1,
            text=MessageText("Test"),
            date=datetime.now(),
            chat_title=ChatTitle("Test Chat"),
            link=None,
            sender_name=SenderName("User"),
            similarity_score=1.0
        )
        assert msg.similarity_score == 1.0

    def test_valid_similarity_score_middle(self):
        """Допустимое значение: 0.5."""
        msg = MessageRecord(
            id=1,
            text=MessageText("Test"),
            date=datetime.now(),
            chat_title=ChatTitle("Test Chat"),
            link=None,
            sender_name=SenderName("User"),
            similarity_score=0.5
        )
        assert msg.similarity_score == 0.5

    def test_invalid_similarity_score_negative(self):
        """Недопустимое значение: отрицательное."""
        with pytest.raises(ValueError) as exc_info:
            MessageRecord(
                id=1,
                text=MessageText("Test"),
                date=datetime.now(),
                chat_title=ChatTitle("Test Chat"),
                link=None,
                sender_name=SenderName("User"),
                similarity_score=-0.1
            )
        assert "similarity_score должен быть в диапазоне 0.0-1.0" in str(exc_info.value)

    def test_invalid_similarity_score_above_one(self):
        """Недопустимое значение: больше 1.0."""
        with pytest.raises(ValueError) as exc_info:
            MessageRecord(
                id=1,
                text=MessageText("Test"),
                date=datetime.now(),
                chat_title=ChatTitle("Test Chat"),
                link=None,
                sender_name=SenderName("User"),
                similarity_score=1.5
            )
        assert "similarity_score должен быть в диапазоне 0.0-1.0" in str(exc_info.value)


class TestSummaryRecordValidation:
    """Тесты валидации SummaryRecord."""

    def test_valid_similarity_score(self):
        """Допустимое значение similarity_score."""
        summary = SummaryRecord(
            id=1,
            chat_id=123,
            chat_title=ChatTitle("Test Chat"),
            result_text="Summary text",
            period_start=datetime.now(),
            period_end=datetime.now(),
            messages_count=10,
            similarity_score=0.8
        )
        assert summary.similarity_score == 0.8

    def test_invalid_similarity_score_negative(self):
        """Недопустимое значение: отрицательное."""
        with pytest.raises(ValueError) as exc_info:
            SummaryRecord(
                id=1,
                chat_id=123,
                chat_title=ChatTitle("Test Chat"),
                result_text="Summary text",
                period_start=datetime.now(),
                period_end=datetime.now(),
                messages_count=10,
                similarity_score=-0.1
            )
        assert "similarity_score должен быть в диапазоне 0.0-1.0" in str(exc_info.value)

    def test_invalid_similarity_score_above_one(self):
        """Недопустимое значение: больше 1.0."""
        with pytest.raises(ValueError) as exc_info:
            SummaryRecord(
                id=1,
                chat_id=123,
                chat_title=ChatTitle("Test Chat"),
                result_text="Summary text",
                period_start=datetime.now(),
                period_end=datetime.now(),
                messages_count=10,
                similarity_score=1.5
            )
        assert "similarity_score должен быть в диапазоне 0.0-1.0" in str(exc_info.value)


class TestMergedResultValidation:
    """Тесты валидации MergedResult."""

    def test_valid_similarity_score(self):
        """Допустимое значение similarity_score."""
        msg = MessageRecord(
            id=1,
            text=MessageText("Test"),
            date=datetime.now(),
            chat_title=ChatTitle("Test Chat"),
            link=None,
            sender_name=SenderName("User"),
            similarity_score=0.5
        )
        merged = MergedResult(
            message=msg,
            source_type='message',
            similarity_score=0.7
        )
        assert merged.similarity_score == 0.7

    def test_invalid_similarity_score_negative(self):
        """Недопустимое значение: отрицательное."""
        msg = MessageRecord(
            id=1,
            text=MessageText("Test"),
            date=datetime.now(),
            chat_title=ChatTitle("Test Chat"),
            link=None,
            sender_name=SenderName("User"),
            similarity_score=0.5
        )
        with pytest.raises(ValueError) as exc_info:
            MergedResult(
                message=msg,
                source_type='message',
                similarity_score=-0.1
            )
        assert "similarity_score должен быть в диапазоне 0.0-1.0" in str(exc_info.value)

    def test_invalid_similarity_score_above_one(self):
        """Недопустимое значение: больше 1.0."""
        msg = MessageRecord(
            id=1,
            text=MessageText("Test"),
            date=datetime.now(),
            chat_title=ChatTitle("Test Chat"),
            link=None,
            sender_name=SenderName("User"),
            similarity_score=0.5
        )
        with pytest.raises(ValueError) as exc_info:
            MergedResult(
                message=msg,
                source_type='message',
                similarity_score=1.5
            )
        assert "similarity_score должен быть в диапазоне 0.0-1.0" in str(exc_info.value)


class TestMessageGroupValidation:
    """Тесты валидации MessageGroup."""

    def test_valid_similarity_score(self):
        """Допустимое значение similarity_score."""
        msg = MessageRecord(
            id=1,
            text=MessageText("Test"),
            date=datetime.now(),
            chat_title=ChatTitle("Test Chat"),
            link=None,
            sender_name=SenderName("User"),
            similarity_score=0.5
        )
        group = MessageGroup(
            sender_id=123,
            sender_name="User",
            chat_id=456,
            chat_title="Test Chat",
            messages=[msg],
            start_date=datetime.now(),
            end_date=datetime.now(),
            merged_text="Merged text",
            similarity_score=0.9
        )
        assert group.similarity_score == 0.9

    def test_invalid_similarity_score_negative(self):
        """Недопустимое значение: отрицательное."""
        msg = MessageRecord(
            id=1,
            text=MessageText("Test"),
            date=datetime.now(),
            chat_title=ChatTitle("Test Chat"),
            link=None,
            sender_name=SenderName("User"),
            similarity_score=0.5
        )
        with pytest.raises(ValueError) as exc_info:
            MessageGroup(
                sender_id=123,
                sender_name="User",
                chat_id=456,
                chat_title="Test Chat",
                messages=[msg],
                start_date=datetime.now(),
                end_date=datetime.now(),
                merged_text="Merged text",
                similarity_score=-0.1
            )
        assert "similarity_score должен быть в диапазоне 0.0-1.0" in str(exc_info.value)

    def test_invalid_similarity_score_above_one(self):
        """Недопустимое значение: больше 1.0."""
        msg = MessageRecord(
            id=1,
            text=MessageText("Test"),
            date=datetime.now(),
            chat_title=ChatTitle("Test Chat"),
            link=None,
            sender_name=SenderName("User"),
            similarity_score=0.5
        )
        with pytest.raises(ValueError) as exc_info:
            MessageGroup(
                sender_id=123,
                sender_name="User",
                chat_id=456,
                chat_title="Test Chat",
                messages=[msg],
                start_date=datetime.now(),
                end_date=datetime.now(),
                merged_text="Merged text",
                similarity_score=1.5
            )
        assert "similarity_score должен быть в диапазоне 0.0-1.0" in str(exc_info.value)


class TestSQLParameterization:
    """Тесты на параметризацию SQL запросов."""

    def test_get_message_neighbors_parameterized(self):
        """SQL_GET_MESSAGE_NEIGHBORS использует параметризацию."""
        assert '$1' in SQL_GET_MESSAGE_NEIGHBORS
        assert '$2' in SQL_GET_MESSAGE_NEIGHBORS
        assert '$3' in SQL_GET_MESSAGE_NEIGHBORS
        assert '$4' in SQL_GET_MESSAGE_NEIGHBORS
        assert '$5' in SQL_GET_MESSAGE_NEIGHBORS
        assert '$6' in SQL_GET_MESSAGE_NEIGHBORS
        assert '$7' in SQL_GET_MESSAGE_NEIGHBORS

        assert '{' not in SQL_GET_MESSAGE_NEIGHBORS
        assert '}' not in SQL_GET_MESSAGE_NEIGHBORS

        assert 'f"' not in SQL_GET_MESSAGE_NEIGHBORS
        assert "f'" not in SQL_GET_MESSAGE_NEIGHBORS

    def test_get_consecutive_messages_parameterized(self):
        """SQL_GET_CONSECUTIVE_MESSAGES использует параметризацию."""
        assert '$1' in SQL_GET_CONSECUTIVE_MESSAGES
        assert '$2' in SQL_GET_CONSECUTIVE_MESSAGES
        assert '$3' in SQL_GET_CONSECUTIVE_MESSAGES
        assert '$4' in SQL_GET_CONSECUTIVE_MESSAGES
        assert '$5' in SQL_GET_CONSECUTIVE_MESSAGES
        assert '{' not in SQL_GET_CONSECUTIVE_MESSAGES

    def test_get_messages_in_time_window_parameterized(self):
        """SQL_GET_MESSAGES_IN_TIME_WINDOW использует параметризацию."""
        assert '$1' in SQL_GET_MESSAGES_IN_TIME_WINDOW
        assert '$2' in SQL_GET_MESSAGES_IN_TIME_WINDOW
        assert '$3' in SQL_GET_MESSAGES_IN_TIME_WINDOW
        assert '$4' in SQL_GET_MESSAGES_IN_TIME_WINDOW
        assert '{' not in SQL_GET_MESSAGES_IN_TIME_WINDOW

    def test_check_chat_exists_parameterized(self):
        """SQL_CHECK_CHAT_EXISTS использует параметризацию."""
        assert '$1' in SQL_CHECK_CHAT_EXISTS
        assert '{' not in SQL_CHECK_CHAT_EXISTS

    def test_no_sql_injection_patterns(self):
        """Проверка отсутствия паттернов SQL Injection."""
        queries = [
            SQL_GET_MESSAGE_NEIGHBORS,
            SQL_GET_CONSECUTIVE_MESSAGES,
            SQL_GET_MESSAGES_IN_TIME_WINDOW,
            SQL_CHECK_CHAT_EXISTS,
        ]

        for query in queries:
            assert not re.search(r'f["\'].*\{.*\}.*["\']', query)
            assert '.format(' not in query
            assert '%s' not in query
            assert '%d' not in query


class TestEmbeddingParameterization:
    """Тесты на параметризованную вставку embedding через asyncpg."""

    @pytest.mark.integration
    async def test_embedding_insert_parameterized(self, real_db_pool):
        """Тест на параметризованную вставку embedding в messages."""
        embedding = [0.1] * 768
        message_id = 999999
        chat_id = -1001234567890
        test_date = datetime(2026, 3, 9, 12, 0, 0)

        try:
            # INSERT с параметризованным embedding
            await real_db_pool.execute("""
                INSERT INTO messages (
                    id, chat_id, sender_id, sender_name, message_text,
                    message_date, embedding, is_processed
                ) VALUES ($1, $2, $3, $4, $5, $6, $7::VECTOR(768), $8)
                ON CONFLICT (id) DO UPDATE SET
                    embedding = EXCLUDED.embedding,
                    is_processed = EXCLUDED.is_processed
            """, message_id, chat_id, 0, "Test User",
                "Test message for embedding parameterization", test_date, embedding, True)

            # Извлечение и проверка
            row = await real_db_pool.fetchrow("""
                SELECT embedding FROM messages WHERE id = $1
            """, message_id)

            # Проверка что вектор сохранён корректно
            assert row["embedding"] is not None
            assert len(row["embedding"]) == 768
            assert row["embedding"][0] == pytest.approx(0.1, abs=0.001)

        finally:
            # Очистка
            await real_db_pool.execute(
                "DELETE FROM messages WHERE id = $1", message_id
            )

    @pytest.mark.integration
    async def test_summary_embedding_update_parameterized(self, real_db_pool):
        """Тест на параметризованное обновление embedding в chat_summaries."""
        embedding = [0.2] * 768
        summary_id = 888888
        chat_id = -1001234567890
        period_start = datetime(2026, 3, 1, 0, 0, 0)
        period_end = datetime(2026, 3, 2, 0, 0, 0)

        try:
            # Сначала создадим тестовую запись
            await real_db_pool.execute("""
                INSERT INTO chat_summaries (
                    id, chat_id, period_start, period_end, result_text, messages_count
                ) VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (id) DO UPDATE SET
                    result_text = EXCLUDED.result_text
            """, summary_id, chat_id, period_start, period_end, "Test summary", 10)

            # UPDATE с параметризованным embedding
            await real_db_pool.execute("""
                UPDATE chat_summaries
                SET embedding = $1::VECTOR(768)
                WHERE id = $2
            """, embedding, summary_id)

            # Извлечение и проверка
            row = await real_db_pool.fetchrow("""
                SELECT embedding FROM chat_summaries WHERE id = $1
            """, summary_id)

            # Проверка что вектор сохранён корректно
            assert row["embedding"] is not None
            assert len(row["embedding"]) == 768
            assert row["embedding"][0] == pytest.approx(0.2, abs=0.001)

        finally:
            # Очистка
            await real_db_pool.execute(
                "DELETE FROM chat_summaries WHERE id = $1", summary_id
            )
