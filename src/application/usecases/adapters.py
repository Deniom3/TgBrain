"""Адаптеры портов для UseCase-классов.

Тонкие обёртки над существующими сервисами, обеспечивающие соответствие
интерфейсам Protocol-портов application слоя. Без бизнес-логики — только делегирование.
"""

from __future__ import annotations

import json
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Any, AsyncIterator

from src.application.usecases.protocols import (
    ChatAccessInfo,
    ChatAccessValidationPort,
    ChatSettingsData,
    ChatSettingsPort,
    ChunkGeneratorPort,
    ConnectionProviderPort,
    EmbeddingGeneratorPort,
    ExternalMessageData,
    FileStoragePort,
    FileValidationPort,
    LLMGenerationPort,
    MessageFetcherPort,
    MessageIngestionPort,
    SaveResult,
    SummaryGenerationPort,
    SummaryRepositoryPort,
    SummarySearchPort,
    ValidationResult,
    VectorSearchPort,
)
from src.models.data_models import ChatSummary, MessageRecord, SummaryRecord

logger = logging.getLogger(__name__)


# ==========================
# AskQuestionUseCase адаптеры
# ==========================


class EmbeddingsClientAsEmbeddingGeneratorPort(EmbeddingGeneratorPort):
    """Адаптер EmbeddingsClient → EmbeddingGeneratorPort."""

    def __init__(self, embeddings_client: Any) -> None:  # noqa: ANN401 — dynamic DI wrapper
        self._embeddings_client = embeddings_client

    async def get_embedding(self, text: str) -> list[float]:
        return await self._embeddings_client.get_embedding(text)


class RAGSearchAsVectorSearchPort(VectorSearchPort):
    """Адаптер RAGSearch → VectorSearchPort."""

    def __init__(self, rag_search: Any) -> None:  # noqa: ANN401 — dynamic DI wrapper
        self._rag_search = rag_search

    async def search_similar(
        self,
        embedding: list[float],
        top_k: int,
        chat_id: int | None,
    ) -> list[MessageRecord]:
        return await self._rag_search.search_similar(
            query_embedding=embedding,
            top_k=top_k,
            chat_id=chat_id,
        )

    async def expand_search_results(
        self,
        messages: list[MessageRecord],
        chat_id: int | None,
        context_window: int,
    ) -> list[MessageRecord]:
        return await self._rag_search.expand_search_results(
            messages=messages,
            chat_id=chat_id,
            expand_context=True,
            context_window=context_window,
        )


class ChatSummarySearchServiceAsSummarySearchPort(SummarySearchPort):
    """Адаптер ChatSummarySearchService → SummarySearchPort."""

    def __init__(self, summary_search: Any) -> None:  # noqa: ANN401 — dynamic DI wrapper
        self._summary_search = summary_search

    async def search_summaries(
        self,
        embedding: list[float],
        top_k: int,
        chat_id: int | None,
    ) -> list[SummaryRecord]:
        return await self._summary_search.search_summaries(
            query_embedding=embedding,
            limit=top_k,
            chat_id=chat_id,
        )


class LLMClientAsLLMGenerationPort(LLMGenerationPort):
    """Адаптер LLMClient → LLMGenerationPort."""

    def __init__(self, llm_client: Any) -> None:  # noqa: ANN401 — dynamic DI wrapper
        self._llm_client = llm_client

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        return await self._llm_client.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
        )


# ==========================
# GenerateSummaryUseCase адаптеры
# ==========================


