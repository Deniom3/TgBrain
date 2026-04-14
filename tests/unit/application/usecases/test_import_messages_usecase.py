"""Тесты для ImportMessagesUseCase.

Покрывает 12 сценариев:
- start_import из файла (успех, файл слишком большой, слишком много сообщений, нет доступа)
- start_import из JSON (успех, слишком много сообщений, невалидный JSON, нет входных данных)
- cancel_import (отмена, задача не найдена)
- get_progress (успех, задача не найдена)
"""

import asyncio
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from src.application.exceptions import (
    AccessDeniedError,
    FileTooLargeError,
    InvalidInputError,
    TaskNotFoundError,
    TooManyMessagesError,
)
from src.application.usecases.import_messages import (
    ImportMessagesUseCase,
    ImportRequest,
    ProgressData,
)
from src.application.usecases.protocols import (
    ChatAccessInfo,
    ChatAccessValidationPort,
    ChunkGeneratorPort,
    ExternalMessageData,
    FileStoragePort,
    FileValidationPort,
    MessageIngestionPort,
    SaveResult,
    ValidationResult,
)


@dataclass
class MockFileStoragePort(FileStoragePort):
    """Stub для FileStoragePort."""

    temp_path: str = ""
    raise_on_save: bool = False
    _created_files: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.temp_path:
            tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
            tmp.close()
            object.__setattr__(self, "temp_path", tmp.name)

    async def save_to_temp(self, content: bytes, max_size: int) -> str:
        if self.raise_on_save:
            raise ValueError("File too large")
        return self.temp_path

    async def save_json_to_temp(self, data: dict[str, Any], file_id: str) -> str:
        if self.raise_on_save:
            raise OSError("Disk full")
        Path(self.temp_path).write_text(json.dumps(data), encoding="utf-8")
        self._created_files.append(self.temp_path)
        return self.temp_path

    async def delete_file(self, path: str) -> None:
        pass


@dataclass
class MockFileValidationPort(FileValidationPort):
    """Stub для FileValidationPort."""

    validation_result: ValidationResult | None = None
    raise_on_validate: bool = False
    raise_type: type[Exception] = ValueError

    async def validate_content(self, file_path: str) -> ValidationResult:
        if self.raise_on_validate:
            raise self.raise_type("Validation failed")
        return self.validation_result or ValidationResult(messages_count=10)

    async def validate_json_data(self, data: dict[str, Any]) -> ValidationResult:
        if self.raise_on_validate:
            raise self.raise_type("Validation failed")
        return self.validation_result or ValidationResult(messages_count=5)


@dataclass
class MockChatAccessValidationPort(ChatAccessValidationPort):
    """Stub для ChatAccessValidationPort."""

    deny_access: bool = False

    async def validate_access(self, user_id: int, chat_info: ChatAccessInfo) -> None:
        if self.deny_access:
            raise PermissionError("Access denied")


@dataclass
class MockMessageIngestionPort(MessageIngestionPort):
    """Stub для MessageIngestionPort."""

    calls: list[ExternalMessageData] = None

    def __post_init__(self) -> None:
        if self.calls is None:
            object.__setattr__(self, "calls", [])

    async def save_external_message(self, msg: ExternalMessageData) -> SaveResult:
        self.calls.append(msg)
        return SaveResult(message_id=1, is_duplicate=False)


@dataclass
class MockChunkGeneratorPort(ChunkGeneratorPort):
    """Stub для ChunkGeneratorPort."""

    total_count: int = 10
    chunks: list[list[dict[str, Any]]] = None
    delay: float = 0.0

    def __post_init__(self) -> None:
        if self.chunks is None:
            object.__setattr__(self, "chunks", [[{"id": i, "text": f"msg {i}"} for i in range(5)]])

    async def iterate_chunks(self, file_path: str, chunk_size: int):
        for chunk in self.chunks:
            if self.delay > 0:
                await asyncio.sleep(self.delay)
            yield chunk

    async def get_total_count(self, file_path: str) -> int:
        return self.total_count


