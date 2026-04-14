"""Протоколы-порты для UseCase-классов.

Содержит 16 Protocol-портов для трёх UseCase-классов:
- AskQuestionUseCase (5 портов)
- GenerateSummaryUseCase (6 портов)
- ImportMessagesUseCase (5 портов)

Все протоколы используют структурную типизацию (typing.Protocol).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncIterator, Protocol

from src.models.data_models import ChatSummary, MessageRecord, SummaryRecord


class ConnectionProviderPort(Protocol):
    """Порт предоставления соединений с БД.

    Абстракция над asyncpg.Pool для использования в application слое.
    """

    def acquire(self) -> Any:
        """Возвращает контекстный менеджер для получения соединения."""

# ==========================
# DTO-типы для UseCase-уровня
# ==========================


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Результат валидации файла."""

    messages_count: int
    chat_info: dict[str, Any] | None = None  # noqa: ANN401 — extension point для метаданных валидации


@dataclass(frozen=True, slots=True)
class SaveResult:
    """Результат сохранения сообщения."""

    message_id: int
    is_duplicate: bool = False


@dataclass(frozen=True, slots=True)
class ChatSettingsData:
    """Настройки summary для чата (UseCase-level DTO)."""

    summary_enabled: bool
    period_minutes: int | None = None
    max_messages: int | None = None


@dataclass(frozen=True, slots=True)
class ChatAccessInfo:
    """Информация о чате для проверки доступа (UseCase-level DTO)."""

    chat_id: int
    chat_title: str | None = None
    chat_type: str | None = None


@dataclass(frozen=True, slots=True)
class ExternalMessageData:
    """Данные внешнего сообщения для сохранения (UseCase-level DTO)."""

    chat_id: int
    sender_id: int | None
    text: str
    date: datetime
    message_type: str
    metadata: dict[str, Any] | None = None  # noqa: ANN401 — extension point для произвольных метаданных


# ==========================
# AskQuestionUseCase порты
# ==========================
# AskQuestionUseCase порты
# ==========================


class EmbeddingGeneratorPort(Protocol):
    """Порт генерации эмбеддингов для текста вопроса."""

    async def get_embedding(self, text: str) -> list[float]:
        """Генерирует вектор эмбеддинга для текста."""


class VectorSearchPort(Protocol):
    """Порт поиска в векторном хранилище сообщений."""

    async def search_similar(
        self,
        embedding: list[float],
        top_k: int,
        chat_id: int | None,
    ) -> list[MessageRecord]:
        """Ищет похожие сообщения по эмбеддингу."""

    async def expand_search_results(
        self,
        messages: list[MessageRecord],
        chat_id: int | None,
        context_window: int,
    ) -> list[MessageRecord]:
        """Расширяет результаты поиска контекстными сообщениями."""


class SummarySearchPort(Protocol):
    """Порт поиска по ранее сгенерированным summary."""

    async def search_summaries(
        self,
        embedding: list[float],
        top_k: int,
        chat_id: int | None,
    ) -> list[SummaryRecord]:
        """Ищет похожие summary по эмбеддингу."""