class ChatSummaryRepositoryAsSummaryRepositoryPort(SummaryRepositoryPort):
    """Адаптер ChatSummaryRepository → SummaryRepositoryPort."""

    def __init__(self, summary_repo: Any) -> None:  # noqa: ANN401 — dynamic DI wrapper
        self._repo = summary_repo

    async def get_cached_summary_by_hash(
        self,
        conn: Any,
        content_hash: str,
        cache_ttl: int | None,
    ) -> SummaryRecord | None:
        return await self._repo.get_cached_summary_record_by_hash(
            conn, content_hash, cache_ttl,
        )

    async def get_pending_task_by_hash(
        self,
        conn: Any,
        content_hash: str,
    ) -> SummaryRecord | None:
        return await self._repo.get_pending_task_record_by_hash(conn, content_hash)

    async def create_summary_task(
        self,
        conn: Any,
        chat_id: int,
        period_start: str,
        period_end: str,
        content_hash: str,
        metadata: dict[str, Any] | None,
    ) -> tuple[int, Any, str] | None:
        result = await self._repo.create_summary_task_with_parsed_dates(
            conn, chat_id, period_start, period_end, content_hash, metadata,
        )
        if result is None:
            return None
        task_id, created_at, status = result
        return task_id, created_at, getattr(status, "value", str(status))

    async def update_status(
        self,
        conn: Any,
        task_id: int,
        status: str,
        result_text: str | None,
        metadata: dict[str, Any] | None,
        messages_count: int | None = None,
    ) -> None:
        await self._repo.update_status(conn, task_id, status, result_text, metadata, messages_count)

    async def cleanup_old_failed_tasks(
        self,
        conn: Any,
        chat_id: int,
        older_than_hours: int = 24,
    ) -> int:
        return await self._repo.cleanup_old_failed_tasks(conn, chat_id, older_than_hours)

    async def get_summary_task(
        self,
        conn: Any,
        task_id: int,
    ) -> ChatSummary | None:
        return await self._repo.get_summary_task(conn, task_id)

    async def cleanup_old_tasks(
        self,
        conn: Any,
        older_than_hours: int = 24,
    ) -> int:
        return await self._repo.cleanup_old_tasks(conn, older_than_hours)


class RAGSearchAsMessageFetcherPort(MessageFetcherPort):
    """Адаптер RAGSearch → MessageFetcherPort."""

    def __init__(self, rag_search: Any) -> None:  # noqa: ANN401 — dynamic DI wrapper
        self._rag_search = rag_search

    async def get_messages_by_period(
        self,
        chat_id: int,
        period_hours: float,
        max_messages: int,
    ) -> list[MessageRecord]:
        return await self._rag_search.get_messages_by_period(
            period_hours=int(period_hours),
            max_messages=max_messages,
            chat_id=chat_id,
        )


class RAGSummaryAsSummaryGenerationPort(SummaryGenerationPort):
    """Адаптер RAGSummary → SummaryGenerationPort."""

    def __init__(self, rag_summary: Any) -> None:  # noqa: ANN401 — dynamic DI wrapper
        self._rag_summary = rag_summary

    @property
    def model(self) -> str:
        return getattr(self._rag_summary.config, "ollama_model", "default")

    async def summary(
        self,
        period_hours: int,
        max_messages: int,
        chat_id: int,
        custom_prompt: str | None = None,
        use_cache: bool = False,
        save_to_db: bool = False,
    ) -> str:
        return await self._rag_summary.summary(
            period_hours=period_hours,
            max_messages=max_messages,
            chat_id=chat_id,
            custom_prompt=custom_prompt,
            use_cache=use_cache,
            save_to_db=save_to_db,
        )


class ChatSettingsRepoAsChatSettingsPort(ChatSettingsPort):
    """Адаптер ChatSettingsRepository → ChatSettingsPort."""

    def __init__(self, chat_settings_repo: Any) -> None:  # noqa: ANN401 — dynamic DI wrapper
        self._chat_settings_repo = chat_settings_repo

    async def get_summary_settings(
        self,
        chat_id: int,
    ) -> ChatSettingsData | None:
        raw = await self._chat_settings_repo.get_summary_settings(chat_id)
        if raw is None:
            return None
        return ChatSettingsData(
            summary_enabled=bool(raw.get("summary_enabled", False)),
            period_minutes=raw.get("summary_period_minutes"),
            max_messages=raw.get("summary_max_messages"),
        )

    async def get_enabled_summary_chat_ids(
        self,
    ) -> list[int]:
        return await self._chat_settings_repo.get_enabled_summary_chat_ids()


class DbPoolAsConnectionProviderPort(ConnectionProviderPort):
    """Адаптер asyncpg.Pool → ConnectionProviderPort."""

    def __init__(self, db_pool: Any) -> None:  # noqa: ANN401 — dynamic DI wrapper
        self._db_pool = db_pool

    def acquire(self) -> Any:
        return self._db_pool.acquire()


# ==========================
# ImportMessagesUseCase адаптеры
# ==========================


