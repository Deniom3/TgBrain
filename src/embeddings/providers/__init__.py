"""
Embedding провайдеры для TgBrain.

Поддерживаемые провайдеры:
- Ollama (локально)
- LM Studio (локально)
- Google Gemini (text-embedding-004)
- OpenRouter (OpenAI и другие модели)

Пример использования:
    from src.embeddings.providers import create_embedding_provider, EmbeddingProviderFactory

    # Через фабрику
    provider = EmbeddingProviderFactory.create(settings, "ollama")

    # Через удобную функцию
    provider = create_embedding_provider(settings, provider_name="lm-studio")

    # Получить эмбеддинг
    embedding = await provider.get_embedding("Привет, мир!")
"""

import logging
from typing import Type

from src.config import Settings

from .base import BaseEmbeddingProvider, EmbeddingProviderError
from .gemini import GeminiEmbeddingProvider, GeminiEmbeddingError
from .lmstudio import LMStudioEmbeddingProvider, LMStudioEmbeddingError
from .ollama import OllamaEmbeddingProvider, OllamaEmbeddingError
from .openrouter import (
    OpenRouterEmbeddingProvider,
    OpenRouterEmbeddingError,
)

logger = logging.getLogger(__name__)


class EmbeddingProviderFactory:
    """Фабрика для создания embedding провайдеров."""

    # Маппинг имён провайдеров на классы
    PROVIDERS: dict[str, Type["BaseEmbeddingProvider"]] = {
        "ollama": OllamaEmbeddingProvider,
        "lm-studio": LMStudioEmbeddingProvider,
        "lm_studio": LMStudioEmbeddingProvider,  # Алиас
        "gemini": GeminiEmbeddingProvider,
        "openrouter": OpenRouterEmbeddingProvider,
        "open-router": OpenRouterEmbeddingProvider,  # Алиас
    }

    # Конфигурация провайдеров по умолчанию
    DEFAULT_CONFIGS = {
        "ollama": {
            "base_url": "http://localhost:11434",
            "model": "nomic-embed-text",
            "dimension": 768,
        },
        "lm-studio": {
            "base_url": "http://localhost:1234",
            "model": "text-embedding-model",
            "dimension": 768,
        },
        "gemini": {
            "model": "text-embedding-004",
            "dimension": 768,
        },
        "openrouter": {
            "model": "openai/text-embedding-3-small",
            "dimension": 1536,
        },
    }

    @classmethod
    def get_provider_class(
        cls, provider_name: str
    ) -> Type["BaseEmbeddingProvider"] | None:
        """
        Получить класс провайдера по имени.

        Args:
            provider_name: Название провайдера.

        Returns:
            Класс провайдера или None если не найден.
        """
        provider_name = provider_name.lower()
        return cls.PROVIDERS.get(provider_name)

    @classmethod
    def create(
        cls,
        config: Settings,
        provider_name: str | None = None,
        instance_id: str | None = None
    ) -> BaseEmbeddingProvider:
        """
        Создать экземпляр embedding провайдера.

        Args:
            config: Настройки приложения.
            provider_name: Название провайдера (опционально).
            instance_id: Уникальный ID экземпляра (для Ollama).

        Returns:
            Экземпляр провайдера.

        Raises:
            ValueError: Если провайдер не найден или не настроен.
        """
        # Определяем имя провайдера
        name = provider_name or config.ollama_embedding_provider or "ollama"
        name = name.lower()

        provider_class = cls.get_provider_class(name)

        if not provider_class:
            available = ", ".join(cls.PROVIDERS.keys())
            raise ValueError(
                f"Неизвестный embedding провайдер: {name}. "
                f"Доступные: {available}"
            )

        # Создаём провайдер в зависимости от типа
        if name == "ollama":
            return cls._create_ollama(config)
        elif name in ["lm-studio", "lm_studio"]:
            return cls._create_lm_studio(config)
        elif name == "gemini":
            return cls._create_gemini(config)
        elif name == "openrouter":
            return cls._create_openrouter(config)
        else:
            raise ValueError(f"Неподдерживаемый провайдер: {name}")

    @classmethod
    async def create_async(
        cls,
        config: Settings,
        provider_name: str | None = None,
        instance_id: str | None = None,
        auto_detect_dimension: bool = True
    ) -> BaseEmbeddingProvider:
        """
        Создать экземпляр embedding провайдера (асинхронная версия).
        
        Args:
            config: Настройки приложения.
            provider_name: Название провайдера (опционально).
            instance_id: Уникальный ID экземпляра (для Ollama).
            auto_detect_dimension: Автоматически определить размерность для Ollama.

        Returns:
            Экземпляр провайдера.

        Raises:
            ValueError: Если провайдер не найден или не настроен.
        """
        # Определяем имя провайдера
        name = provider_name or config.ollama_embedding_provider or "ollama"
        name = name.lower()

        provider_class = cls.get_provider_class(name)

        if not provider_class:
            available = ", ".join(cls.PROVIDERS.keys())
            raise ValueError(
                f"Неизвестный embedding провайдер: {name}. "
                f"Доступные: {available}"
            )

        # Создаём провайдер в зависимости от типа
        if name == "ollama":
            return await cls._create_ollama_async(
                config, 
                auto_detect_dimension=auto_detect_dimension
            )
        elif name in ["lm-studio", "lm_studio"]:
            return cls._create_lm_studio(config)
        elif name == "gemini":
            return cls._create_gemini(config)
        elif name == "openrouter":
            return cls._create_openrouter(config)
        else:
            raise ValueError(f"Неподдерживаемый провайдер: {name}")

    @classmethod
    def _create_ollama(
        cls,
        config: Settings
    ) -> OllamaEmbeddingProvider:
        """Создать Ollama embedding провайдер (синхронно)."""
        emb_cfg = config.embedding_config.ollama
        dimension = emb_cfg.dim
        if dimension is None:
            raise RuntimeError("Размерность ollama_embedding_dim не указана в конфигурации")
        return OllamaEmbeddingProvider(
            base_url=emb_cfg.url,
            model=emb_cfg.model,
            dimension=dimension,
            max_retries=emb_cfg.max_retries,
            timeout=emb_cfg.timeout,
        )

    @classmethod
    async def _create_ollama_async(
        cls,
        config: Settings,
        auto_detect_dimension: bool = True
    ) -> OllamaEmbeddingProvider:
        """
        Создать Ollama embedding провайдер с авто-определением размерности.
        
        Args:
            config: Настройки приложения.
            auto_detect_dimension: Автоматически определить размерность от сервера.
        """
        emb_cfg = config.embedding_config.ollama
        
        # Создаём провайдер с временной размерностью
        provider = OllamaEmbeddingProvider(
            base_url=emb_cfg.url,
            model=emb_cfg.model,
            dimension=emb_cfg.dim or 768,  # Временное значение
            max_retries=emb_cfg.max_retries,
            timeout=emb_cfg.timeout,
        )
        
        # Авто-определение размерности от сервера (только если не указана в конфиге)
        if auto_detect_dimension and not emb_cfg.dim:
            try:
                logger.info(
                    "Авто-определение размерности для модели "
                    "'%s'...",
                    emb_cfg.model,
                )
                dimension = await provider.get_embedding_dimension()
                
                if dimension > 0:
                    provider.dimension = dimension
                    logger.info(
                        "Установлена размерность: %s для модели "
                        "'%s'",
                        dimension,
                        emb_cfg.model,
                    )
                else:
                    logger.warning(
                        "Не удалось определить размерность, используется "
                        "значение по умолчанию: 768"
                    )
            except Exception as e:
                # PY-004: Dimension detection boundary — broad except justified; falls back to default dimension
                logger.warning(
                    "Ошибка при определении размерности: %s, "
                    "используется значение по умолчанию: 768",
                    type(e).__name__,
                )
        elif emb_cfg.dim:
            logger.info(
                "Используем размерность из конфига: %s "
                "для модели '%s'",
                emb_cfg.dim,
                emb_cfg.model,
            )
        
        return provider

    @classmethod
    def _create_lm_studio(cls, config: Settings) -> LMStudioEmbeddingProvider:
        """Создать LM Studio embedding провайдер."""
        emb_cfg = config.embedding_config.lm_studio
        return LMStudioEmbeddingProvider(
            base_url=emb_cfg.url,
            model=emb_cfg.model,
            dimension=emb_cfg.dim,
            api_key=emb_cfg.api_key,
            max_retries=emb_cfg.max_retries,
            timeout=emb_cfg.timeout,
            normalize=emb_cfg.normalize,
        )

    @classmethod
    def _create_gemini(cls, config: Settings) -> GeminiEmbeddingProvider:
        """Создать Gemini embedding провайдер."""
        if not config.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY не указан. "
                "Получите ключ на https://aistudio.google.com/apikey"
            )

        emb_cfg = config.embedding_config.gemini
        return GeminiEmbeddingProvider(
            api_key=config.gemini_api_key,
            model=emb_cfg.model,
            dimension=emb_cfg.dim,
            base_url=config.gemini_base_url,
            max_retries=emb_cfg.max_retries,
            timeout=emb_cfg.timeout,
            normalize=emb_cfg.normalize,
        )

    @classmethod
    def _create_openrouter(cls, config: Settings) -> OpenRouterEmbeddingProvider:
        """Создать OpenRouter embedding провайдер."""
        if not config.openrouter_api_key:
            raise ValueError(
                "OPENROUTER_API_KEY не указан. "
                "Получите ключ на https://openrouter.ai/keys"
            )

        emb_cfg = config.embedding_config.openrouter
        return OpenRouterEmbeddingProvider(
            api_key=config.openrouter_api_key,
            model=emb_cfg.model,
            dimension=emb_cfg.dim,
            base_url=config.openrouter_base_url,
            max_retries=emb_cfg.max_retries,
            timeout=emb_cfg.timeout,
            normalize=emb_cfg.normalize,
            batch_size=emb_cfg.batch_size,
        )

    @classmethod
    def get_available_providers(cls) -> list[str]:
        """
        Получить список доступных провайдеров.

        Returns:
            Список названий провайдеров.
        """
        return list(cls.PROVIDERS.keys())


