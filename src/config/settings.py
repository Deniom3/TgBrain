"""
Основные настройки приложения через pydantic-settings.
Загрузка настроек из переменных окружения (.env файл).
"""

from functools import lru_cache
import logging
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .providers import ProviderConfigMixin

logger = logging.getLogger(__name__)


# ==================== Nested Embedding Config Models ====================

class OllamaEmbeddingConfig(BaseModel):
    """Конфигурация Ollama embedding провайдера."""
    model_config = {"extra": "forbid"}
    url: str = "http://localhost:11434"
    model: str = "nomic-embed-text"
    dim: int | None = None
    max_retries: int = 3
    timeout: int = 30
    normalize: bool = False


class GeminiEmbeddingConfig(BaseModel):
    """Конфигурация Gemini embedding провайдера."""
    model_config = {"extra": "forbid"}
    url: str = "https://generativelanguage.googleapis.com/v1beta"
    model: str = "text-embedding-004"
    dim: int = 768
    max_retries: int = 3
    timeout: int = 30
    normalize: bool = False


class OpenRouterEmbeddingConfig(BaseModel):
    """Конфигурация OpenRouter embedding провайдера."""
    model_config = {"extra": "forbid"}
    url: str = "https://openrouter.ai/api/v1"
    model: str = "openai/text-embedding-3-small"
    dim: int = 1536
    max_retries: int = 3
    timeout: int = 30
    normalize: bool = False
    batch_size: int = 20


class LMStudioEmbeddingConfig(BaseModel):
    """Конфигурация LM Studio embedding провайдера."""
    model_config = {"extra": "forbid"}
    url: str = "http://localhost:1234"
    model: str = "text-embedding-model"
    dim: int = 768
    api_key: str | None = Field(default=None, repr=False, exclude=True)
    max_retries: int = 3
    timeout: int = 30
    normalize: bool = False


class EmbeddingProvidersConfig(BaseModel):
    """Контейнер конфигураций всех embedding провайдеров."""
    ollama: OllamaEmbeddingConfig
    gemini: GeminiEmbeddingConfig
    openrouter: OpenRouterEmbeddingConfig
    lm_studio: LMStudioEmbeddingConfig