class TempFileStorage(FileStoragePort):
    """Реализация FileStoragePort на основе tempfile."""

    def __init__(self) -> None:
        self._temp_dir = Path(tempfile.gettempdir()) / "batch_imports"
        self._temp_dir.mkdir(mode=0o700, exist_ok=True)

    async def save_to_temp(
        self,
        content: bytes,
        max_size: int,
    ) -> str:
        if len(content) > max_size:
            raise ValueError("File exceeds maximum allowed size")
        import uuid
        file_path = self._temp_dir / f"{uuid.uuid4()}.json"
        file_path.write_bytes(content)
        return str(file_path)

    async def save_json_to_temp(
        self,
        data: dict[str, Any],
        file_id: str,
    ) -> str:
        try:
            uuid.UUID(file_id)
        except ValueError:
            raise ValueError("Invalid file_id: must be a valid UUID")
        file_path = self._temp_dir / f"{file_id}.json"
        file_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return str(file_path)

    async def delete_file(
        self,
        path: str,
    ) -> None:
        resolved = Path(path).resolve()
        if not resolved.is_relative_to(self._temp_dir.resolve()):
            raise ValueError(f"Path {path} is outside temp directory")
        if resolved.exists():
            resolved.unlink()


class BatchImportFileServiceAsFileValidationPort(FileValidationPort):
    """Адаптер BatchImportFileService → FileValidationPort."""

    def __init__(self, file_service: Any) -> None:  # noqa: ANN401 — dynamic DI wrapper
        self._file_service = file_service

    async def validate_content(
        self,
        file_path: str,
    ) -> ValidationResult:
        result = self._file_service.validate_file_content_full(file_path)
        return ValidationResult(
            messages_count=result["messages_count"],
            chat_info=result.get("chat_info"),
        )

    async def validate_json_data(
        self,
        data: dict[str, Any],
    ) -> ValidationResult:
        raw = self._file_service.validate_json_data(data)
        return ValidationResult(
            messages_count=raw["messages_count"],
            chat_info=raw.get("chat_info"),
        )


class ChatAccessValidatorAsChatAccessValidationPort(ChatAccessValidationPort):
    """Адаптер ChatAccessValidator → ChatAccessValidationPort."""

    def __init__(self, chat_access_validator: Any) -> None:  # noqa: ANN401 — dynamic DI wrapper
        self._validator = chat_access_validator

    async def validate_access(
        self,
        user_id: int,
        chat_info: ChatAccessInfo,
    ) -> None:
        del user_id
        from src.domain.value_objects import ChatId, ChatTitle, ChatType
        chat_id_vo = ChatId(chat_info.chat_id)
        chat_title_vo = ChatTitle(chat_info.chat_title or f"Chat {chat_info.chat_id}")
        chat_type_vo = ChatType(chat_info.chat_type or "private")
        await self._validator.validate_access(
            chat_id=chat_id_vo,
            chat_title=chat_title_vo,
            chat_type=chat_type_vo,
        )


class ExternalMessageSaverAsMessageIngestionPort(MessageIngestionPort):
    """Адаптер ExternalMessageSaver → MessageIngestionPort."""

    def __init__(self, external_saver: Any) -> None:  # noqa: ANN401 — dynamic DI wrapper
        self._external_saver = external_saver

    async def save_external_message(
        self,
        msg: ExternalMessageData,
    ) -> SaveResult:
        result = await self._external_saver.save_external_message(
            chat_id=msg.chat_id,
            text=msg.text,
            date=msg.date,
            sender_id=msg.sender_id,
        )
        return SaveResult(
            message_id=result.message_id or 0,
            is_duplicate=result.status.duplicate if result.status else False,
        )


class StreamingChunkGeneratorAsChunkGeneratorPort(ChunkGeneratorPort):
    """Адаптер StreamingChunkGenerator → ChunkGeneratorPort."""

    def __init__(self, chunk_generator_class: Any) -> None:  # noqa: ANN401 — dynamic DI wrapper
        self._chunk_generator_class = chunk_generator_class

    async def iterate_chunks(
        self,
        file_path: str,
        chunk_size: int,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        generator = self._chunk_generator_class(file_path=file_path, chunk_size=chunk_size)
        for chunk_dict in generator.iterate_chunks_as_dicts():
            yield chunk_dict

    async def get_total_count(
        self,
        file_path: str,
    ) -> int:
        generator = self._chunk_generator_class(file_path=file_path)
        return generator.get_total_count()