def create_embedding_provider(
    config: Settings,
    provider_name: str | None = None,
    instance_id: str | None = None
) -> BaseEmbeddingProvider:
    """
    Создать embedding провайдер на основе настроек.

    Удобная функция для быстрого создания провайдера.

    Args:
        config: Настройки приложения.
        provider_name: Название провайдера (опционально).
        instance_id: Уникальный ID экземпляра (для Ollama).

    Returns:
        Экземпляр провайдера.

    Raises:
        ValueError: Если провайдер не найден.

    Пример:
        settings = Settings()
        provider = create_embedding_provider(settings, "ollama")
        embedding = await provider.get_embedding("Привет!")
    """
    return EmbeddingProviderFactory.create(config, provider_name, instance_id)


def get_available_embedding_providers() -> list[str]:
    """
    Получить список доступных embedding провайдеров.

    Returns:
        Список названий провайдеров.
    """
    return EmbeddingProviderFactory.get_available_providers()


# Экспорт всех классов и функций
__all__ = [
    # Фабрика
    "EmbeddingProviderFactory",

    # Удобные функции
    "create_embedding_provider",
    "get_available_embedding_providers",

    # Базовый класс
    "BaseEmbeddingProvider",
    "EmbeddingProviderError",

    # Провайдеры
    "OllamaEmbeddingProvider",
    "LMStudioEmbeddingProvider",
    "GeminiEmbeddingProvider",
    "OpenRouterEmbeddingProvider",

    # Ошибки
    "OllamaEmbeddingError",
    "LMStudioEmbeddingError",
    "GeminiEmbeddingError",
    "OpenRouterEmbeddingError",
]
