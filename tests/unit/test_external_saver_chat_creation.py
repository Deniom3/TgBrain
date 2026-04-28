"""
Тесты авто-создания записи в chat_settings при приёме внешних сообщений.

Сценарии:
- Сообщение для несуществующего чата создаёт запись в chat_settings
- Сообщение для существующего чата с is_monitored=TRUE обрабатывается
- Сообщение для существующего чата с is_monitored=FALSE отклоняется (EXT-002)
- Повторные сообщения не создают дубликатов в chat_settings
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from typing import Callable

from src.ingestion.external_saver import ExternalMessageSaver


class MockConnection:
    """Мок-соединение для отслеживания SQL-вызовов."""

    def __init__(self) -> None:
        self.fetchrow_calls: list[tuple[str, tuple]] = []
        self.execute_calls: list[tuple[str, tuple]] = []
        self._fetchrow_handler: Callable[[str, tuple], dict | None] | None = None

    def set_fetchrow_handler(self, handler: Callable[[str, tuple], dict | None]) -> None:
        self._fetchrow_handler = handler

    async def fetchrow(self, query: str, *args: object) -> dict | None:
        self.fetchrow_calls.append((query, args))
        if self._fetchrow_handler is not None:
            return self._fetchrow_handler(query, args)
        return None

    async def execute(self, query: str, *args: object) -> None:
        self.execute_calls.append((query, args))


class TestExternalSaverChatCreation:
    """Тесты авто-создания chat_settings через _ensure_chat_monitored."""

    def _create_saver_with_connection(self, conn: MockConnection) -> ExternalMessageSaver:
        mock_pool = MagicMock()

        class MockAcquireCtx:
            async def __aenter__(self) -> MockConnection:
                return conn

            async def __aexit__(self, *args: object) -> None:
                return None

        mock_pool.acquire = MagicMock(return_value=MockAcquireCtx())

        mock_saver = MagicMock()
        mock_embeddings = MagicMock()
        mock_embeddings.get_embedding = AsyncMock(return_value=[0.1] * 768)
        mock_embeddings.get_model_name = MagicMock(return_value="test-model")
        mock_saver.embeddings = mock_embeddings

        return ExternalMessageSaver(mock_pool, mock_saver)

    @pytest.mark.asyncio
    async def test_NewChat_CreatesSettingsAndSavesMessage(self) -> None:
        """Сообщение для несуществующего чата создаёт запись в chat_settings."""
        conn = MockConnection()
        message_id_counter = [0]

        def fetchrow_handler(query: str, args: tuple) -> dict | None:
            if "is_monitored" in query:
                return None
            if "INSERT INTO messages" in query or "ON CONFLICT" in query and "messages" in query:
                message_id_counter[0] += 1
                return {"id": message_id_counter[0]}
            return None

        conn.set_fetchrow_handler(fetchrow_handler)

        saver = self._create_saver_with_connection(conn)

        result = await saver.save_external_message(
            chat_id=-100999888777,
            text="Достаточно длинное сообщение для прохождения фильтрации",
            date=datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

        assert result.success is True
        assert result.status.status == "processed"
        assert result.chat_id == -100999888777

        chat_settings_calls = [
            call for call in conn.execute_calls
            if "chat_settings" in call[0]
        ]
        assert len(chat_settings_calls) >= 1

        chat_settings_upsert_args = chat_settings_calls[0][1]
        assert chat_settings_upsert_args[0] == -100999888777
        assert chat_settings_upsert_args[1] == "External Chat -100999888777"
        assert chat_settings_upsert_args[2] == "external"

    @pytest.mark.asyncio
    async def test_ExistingChat_MonitoredTrue_ProcessesMessage(self) -> None:
        """Сообщение для существующего чата с is_monitored=TRUE обрабатывается."""
        conn = MockConnection()
        message_id_counter = [0]

        def fetchrow_handler(query: str, args: tuple) -> dict | None:
            if "is_monitored" in query:
                return {
                    "is_monitored": True,
                    "filter_bots": True,
                    "filter_actions": True,
                    "filter_min_length": 15,
                    "filter_ads": True,
                }
            if "INSERT INTO messages" in query or "ON CONFLICT" in query and "messages" in query:
                message_id_counter[0] += 1
                return {"id": message_id_counter[0]}
            return None

        conn.set_fetchrow_handler(fetchrow_handler)

        saver = self._create_saver_with_connection(conn)

        result = await saver.save_external_message(
            chat_id=-100111222333,
            text="Достаточно длинное сообщение для прохождения фильтрации",
            date=datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

        assert result.success is True
        assert result.status.status == "processed"

    @pytest.mark.asyncio
    async def test_ExistingChat_MonitoredFalse_RejectsMessage(self) -> None:
        """Сообщение для существующего чата с is_monitored=FALSE отклоняется (EXT-002)."""
        conn = MockConnection()
        conn.set_fetchrow_handler(
            lambda query, args: {
                "is_monitored": False,
                "filter_bots": True,
                "filter_actions": True,
                "filter_min_length": 15,
                "filter_ads": True,
            }
            if "is_monitored" in query
            else None
        )

        saver = self._create_saver_with_connection(conn)

        result = await saver.save_external_message(
            chat_id=-100444555666,
            text="Сообщение для немониторируемого чата",
            date=datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

        assert result.success is False
        assert result.status.status == "error"
        assert result.reason == "Chat not monitored"

    @pytest.mark.asyncio
    async def test_RepeatedMessages_NoDuplicateChatSettings(self) -> None:
        """Повторные сообщения для одного чата: _ensure_chat_monitored не создаёт дубликаты."""
        conn = MockConnection()
        message_id_counter = [0]
        fetchrow_call_count = [0]

        def fetchrow_handler(query: str, args: tuple) -> dict | None:
            if "is_monitored" in query:
                fetchrow_call_count[0] += 1
                if fetchrow_call_count[0] == 1:
                    return None
                return {
                    "is_monitored": True,
                    "filter_bots": True,
                    "filter_actions": True,
                    "filter_min_length": 15,
                    "filter_ads": True,
                }
            if "INSERT INTO messages" in query or "ON CONFLICT" in query and "messages" in query:
                message_id_counter[0] += 1
                return {"id": message_id_counter[0]}
            return None

        conn.set_fetchrow_handler(fetchrow_handler)

        saver = self._create_saver_with_connection(conn)

        result_first = await saver.save_external_message(
            chat_id=-100777888999,
            text="Первое сообщение для нового чата с достаточной длиной",
            date=datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

        assert result_first.success is True
        assert result_first.status.status == "processed"

        result_second = await saver.save_external_message(
            chat_id=-100777888999,
            text="Второе сообщение для того же чата с достаточной длиной",
            date=datetime(2026, 4, 1, 12, 1, 0, tzinfo=timezone.utc),
        )

        assert result_second.success is True
        assert result_second.status.status == "processed"

        is_monitored_checks = [
            call for call in conn.fetchrow_calls
            if "is_monitored" in call[0]
        ]
        assert len(is_monitored_checks) == 2

        chat_settings_calls = [
            call for call in conn.execute_calls
            if "chat_settings" in call[0]
        ]
        assert len(chat_settings_calls) == 1