def _make_valid_validation_result() -> ValidationResult:
    return ValidationResult(
        messages_count=10,
        chat_info={"chat_id": 123, "chat_name": "Test Chat", "chat_type": "private"},
    )


class TestStartImportFromFileSuccess:
    """start_import из файла — успешный сценарий."""

    @pytest.mark.asyncio
    async def test_start_import_from_file_success(self) -> None:
        file_storage = MockFileStoragePort()
        file_validation = MockFileValidationPort(validation_result=_make_valid_validation_result())
        chat_access = MockChatAccessValidationPort()
        message_ingestion = MockMessageIngestionPort()
        chunk_generator = MockChunkGeneratorPort()

        usecase = ImportMessagesUseCase(
            file_storage=file_storage,
            file_validation=file_validation,
            chat_access=chat_access,
            message_ingestion=message_ingestion,
            chunk_generator=chunk_generator,
        )

        request = ImportRequest(
            file_content=b'{"messages": []}',
            json_data=None,
            chat_id_override=None,
            file_id="test-file-1",
        )

        result = await usecase.start_import(request)

        assert result.is_success
        import_result = result.value
        assert import_result.task_id is not None
        assert import_result.status == "processing"
        assert import_result.messages_count == 10
        assert import_result.chat_id_from_file == 123


class TestStartImportFromJsonSuccess:
    """start_import из JSON — успешный сценарий."""

    @pytest.mark.asyncio
    async def test_start_import_from_json_success(self) -> None:
        file_storage = MockFileStoragePort()
        file_validation = MockFileValidationPort(validation_result=_make_valid_validation_result())
        chat_access = MockChatAccessValidationPort()
        message_ingestion = MockMessageIngestionPort()
        chunk_generator = MockChunkGeneratorPort()

        usecase = ImportMessagesUseCase(
            file_storage=file_storage,
            file_validation=file_validation,
            chat_access=chat_access,
            message_ingestion=message_ingestion,
            chunk_generator=chunk_generator,
        )

        json_data = {"messages": [{"id": 1, "text": "hello"}]}
        request = ImportRequest(
            file_content=None,
            json_data=json_data,
            chat_id_override=456,
            file_id="test-file-2",
        )

        result = await usecase.start_import(request)

        assert result.is_success
        import_result = result.value
        assert import_result.task_id is not None
        assert import_result.status == "processing"


class TestStartImportFileTooLarge:
    """start_import из файла — файл слишком большой."""

    @pytest.mark.asyncio
    async def test_start_import_file_too_large_raises_error(self) -> None:
        file_storage = MockFileStoragePort(raise_on_save=True)
        file_validation = MockFileValidationPort()
        chat_access = MockChatAccessValidationPort()
        message_ingestion = MockMessageIngestionPort()
        chunk_generator = MockChunkGeneratorPort()

        usecase = ImportMessagesUseCase(
            file_storage=file_storage,
            file_validation=file_validation,
            chat_access=chat_access,
            message_ingestion=message_ingestion,
            chunk_generator=chunk_generator,
        )

        request = ImportRequest(
            file_content=b'{"messages": []}',
            json_data=None,
            chat_id_override=None,
            file_id="test-file-3",
        )

        result = await usecase.start_import(request)

        assert result.is_failure
        assert isinstance(result.error, FileTooLargeError)


class TestStartImportTooManyMessagesFromFile:
    """start_import из файла — слишком много сообщений."""

    @pytest.mark.asyncio
    async def test_start_import_too_many_messages_raises_error(self) -> None:
        file_storage = MockFileStoragePort()
        too_many = ValidationResult(messages_count=15000)
        file_validation = MockFileValidationPort(validation_result=too_many)
        chat_access = MockChatAccessValidationPort()
        message_ingestion = MockMessageIngestionPort()
        chunk_generator = MockChunkGeneratorPort()

        usecase = ImportMessagesUseCase(
            file_storage=file_storage,
            file_validation=file_validation,
            chat_access=chat_access,
            message_ingestion=message_ingestion,
            chunk_generator=chunk_generator,
        )

        request = ImportRequest(
            file_content=b'{"messages": []}',
            json_data=None,
            chat_id_override=None,
            file_id="test-file-4",
        )

        result = await usecase.start_import(request)

        assert result.is_failure
        assert isinstance(result.error, TooManyMessagesError)


