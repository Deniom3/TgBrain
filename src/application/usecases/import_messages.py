"""UseCase для оркестрации пакетного импорта сообщений.

Переносит оркестрационную логику из BatchImportTaskManager.start_import()
и import_endpoint.py в application слой.
"""

from __future__ import annotations

import asyncio
import json
import logging
import pathlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, cast

from src.application.exceptions import (
    AccessDeniedError,
    FileTooLargeError,
    InvalidInputError,
    TaskNotFoundError,
    TooManyMessagesError,
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
)
from src.application.usecases.result import Failure, Result, Success

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 500 * 1024 * 1024
MAX_FILE_MESSAGES = 200000
MAX_JSON_MESSAGES = 1000
DEFAULT_CHUNK_SIZE = 100


@dataclass(frozen=True, slots=True)
class ImportRequest:
    """Входные данные для ImportMessagesUseCase."""

    file_content: bytes | None
    json_data: dict[str, Any] | None
    chat_id_override: int | None
    file_id: str
    user_id: int = 0


@dataclass(frozen=True, slots=True)
class ImportResult:
    """Результат запуска импорта."""

    task_id: str
    status: str
    file_id: str
    file_size: int
    messages_count: int
    estimated_chunks: int
    chat_id_from_file: int | None
    chat_name_from_file: str | None


@dataclass(slots=True)
class ProgressData:
    """Прогресс обработки импорта."""

    task_id: str
    status: str
    total_messages: int
    processed_messages: int = 0
    duplicates: int = 0
    errors: int = 0
    file_path: str | None = None
    filtered: int = 0
    pending: int = 0
    current_chunk: int = 0
    total_chunks: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class CancelResult:
    """Результат отмены импорта."""

    cancelled: bool
    already_done: bool = False