class LLMGenerationPort(Protocol):
    """Порт генерации ответа через LLM."""

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Генерирует текстовый ответ через LLM."""


class ChatExistenceChecker(Protocol):
    """Порт проверки существования чата."""

    async def check_chat_exists(self, chat_id: int) -> bool:
        """Проверяет, существует ли чат."""


# ==========================
# GenerateSummaryUseCase порты
# ==========================


class SummaryRepositoryPort(Protocol):
    """Порт работы с репозиторием summary."""

    async def get_cached_summary_by_hash(
        self,
        conn: Any,
        content_hash: str,
        cache_ttl: int | None,
    ) -> SummaryRecord | None:
        """Возвращает кэшированную summary по хэшу."""

    async def get_pending_task_by_hash(
        self,
        conn: Any,
        content_hash: str,
    ) -> SummaryRecord | None:
        """Возвращает ожидающую задачу по хэшу."""

    async def create_summary_task(
        self,
        conn: Any,
        chat_id: int,
        period_start: str,
        period_end: str,
        content_hash: str,
        metadata: dict[str, Any] | None,
    ) -> tuple[int, Any, str] | None:
        """Создаёт задачу на генерацию summary."""

    async def update_status(
        self,
        conn: Any,
        task_id: int,
        status: str,
        result_text: str | None,
        metadata: dict[str, Any] | None,
        messages_count: int | None = None,
    ) -> None:
        """Обновляет статус задачи."""

    async def cleanup_old_failed_tasks(
        self,
        conn: Any,
        chat_id: int,
        older_than_hours: int = 24,
    ) -> int:
        """Удаляет failed-задачи старше указанного времени."""

    async def get_summary_task(
        self,
        conn: Any,
        task_id: int,
    ) -> ChatSummary | None:
        """Возвращает задачу по ID."""

    async def cleanup_old_tasks(
        self,
        conn: Any,
        older_than_hours: int = 24,
    ) -> int:
        """Удаляет старые задачи."""


class MessageFetcherPort(Protocol):
    """Порт получения сообщений за период."""

    async def get_messages_by_period(
        self,
        chat_id: int,
        period_hours: float,
        max_messages: int,
    ) -> list[MessageRecord]:
        """Получает сообщения чата за указанный период."""


class SummaryGenerationPort(Protocol):
    """Порт генерации summary из сообщений."""

    @property
    def model(self) -> str:
        """Название модели для генерации summary."""

    async def summary(
        self,
        period_hours: int,
        max_messages: int,
        chat_id: int,
        custom_prompt: str | None = None,
        use_cache: bool = False,
        save_to_db: bool = False,
    ) -> str:
        """Генерирует summary."""


class EmbeddingDispatcherPort(Protocol):
    """Порт диспетчеризации эмбеддинга для summary."""

    async def dispatch_embedding(
        self,
        task_id: int,
        digest: str,
        model_name: str,
    ) -> bool:
        """Отправляет задачу на генерацию эмбеддинга для summary."""


class WebhookDispatcherPort(Protocol):
    """Порт отправки вебхуков при завершении генерации."""

    async def dispatch_webhook_on_completion(
        self,
        task_id: int,
        chat_id: int,
    ) -> bool:
        """Отправляет вебхук при завершении генерации summary."""


class ChatSettingsPort(Protocol):
    """Порт получения настроек summary для чата."""

    async def get_summary_settings(
        self,
        chat_id: int,
    ) -> ChatSettingsData | None:
        """Возвращает настройки summary для чата."""

    async def get_enabled_summary_chat_ids(
        self,
    ) -> list[int]:
        """Возвращает ID чатов с включённой генерацией summary."""


# ==========================
# ImportMessagesUseCase порты
# ==========================


class FileStoragePort(Protocol):
    """Порт временного хранения файлов."""

    async def save_to_temp(
        self,
        content: bytes,
        max_size: int,
    ) -> str:
        """Сохраняет содержимое во временное хранилище, возвращает путь."""

    async def save_json_to_temp(
        self,
        data: dict[str, Any],
        file_id: str,
    ) -> str:
        """Сохраняет JSON-данные во временное хранилище, возвращает путь."""

    async def delete_file(
        self,
        path: str,
    ) -> None:
        """Удаляет файл из временного хранилища."""


class FileValidationPort(Protocol):
    """Порт валидации содержимого файлов."""

    async def validate_content(
        self,
        file_path: str,
    ) -> ValidationResult:
        """Валидирует содержимое файла."""

    async def validate_json_data(
        self,
        data: dict[str, Any],
    ) -> ValidationResult:
        """Валидирует JSON-данные."""


class ChatAccessValidationPort(Protocol):
    """Порт проверки доступа к чату."""

    async def validate_access(
        self,
        user_id: int,
        chat_info: ChatAccessInfo,
    ) -> None:
        """Проверяет доступ пользователя к чату. Вызывает PermissionError при отказе."""


class MessageIngestionPort(Protocol):
    """Порт сохранения внешних сообщений."""

    async def save_external_message(
        self,
        msg: ExternalMessageData,
    ) -> SaveResult:
        """Сохраняет внешнее сообщение."""


class ChunkGeneratorPort(Protocol):
    """Порт итерации по чанкам файла."""

    def iterate_chunks(
        self,
        file_path: str,
        chunk_size: int,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Итерирует по чанкам файла."""

    async def get_total_count(
        self,
        file_path: str,
    ) -> int:
        """Возвращает общее количество записей в файле."""
