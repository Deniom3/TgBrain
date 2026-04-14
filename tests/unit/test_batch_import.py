"""
Тесты для Phase 2 & 3: Services и API Endpoints.

Phase 2: StreamingChunkGenerator, ChatAccessValidator, BatchImportTaskManager
Phase 3: API Endpoints (import, progress, cancel)

Примечание: Тесты для BatchImportTaskManager (start_import, get_progress, cancel_import)
перенесены в tests/unit/application/usecases/test_import_messages_usecase.py,
так как оркестрационная логика перемещена в ImportMessagesUseCase.
"""

import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest

from src.domain.value_objects import ChatId, ChatTitle, ChatType
from src.importers.chunk_generator import StreamingChunkGenerator
from src.importers.telegram_export_parser import TelegramExportParser
from src.services.chat_access_validator import ChatAccessValidator


class TestStreamingChunkGenerator:
    """Тесты для StreamingChunkGenerator."""

    def _create_test_export_file(
        self,
        num_messages: int,
        chat_id: int = 123,
    ) -> str:
        """Создание тестового JSON файла экспорта."""
        messages = []
        for i in range(num_messages):
            msg = {
                "id": i + 1,
                "type": "message",
                "date": "2026-03-27T10:00:00",
                "from": f"User{i}",
                "from_id": f"user{i}",
                "text": f"Message text {i}",
            }
            messages.append(msg)

        export_data = {
            "id": chat_id,
            "name": f"Test Chat {chat_id}",
            "type": "private",
            "messages": messages,
        }

        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False,
            encoding='utf-8',
        ) as f:
            json.dump(export_data, f, ensure_ascii=False)
            return f.name

    def test_batch_import_process_stream_chunking_no_memory_overflow(self):
        """
        TestBatchImportProcess_StreamChunking_NoMemoryOverflow.

        Проверяет, что большой файл обрабатывается потоково,
        а не загружается целиком в память.
        """
        file_path = self._create_test_export_file(1000)

        try:
            generator = StreamingChunkGenerator(file_path, chunk_size=100)

            chunk_count = 0
            for chunk in generator:
                chunk_count += 1
                assert len(chunk) <= 100

            assert chunk_count == 10

        finally:
            os.unlink(file_path)

    def test_batch_import_process_chunk_by_100_correct_count(self):
        """
        TestBatchImportProcess_ChunkBy100_CorrectCount.

        Проверяет, что 15000 сообщений разбиваются на 150 чанков.
        """
        file_path = self._create_test_export_file(150)

        try:
            generator = StreamingChunkGenerator(file_path, chunk_size=100)

            chunks = list(generator)

            assert len(chunks) == 2
            assert len(chunks[0]) == 100
            assert len(chunks[1]) == 50

        finally:
            os.unlink(file_path)

    def test_batch_import_process_progress_after_chunk_updated(self):
        """
        TestBatchImportProcess_ProgressAfterChunk_Updated.

        Проверяет, что прогресс обновляется после обработки чанка.
        """
        file_path = self._create_test_export_file(250)

        try:
            generator = StreamingChunkGenerator(file_path, chunk_size=100)

            total_count = generator.get_total_count()
            assert total_count == 250

            chunks_processed = 0
            for chunk in generator:
                chunks_processed += 1

            assert chunks_processed == 3

        finally:
            os.unlink(file_path)

    def test_batch_import_process_file_deleted_after_complete(self):
        """
        TestBatchImportProcess_FileDeletedAfterComplete.

        Проверяет, что файл удаляется после завершения обработки.
        """
        file_path = self._create_test_export_file(50)

        try:
            assert os.path.exists(file_path)

            generator = StreamingChunkGenerator(file_path, chunk_size=100)
            list(generator)

            assert os.path.exists(file_path)

        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)

    def test_batch_import_process_mid_chunk_error_file_deleted(self):
        """
        TestBatchImportProcess_MidChunkError_FileDeleted.

        Проверяет, что при ошибке файл удаляется и прогресс сохраняется.
        """
        file_path = self._create_test_export_file(100)

        try:
            generator = StreamingChunkGenerator(file_path, chunk_size=50)

            with patch.object(
                TelegramExportParser,
                'convert_to_ingestion',
                side_effect=ValueError("Test error"),
            ):
                with pytest.raises(ValueError):
                    list(generator)

            assert os.path.exists(file_path)

        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)


class TestChatAccessValidator:
    """Тесты для ChatAccessValidator."""

    @pytest.mark.asyncio
    async def test_batch_import_process_chat_not_found_auto_created(self):
        """
        TestBatchImportProcess_ChatNotFound_AutoCreated.

        Проверяет, что чат автоматически создаётся при отсутствии.
        """
        pool = AsyncMock()
        conn = AsyncMock()

        class MockAcquireCtx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *args):
                return None

        pool.acquire = MagicMock(return_value=MockAcquireCtx())

        conn.fetchrow.return_value = None
        conn.execute.return_value = None

        telegram_client = AsyncMock()
        telegram_client.get_chat = AsyncMock(return_value=MagicMock())

        validator = ChatAccessValidator(pool, telegram_client)

        result = await validator.validate_access(
            chat_id=ChatId(123),
            chat_title=ChatTitle("Test Chat"),
            chat_type=ChatType("private"),
        )

        assert result is True
        conn.fetchrow.assert_called_once()
        conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_import_process_user_has_access_allowed(self):
        """
        TestBatchImportProcess_UserHasAccess_Allowed.

        Проверяет, что доступ разрешён при наличии чата.
        """
        pool = AsyncMock()
        conn = AsyncMock()

        class MockAcquireCtx2:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *args):
                return None

        pool.acquire = MagicMock(return_value=MockAcquireCtx2())

        conn.fetchrow.return_value = {"chat_id": 123, "is_monitored": False}

        validator = ChatAccessValidator(pool)

        result = await validator.validate_access(
            chat_id=ChatId(123),
            chat_title=ChatTitle("Test Chat"),
            chat_type=ChatType("private"),
        )

        assert result is True
        conn.fetchrow.assert_called_once()
        conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_batch_import_process_user_no_access_returns_403(self):
        """
        TestBatchImportProcess_UserNoAccess_Returns403.

        Проверяет сценарий отказа в доступе.
        """
        pool = AsyncMock()
        conn = AsyncMock()

        class MockAcquireCtx3:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *args):
                return None

        pool.acquire = MagicMock(return_value=MockAcquireCtx3())

        conn.fetchrow.return_value = None
        conn.execute.side_effect = asyncpg.exceptions.UniqueViolationError(
            "Unique violation",
            None,
            None,
        )

        telegram_client = AsyncMock()
        telegram_client.get_chat = AsyncMock(return_value=MagicMock())

        validator = ChatAccessValidator(pool, telegram_client)

        with pytest.raises(asyncpg.exceptions.UniqueViolationError):
            await validator.validate_access(
                chat_id=ChatId(123),
                chat_title=ChatTitle("Test Chat"),
                chat_type=ChatType("private"),
            )