class ImportMessagesUseCase:
    """Оркестрация импорта: валидация → сохранение → запуск обработки → прогресс → отмена."""

    def __init__(
        self,
        file_storage: FileStoragePort,
        file_validation: FileValidationPort,
        chat_access: ChatAccessValidationPort,
        message_ingestion: MessageIngestionPort,
        chunk_generator: ChunkGeneratorPort,
    ) -> None:
        self._file_storage = file_storage
        self._file_validation = file_validation
        self._chat_access = chat_access
        self._message_ingestion = message_ingestion
        self._chunk_generator = chunk_generator
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._progress: dict[str, ProgressData] = {}
        self._lock = asyncio.Lock()

    async def start_import(
        self,
        request: ImportRequest,
    ) -> Result[ImportResult, Exception]:
        """Запустить процесс импорта сообщений."""
        has_file = request.file_content is not None
        has_json = request.json_data is not None

        if has_file == has_json:
            return Failure(InvalidInputError("Specify either file or json_data, not both"))

        temp_path: str | None = None
        messages_count = 0
        chat_id_from_file: int | None = None
        chat_name_from_file: str | None = None
        chat_type_from_file: str | None = None
        file_size = 0

        if has_file:
            content = cast(bytes, request.file_content)
            result = await self._process_file_input(content, request.file_id)
            if isinstance(result, Failure):
                return Failure(result.error)

            success_result = cast(Success[dict[str, Any], Exception], result)
            data = success_result.value
            temp_path = data["temp_path"]
            messages_count = data["messages_count"]
            chat_id_from_file = data["chat_id_from_file"]
            chat_name_from_file = data["chat_name_from_file"]
            chat_type_from_file = data["chat_type_from_file"]
            file_size = len(content)

        else:
            data_input = request.json_data
            result = await self._process_json_input(data_input, request.file_id)
            if isinstance(result, Failure):
                return Failure(result.error)

            success_result = cast(Success[dict[str, Any], Exception], result)
            data = success_result.value
            temp_path = data["temp_path"]
            messages_count = data["messages_count"]
            chat_id_from_file = data["chat_id_from_file"]
            chat_name_from_file = data["chat_name_from_file"]
            chat_type_from_file = data["chat_type_from_file"]
            file_size = data["file_size"]

        final_chat_id = request.chat_id_override or chat_id_from_file
        if final_chat_id is None:
            return Failure(InvalidInputError("chat_id is required (from upload or JSON file)"))

        try:
            await self._chat_access.validate_access(
                user_id=request.user_id,
                chat_info=ChatAccessInfo(
                    chat_id=final_chat_id,
                    chat_title=chat_name_from_file,
                    chat_type=chat_type_from_file,
                ),
            )
        except PermissionError:
            return Failure(AccessDeniedError(final_chat_id))

        estimated_chunks = (messages_count + DEFAULT_CHUNK_SIZE - 1) // DEFAULT_CHUNK_SIZE

        task_id = str(uuid.uuid4())

        background_task = asyncio.create_task(
            self._process_chunks(temp_path, final_chat_id, DEFAULT_CHUNK_SIZE, task_id),
        )
        async with self._lock:
            self._tasks[task_id] = background_task

        logger.info(
            "ImportMessagesUseCase: started task_id=%s, chat_id=%d, messages=%d",
            task_id,
            final_chat_id,
            messages_count,
        )

        return Success(ImportResult(
            task_id=task_id,
            status="processing",
            file_id=request.file_id,
            file_size=file_size,
            messages_count=messages_count,
            estimated_chunks=estimated_chunks,
            chat_id_from_file=chat_id_from_file,
            chat_name_from_file=chat_name_from_file,
        ))

    async def get_progress(
        self,
        task_id: str,
    ) -> Result[ProgressData, Exception]:
        """Получить прогресс обработки импорта."""
        async with self._lock:
            if task_id not in self._progress:
                return Failure(TaskNotFoundError(task_id))
            return Success(self._progress[task_id])

    async def cancel_import(
        self,
        task_id: str,
    ) -> Result[CancelResult, Exception]:
        """Отменить обработку импорта."""
        async with self._lock:
            if task_id not in self._progress or task_id not in self._tasks:
                return Failure(TaskNotFoundError(task_id))

            progress = self._progress[task_id]
            task = self._tasks[task_id]

        if task.done():
            return Success(CancelResult(cancelled=False, already_done=True))

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        progress.status = "cancelled"
        progress.completed_at = datetime.now(timezone.utc)

        if progress.file_path:
            await self._delete_file(progress.file_path)

        logger.info("ImportMessagesUseCase: cancelled task_id=%s", task_id)

        return Success(CancelResult(cancelled=True))

    async def _process_file_input(
        self,
        file_content: bytes,
        file_id: str,
    ) -> Result[dict[str, Any], Exception]:
        """Обработать входной файл: сохранение + валидация + извлечение информации."""
        del file_id

        try:
            temp_path = await self._file_storage.save_to_temp(file_content, MAX_FILE_SIZE)
        # Boundary: convert infrastructure error to domain error
        except ValueError:
            return Failure(FileTooLargeError())

        try:
            validation_result = await self._file_validation.validate_content(temp_path)
        # Boundary: convert infrastructure error to domain error
        except ValueError as exc:
            if "Too many messages" in str(exc):
                return Failure(TooManyMessagesError(count=0, max_count=MAX_FILE_MESSAGES))
            logger.error("Ошибка валидации файла: %s", type(exc).__name__)
            return Failure(InvalidInputError("File validation failed"))

        if validation_result.messages_count > MAX_FILE_MESSAGES:
            return Failure(TooManyMessagesError(
                count=validation_result.messages_count,
                max_count=MAX_FILE_MESSAGES,
            ))

        chat_info = validation_result.chat_info or {}
        chat_id_from_file = chat_info.get("chat_id")
        chat_name_from_file = chat_info.get("chat_name")
        chat_type_from_file = chat_info.get("chat_type")

        return Success({
            "temp_path": temp_path,
            "messages_count": validation_result.messages_count,
            "chat_id_from_file": chat_id_from_file,
            "chat_name_from_file": chat_name_from_file,
            "chat_type_from_file": chat_type_from_file,
            "file_size": len(file_content),
        })

    async def _process_json_input(
        self,
        json_data: dict[str, Any] | None,
        file_id: str,
    ) -> Result[dict[str, Any], Exception]:
        """Обработать входной JSON: валидация + сохранение + извлечение информации."""
        if json_data is None:
            return Failure(InvalidInputError("JSON data is required"))

        try:
            validation_result = await self._file_validation.validate_json_data(json_data)
        except ValueError:
            return Failure(InvalidInputError("Invalid JSON format"))

        if validation_result.messages_count > MAX_JSON_MESSAGES:
            return Failure(TooManyMessagesError(
                count=validation_result.messages_count,
                max_count=MAX_JSON_MESSAGES,
            ))

        try:
            temp_path = await self._file_storage.save_json_to_temp(json_data, file_id)
        except (json.JSONDecodeError, OSError, ValueError, KeyError) as exc:
            logger.error("Ошибка обработки JSON: %s", type(exc).__name__)
            return Failure(InvalidInputError("Failed to process JSON input"))

        chat_info = validation_result.chat_info or {}
        chat_id_from_file = chat_info.get("chat_id")
        chat_name_from_file = chat_info.get("chat_name")
        chat_type_from_file = chat_info.get("chat_type")

        file_size = pathlib.Path(temp_path).stat().st_size

        return Success({
            "temp_path": temp_path,
            "messages_count": validation_result.messages_count,
            "chat_id_from_file": chat_id_from_file,
            "chat_name_from_file": chat_name_from_file,
            "chat_type_from_file": chat_type_from_file,
            "file_size": file_size,
        })

    async def _process_chunks(
        self,
        file_path: str,
        chat_id: int,
        chunk_size: int,
        task_id: str,
    ) -> None:
        """Фоновая обработка чанков файла.

        Примечание: _process_chunks находится в UseCase слое, так как является
        частью бизнес-оркестрации импорта (итерация → сохранение → прогресс).
        Это осознанное отклонение от плана phase-04.
        """
        total_messages = await self._chunk_generator.get_total_count(file_path)
        total_chunks = (total_messages + chunk_size - 1) // chunk_size if total_messages > 0 else 1

        progress = ProgressData(
            task_id=task_id,
            status="processing",
            total_messages=total_messages,
            total_chunks=total_chunks,
            file_path=file_path,
        )
        async with self._lock:
            self._progress[task_id] = progress

        try:
            chunk_index = 0
            async for chunk in self._chunk_generator.iterate_chunks(file_path, chunk_size):
                async with self._lock:
                    task = self._tasks.get(task_id)
                    task_cancelled = task.cancelled() if task else True
                if task_cancelled:
                    break

                for msg_data in chunk:
                    if progress.status != "processing":
                        break

                    msg_date = self._parse_message_date(msg_data.get("date"))

                    external_msg = ExternalMessageData(
                        chat_id=chat_id,
                        sender_id=msg_data.get("from_id"),
                        text=msg_data.get("text", ""),
                        date=msg_date,
                        message_type=msg_data.get("type", "message"),
                        metadata=msg_data,
                    )

                    save_result = await self._message_ingestion.save_external_message(external_msg)
                    self._update_progress_from_result(progress, save_result)

                progress.current_chunk = chunk_index + 1
                chunk_index += 1
                logger.debug(
                    "ImportMessagesUseCase: chunk %d/%d, task_id=%s",
                    progress.current_chunk,
                    progress.total_chunks,
                    task_id,
                )

            if progress.status == "processing":
                progress.status = "completed"
                progress.completed_at = datetime.now(timezone.utc)
                logger.info("ImportMessagesUseCase: completed task_id=%s", task_id)

        except asyncio.CancelledError:
            progress.status = "cancelled"
            progress.completed_at = datetime.now(timezone.utc)
            raise
        # Boundary: convert infrastructure error to domain error
        except Exception as exc:
            progress.status = "failed"
            progress.error_message = self._sanitize_error(exc)
            progress.completed_at = datetime.now(timezone.utc)
            logger.error("ImportMessagesUseCase: failed task_id=%s, error=%s", task_id, type(exc).__name__)
        finally:
            if file_path:
                await self._delete_file(file_path)

            async with self._lock:
                self._tasks.pop(task_id, None)

    def _parse_message_date(self, raw_date: Any) -> datetime:  # noqa: ANN401
        """Распарсить дату сообщения из JSON-данных."""
        if isinstance(raw_date, datetime):
            return raw_date
        if isinstance(raw_date, (int, float)):
            return datetime.fromtimestamp(raw_date, tz=timezone.utc)
        if isinstance(raw_date, str):
            try:
                return datetime.fromisoformat(raw_date)
            except ValueError:
                pass
        return datetime.now(timezone.utc)

    def _update_progress_from_result(
        self,
        progress: ProgressData,
        result: SaveResult,
    ) -> None:
        """Обновить прогресс на основе результата сохранения."""
        progress.processed_messages += 1

        if result.is_duplicate:
            progress.duplicates += 1

    def _sanitize_error(self, error: Exception) -> str:
        """Санитизировать сообщение об ошибке для безопасности."""
        if isinstance(error, FileNotFoundError):
            return "File not found"
        if isinstance(error, PermissionError):
            return "Permission denied"
        if isinstance(error, ValueError):
            return "Invalid value"
        logger.debug("Unknown error type during cleanup: %s", type(error).__name__)
        return "Internal error"

    async def _delete_file(self, file_path: str) -> None:
        """Удалить временный файл."""
        try:
            await self._file_storage.delete_file(file_path)
        # Boundary: convert infrastructure error to domain error
        except Exception as exc:
            logger.warning("ImportMessagesUseCase: failed to delete file %s: %s", file_path, type(exc).__name__)