class Settings(BaseSettings, ProviderConfigMixin):
    """
    Класс настроек приложения.

    Загружает переменные из .env файла и переменных окружения.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        protected_namespaces=(),
        frozen=True,
    )

    # ==================== Telegram ====================
    tg_api_id: int | None = Field(default=None, description="Telegram API ID", ge=1)
    tg_api_hash: str | None = Field(default=None, description="Telegram API Hash")
    tg_phone_number: str | None = Field(default=None, description="Номер телефона Telegram")

    # ==================== API Authentication ====================
    api_key: str | None = Field(
        default=None,
        description="API ключ для защиты эндпоинтов. Если не установлен — эндпоинты публичны.",
        repr=False,
        exclude=True,
    )

    @field_validator("api_key", mode="before")
    @classmethod
    def validate_api_key(cls, value: str | None) -> str | None:
        """Преобразование пустой строки в None и проверка минимальной длины."""
        if value is None or value == "":
            return None
        if len(value) < 16:
            raise ValueError("API_KEY должен содержать минимум 16 символов")
        return value

    # ==================== Chat Management ====================
    # Параметры для инициализации чатов при старте
    tg_chat_enable: str = Field(
        default="",
        description="Список ID чатов для включения мониторинга при старте"
    )
    tg_chat_disable: str = Field(
        default="",
        description="Список ID чатов для отключения мониторинга при старте"
    )

    @field_validator("tg_api_id", mode="before")
    @classmethod
    def validate_api_id(cls, value: str | int | None) -> int | None:
        """Преобразование пустой строки в None для tg_api_id."""
        if value is None or value == "":
            return None
        return int(value) if value else None

    @field_validator("tg_api_hash", mode="before")
    @classmethod
    def validate_api_hash(cls, value: str | None) -> str | None:
        """Преобразование пустой строки в None для tg_api_hash."""
        if value is None or value == "":
            return None
        if len(value) < 32:
            logger.warning(
                "TG_API_HASH слишком короткий (%d < 32 символов), игнорируется",
                len(value),
            )
            return None
        return value

    # ==================== Database ====================
    db_host: str = Field(default="localhost", description="Хост БД")
    db_port: int = Field(default=5432, description="Порт БД", ge=1, le=65535)
    db_name: str = Field(default="tg_db", description="Имя БД")
    db_user: str = Field(default="postgres", description="Пользователь БД")
    db_password: str = Field(default="", exclude=True, repr=False, description="Пароль БД")
    db_url: str | None = Field(default=None, description="Полный URL подключения к БД", exclude=True)

    # ==================== Embedding Providers ====================
    ollama_embedding_provider: str = Field(
        default="ollama",
        description="Провайдер для эмбеддингов (ollama, gemini, openrouter)"
    )

    # ==================== Ollama (Embeddings) ====================
    ollama_embedding_url: str = Field(
        default="http://localhost:11434",
        description="URL Ollama API для эмбеддингов"
    )
    ollama_embedding_model: str = Field(
        default="nomic-embed-text",
        description="Модель для генерации эмбеддингов"
    )
    ollama_embedding_dim: int | None = Field(
        default=None,
        description="Размерность вектора (авто-определение если не указана)"
    )
    ollama_embedding_max_retries: int = Field(default=3, description="Макс. попыток")
    ollama_embedding_timeout: int = Field(default=30, description="Таймаут (сек)")
    ollama_embedding_normalize: bool = Field(default=False, description="Нормализация")

    # ==================== Gemini (Embeddings) ====================
    gemini_embedding_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta",
        description="Базовый URL Gemini Embeddings API"
    )
    gemini_embedding_model: str = Field(
        default="text-embedding-004",
        description="Модель Gemini для эмбеддингов"
    )
    gemini_embedding_dim: int = Field(default=768, description="Размерность вектора")
    gemini_embedding_max_retries: int = Field(default=3, description="Макс. попыток")
    gemini_embedding_timeout: int = Field(default=30, description="Таймаут (сек)")
    gemini_embedding_normalize: bool = Field(default=False, description="Нормализация")

    # ==================== OpenRouter (Embeddings) ====================
    openrouter_embedding_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="Базовый URL OpenRouter Embeddings API"
    )
    openrouter_embedding_model: str = Field(
        default="openai/text-embedding-3-small",
        description="Модель OpenRouter для эмбеддингов"
    )
    openrouter_embedding_dim: int = Field(default=1536, description="Размерность вектора")
    openrouter_embedding_max_retries: int = Field(default=3, description="Макс. попыток")
    openrouter_embedding_timeout: int = Field(default=30, description="Таймаут (сек)")
    openrouter_embedding_normalize: bool = Field(default=False, description="Нормализация")
    openrouter_embedding_batch_size: int = Field(
        default=20,
        description="Размер пакета для пакетной обработки"
    )

    # ==================== LM Studio (Embeddings) ====================
    lm_studio_embedding_url: str = Field(
        default="http://localhost:1234",
        description="URL LM Studio API для эмбеддингов"
    )
    lm_studio_embedding_model: str = Field(
        default="text-embedding-model",
        description="Модель LM Studio для эмбеддингов"
    )
    lm_studio_embedding_dim: int = Field(default=768, description="Размерность вектора")
    lm_studio_embedding_api_key: str | None = Field(
        default=None,
        description="API ключ LM Studio (опционально)",
        repr=False,
        exclude=True,
    )
    lm_studio_embedding_max_retries: int = Field(default=3, description="Макс. попыток")
    lm_studio_embedding_timeout: int = Field(default=30, description="Таймаут (сек)")
    lm_studio_embedding_normalize: bool = Field(default=False, description="Нормализация")

    # ==================== LLM Providers - General ====================
    llm_active_provider: str = Field(
        default="gemini",
        description="Активный провайдер LLM (gemini, openrouter, ollama, lm-studio)"
    )
    llm_fallback_providers: str = Field(
        default="openrouter,gemini",
        description="Список резервных провайдеров через запятую"
    )
    llm_auto_fallback: bool = Field(
        default=True,
        description="Автоматический fallback для локальных моделей"
    )
    llm_fallback_timeout: int = Field(default=10, description="Таймаут проверки (сек)")

    # ==================== Google Gemini ====================
    gemini_api_key: str | None = Field(default=None, description="API ключ Gemini", repr=False, exclude=True)
    gemini_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta",
        description="Базовый URL Gemini API"
    )
    gemini_model: str = Field(default="gemini-2.5-flash", description="Модель Gemini")

    # ==================== OpenRouter ====================
    openrouter_api_key: str | None = Field(default=None, description="API ключ OpenRouter", repr=False, exclude=True)
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="Базовый URL OpenRouter API"
    )
    openrouter_model: str = Field(
        default="auto",
        description="Модель OpenRouter (auto для автовыбора)"
    )

    # ==================== Ollama (LLM) ====================
    ollama_llm_enabled: bool = Field(default=True, description="Включить Ollama LLM")
    ollama_llm_base_url: str = Field(
        default="http://localhost:11434",
        description="Базовый URL Ollama LLM API"
    )
    ollama_llm_model: str = Field(default="deepseek-coder:6.7b", description="Модель Ollama")

    # ==================== LM Studio ====================
    lm_studio_enabled: bool = Field(default=False, description="Включить LM Studio")
    lm_studio_base_url: str = Field(
        default="http://localhost:1234",
        description="Базовый URL LM Studio API"
    )
    lm_studio_model: str = Field(default="qwen/qwen3.5-9b", description="Модель LM Studio")

    # ==================== Application ====================
    log_level: str = Field(default="INFO", description="Уровень логирования")
    timezone: str = Field(default="Etc/UTC", description="Часовой пояс приложения")
    summary_default_hours: int = Field(default=24, description="Период сводки (часы)")
    summary_max_messages: int = Field(default=50, description="Макс. сообщений для сводки")
    rag_top_k: int = Field(default=5, description="Количество результатов для RAG")
    rag_score_threshold: float = Field(
        default=0.3,
        description="Порог схожести для RAG",
        ge=0.0,
        le=1.0
    )

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """
        Валидация часового пояса.

        Args:
            v: Значение часового пояса.

        Returns:
            Валидное значение часового пояса.

        Raises:
            ValueError: Если часовой пояс некорректен.
        """
        try:
            ZoneInfo(v)
            return v
        except (ZoneInfoNotFoundError, ValueError, TypeError) as e:
            # PY-004: Граница конфигурации — проверяет часовой пояс при старте; пробрасывает как ValueError
            raise ValueError(f"Invalid timezone: {v}") from e

    @property
    def tz(self) -> ZoneInfo:
        """
        Получить объект часового пояса.

        Returns:
            ZoneInfo объект для текущего timezone.
        """
        return ZoneInfo(self.timezone)

    @model_validator(mode="after")
    def generate_db_url(self) -> Self:
        """Автогенерация DB_URL если не указан."""
        if not self.db_url:
            db_url = (
                f"postgresql://{self.db_user}:{self.db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}"
            )
            object.__setattr__(self, "db_url", db_url)
        return self

    @property
    def tg_chat_enable_list(self) -> list[int]:
        """
        Получение списка ID чатов для включения как список int.
        
        Returns:
            Список ID чатов для включения мониторинга.
        """
        if not self.tg_chat_enable:
            return []
        try:
            return [int(x.strip()) for x in self.tg_chat_enable.split(",")]
        except ValueError:
            logger.warning(
                "Некорректное значение TG_CHAT_ENABLE: '%s'. Возвращается пустой список.",
                self.tg_chat_enable,
            )
            return []
    
    @property
    def tg_chat_disable_list(self) -> list[int]:
        """
        Получение списка ID чатов для отключения как список int.

        Returns:
            Список ID чатов для отключения мониторинга.
        """
        if not self.tg_chat_disable:
            return []
        try:
            return [int(x.strip()) for x in self.tg_chat_disable.split(",")]
        except ValueError:
            logger.warning(
                "Некорректное значение TG_CHAT_DISABLE: '%s'. Возвращается пустой список.",
                self.tg_chat_disable,
            )
            return []

    @property
    def tg_session_name(self) -> str | None:
        """
        Возвращает session_name для обратной совместимости.

        ⚠️ DEPRECATED: session_name теперь хранится только в БД.
        Это свойство возвращает None для старых тестов.
        """
        return None

    @property
    def embedding_config(self) -> EmbeddingProvidersConfig:
        """
        Получить конфигурацию всех embedding провайдеров в виде nested models.

        Returns:
            EmbeddingProvidersConfig с конфигурацией каждого провайдера.
        """
        return EmbeddingProvidersConfig(
            ollama=OllamaEmbeddingConfig(
                url=self.ollama_embedding_url,
                model=self.ollama_embedding_model,
                dim=self.ollama_embedding_dim,
                max_retries=self.ollama_embedding_max_retries,
                timeout=self.ollama_embedding_timeout,
                normalize=self.ollama_embedding_normalize,
            ),
            gemini=GeminiEmbeddingConfig(
                url=self.gemini_embedding_url,
                model=self.gemini_embedding_model,
                dim=self.gemini_embedding_dim,
                max_retries=self.gemini_embedding_max_retries,
                timeout=self.gemini_embedding_timeout,
                normalize=self.gemini_embedding_normalize,
            ),
            openrouter=OpenRouterEmbeddingConfig(
                url=self.openrouter_embedding_url,
                model=self.openrouter_embedding_model,
                dim=self.openrouter_embedding_dim,
                max_retries=self.openrouter_embedding_max_retries,
                timeout=self.openrouter_embedding_timeout,
                normalize=self.openrouter_embedding_normalize,
                batch_size=self.openrouter_embedding_batch_size,
            ),
            lm_studio=LMStudioEmbeddingConfig(
                url=self.lm_studio_embedding_url,
                model=self.lm_studio_embedding_model,
                dim=self.lm_studio_embedding_dim,
                api_key=self.lm_studio_embedding_api_key,
                max_retries=self.lm_studio_embedding_max_retries,
                timeout=self.lm_studio_embedding_timeout,
                normalize=self.lm_studio_embedding_normalize,
            ),
        )

class SettingsWithProviders(Settings):
    """Settings с методами для работы с провайдерами (через ProviderConfigMixin в Settings)."""
    pass


@lru_cache()
def get_settings() -> SettingsWithProviders:
    """
    Получить кэшированный экземпляр Settings.

    Returns:
        Кэшированный экземпляр SettingsWithProviders.
    """
    return SettingsWithProviders()


# Глобальный экземпляр для импорта
settings = get_settings()