class TestStartImportTooManyMessagesFromJson:
    """start_import из JSON — слишком много сообщений."""

    @pytest.mark.asyncio
    async def test_start_import_json_too_many_messages_raises_error(self) -> None:
        file_storage = MockFileStoragePort()
        too_many = ValidationResult(messages_count=2000)
        file_validation = MockFileValidationPort(validation_result=too_many)
        chat_access = MockChatAccessValidationPort()
        message_ingestion = MockMessageIngestionPort()
        chunk_generator = MockChunkGeneratorPort()

        usecase = ImportMessagesUseCase(
            file_storage=file_storage,
            file_validation=file_validation,
            chat_access=chat_access,
            message_ingestion=message_ingestion,
            chunk_generator=chunk_generator,
        )

        request = ImportRequest(
            file_content=None,
            json_data={"messages": []},
            chat_id_override=None,
            file_id="test-file-5",
        )

        result = await usecase.start_import(request)

        assert result.is_failure
        assert isinstance(result.error, TooManyMessagesError)


class TestStartImportAccessDenied:
    """start_import — доступ запрещён."""

    @pytest.mark.asyncio
    async def test_start_import_access_denied_raises_error(self) -> None:
        file_storage = MockFileStoragePort()
        file_validation = MockFileValidationPort(validation_result=_make_valid_validation_result())
        chat_access = MockChatAccessValidationPort(deny_access=True)
        message_ingestion = MockMessageIngestionPort()
        chunk_generator = MockChunkGeneratorPort()

        usecase = ImportMessagesUseCase(
            file_storage=file_storage,
            file_validation=file_validation,
            chat_access=chat_access,
            message_ingestion=message_ingestion,
            chunk_generator=chunk_generator,
        )

        request = ImportRequest(
            file_content=b'{"messages": []}',
            json_data=None,
            chat_id_override=None,
            file_id="test-file-6",
        )

        result = await usecase.start_import(request)

        assert result.is_failure
        assert isinstance(result.error, AccessDeniedError)


class TestStartImportInvalidJson:
    """start_import из JSON — невалидный JSON."""

    @pytest.mark.asyncio
    async def test_start_import_invalid_json_raises_error(self) -> None:
        file_storage = MockFileStoragePort()
        file_validation = MockFileValidationPort(raise_on_validate=True)
        chat_access = MockChatAccessValidationPort()
        message_ingestion = MockMessageIngestionPort()
        chunk_generator = MockChunkGeneratorPort()

        usecase = ImportMessagesUseCase(
            file_storage=file_storage,
            file_validation=file_validation,
            chat_access=chat_access,
            message_ingestion=message_ingestion,
            chunk_generator=chunk_generator,
        )

        request = ImportRequest(
            file_content=None,
            json_data={"invalid": True},
            chat_id_override=None,
            file_id="test-file-7",
        )

        result = await usecase.start_import(request)

        assert result.is_failure
        assert isinstance(result.error, InvalidInputError)


class TestStartImportNoInput:
    """start_import — нет входных данных."""

    @pytest.mark.asyncio
    async def test_start_import_no_input_raises_error(self) -> None:
        file_storage = MockFileStoragePort()
        file_validation = MockFileValidationPort()
        chat_access = MockChatAccessValidationPort()
        message_ingestion = MockMessageIngestionPort()
        chunk_generator = MockChunkGeneratorPort()

        usecase = ImportMessagesUseCase(
            file_storage=file_storage,
            file_validation=file_validation,
            chat_access=chat_access,
            message_ingestion=message_ingestion,
            chunk_generator=chunk_generator,
        )

        request = ImportRequest(
            file_content=None,
            json_data=None,
            chat_id_override=None,
            file_id="test-file-8",
        )

        result = await usecase.start_import(request)

        assert result.is_failure
        assert isinstance(result.error, InvalidInputError)


class TestCancelImportCancelsTask:
    """cancel_import — отмена задачи."""

    @pytest.mark.asyncio
    async def test_cancel_import_cancels_task(self) -> None:
        file_storage = MockFileStoragePort()
        file_validation = MockFileValidationPort(validation_result=_make_valid_validation_result())
        chat_access = MockChatAccessValidationPort()
        message_ingestion = MockMessageIngestionPort()
        chunk_generator = MockChunkGeneratorPort(delay=2.0)

        usecase = ImportMessagesUseCase(
            file_storage=file_storage,
            file_validation=file_validation,
            chat_access=chat_access,
            message_ingestion=message_ingestion,
            chunk_generator=chunk_generator,
        )

        request = ImportRequest(
            file_content=b'{"messages": []}',
            json_data=None,
            chat_id_override=None,
            file_id="test-file-9",
        )

        start_result = await usecase.start_import(request)
        assert start_result.is_success
        task_id = start_result.value.task_id

        await asyncio.sleep(0.1)

        cancel_result = await usecase.cancel_import(task_id)

        assert cancel_result.is_success
        assert cancel_result.value.cancelled is True


class TestCancelImportTaskNotFound:
    """cancel_import — задача не найдена."""

    @pytest.mark.asyncio
    async def test_cancel_import_task_not_found_raises_error(self) -> None:
        file_storage = MockFileStoragePort()
        file_validation = MockFileValidationPort()
        chat_access = MockChatAccessValidationPort()
        message_ingestion = MockMessageIngestionPort()
        chunk_generator = MockChunkGeneratorPort()

        usecase = ImportMessagesUseCase(
            file_storage=file_storage,
            file_validation=file_validation,
            chat_access=chat_access,
            message_ingestion=message_ingestion,
            chunk_generator=chunk_generator,
        )

        result = await usecase.cancel_import("non-existent-task")

        assert result.is_failure
        assert isinstance(result.error, TaskNotFoundError)


class TestGetProgressReturnsData:
    """get_progress — возвращает данные."""

    @pytest.mark.asyncio
    async def test_get_progress_returns_data(self) -> None:
        file_storage = MockFileStoragePort()
        file_validation = MockFileValidationPort(validation_result=_make_valid_validation_result())
        chat_access = MockChatAccessValidationPort()
        message_ingestion = MockMessageIngestionPort()
        chunk_generator = MockChunkGeneratorPort(delay=0.5)

        usecase = ImportMessagesUseCase(
            file_storage=file_storage,
            file_validation=file_validation,
            chat_access=chat_access,
            message_ingestion=message_ingestion,
            chunk_generator=chunk_generator,
        )

        request = ImportRequest(
            file_content=b'{"messages": []}',
            json_data=None,
            chat_id_override=None,
            file_id="test-file-10",
        )

        start_result = await usecase.start_import(request)
        assert start_result.is_success
        task_id = start_result.value.task_id

        await asyncio.sleep(0.1)

        progress_result = await usecase.get_progress(task_id)

        assert progress_result.is_success
        progress = progress_result.value
        assert isinstance(progress, ProgressData)
        assert progress.task_id == task_id


class TestGetProgressTaskNotFound:
    """get_progress — задача не найдена."""

    @pytest.mark.asyncio
    async def test_get_progress_task_not_found_raises_error(self) -> None:
        file_storage = MockFileStoragePort()
        file_validation = MockFileValidationPort()
        chat_access = MockChatAccessValidationPort()
        message_ingestion = MockMessageIngestionPort()
        chunk_generator = MockChunkGeneratorPort()

        usecase = ImportMessagesUseCase(
            file_storage=file_storage,
            file_validation=file_validation,
            chat_access=chat_access,
            message_ingestion=message_ingestion,
            chunk_generator=chunk_generator,
        )

        result = await usecase.get_progress("non-existent-task")

        assert result.is_failure
        assert isinstance(result.error, TaskNotFoundError)
