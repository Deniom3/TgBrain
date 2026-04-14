"""
Клиент для получения эмбеддингов через различные провайдеры.

Поддерживаемые провайдеры:
- Ollama (локально)
- LM Studio (локально)
- Google Gemini (text-embedding-004)
- OpenRouter (OpenAI и другие модели)

Архитектура:
    EmbeddingsClient (обёртка)
        └── EmbeddingProviderFactory
                ├── OllamaEmbeddingProvider
                ├── LMStudioEmbeddingProvider
                ├── GeminiEmbeddingProvider
                └── OpenRouterEmbeddingProvider

Пример использования:
    from src.embeddings import EmbeddingsClient, settings

    client = EmbeddingsClient(settings)
    embedding = await client.get_embedding("Привет, мир!")
"""

import logging

from src.config import Settings
from src.embeddings.providers import (
    BaseEmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingProviderFactory,
)

logger = logging.getLogger(__name__)


class EmbeddingsError(Exception):
    """Базовое исключение для ошибок эмбеддингов."""
    pass


class EmbeddingsClient:
    """
    Клиент для генерации эмбеддингов через различные провайдеры.

    Поддерживает:
    - Выбор провайдера через конфигурацию (ollama, lm-studio, gemini, openrouter)
    - Retry-логику с экспоненциальной задержкой
    - Проверку доступности сервиса
    - Обработку типовых ошибок
    - Контекстный менеджер
    """

    config: Settings
    provider_name: str

    def __init__(
        self,
        config: Settings,
        provider_name: str | None = None
    ):
        """
        Инициализация клиента.

        Args:
            config: Настройки приложения.
            provider_name: Название провайдера (опционально).
        """
        self.config = config
        self.provider_name = provider_name or config.ollama_embedding_provider

        # Создаём провайдер через фабрику
        self._provider: BaseEmbeddingProvider | None = None
        self._provider_initialized = False

        # Получаем название текущей модели эмбеддинга
        self._current_model = self._get_model_from_config()
        
        # Размерность эмбеддинга (заполняется при инициализации)
        self._embedding_dim: int | None = None

        logger.info(
            "EmbeddingsClient инициализирован: провайдер=%s, "
            "модель=%s",
            self.provider_name,
            self._current_model,
        )
    
    def _get_model_from_config(self) -> str:
        """Получить название модели эмбеддинга из конфигурации."""
        provider = self.provider_name.lower()
        emb_cfg = self.config.embedding_config
        if provider == "ollama":
            return emb_cfg.ollama.model
        elif provider == "gemini":
            return f"gemini/{emb_cfg.gemini.model}"
        elif provider == "openrouter":
            return f"openrouter/{emb_cfg.openrouter.model}"
        elif provider in ("lm-studio", "lm_studio"):
            return f"lm-studio/{emb_cfg.lm_studio.model}"
        else:
            return f"{provider}/unknown"

    async def initialize_provider(self) -> None:
        """
        Инициализировать провайдер.
        
        Размерность берётся из конфигурации (БД).
        Вызывается один раз при старте приложения.
        """
        if self._provider_initialized:
            return
            
        try:
            logger.info("Инициализация embedding провайдера '%s'...", self.provider_name)
            
            self._provider = await EmbeddingProviderFactory.create_async(
                self.config,
                provider_name=self.provider_name,
                auto_detect_dimension=False  # Не запрашиваем, размерность уже в БД
            )
            
            # Сохраняем размерность
            self._embedding_dim = self._provider.dimension
            
            self._provider_initialized = True
            
            logger.info(
                "Embedding провайдер инициализирован: %s, "
                "модель=%s, dim=%s",
                self.provider_name,
                self._current_model,
                self._embedding_dim,
            )
            
        except Exception as e:
            # PY-004: Initialization boundary — failure to init is fatal; re-raises after logging
            logger.error("Ошибка инициализации провайдера: %s", type(e).__name__)
            raise

    async def _create_provider_async(
        self,
        provider_name: str | None = None
    ) -> BaseEmbeddingProvider:
        """Создать провайдер через фабрику (асинхронно)."""
        return await EmbeddingProviderFactory.create_async(
            self.config,
            provider_name or self.provider_name,
            auto_detect_dimension=True
        )

    @property
    def provider(self) -> BaseEmbeddingProvider:
        """Получить текущий провайдер (ленивая инициализация)."""
        if self._provider is None:
            raise RuntimeError(
                "Провайдер не инициализирован. Вызовите initialize_provider() "
                "перед использованием."
            )
        return self._provider

    @property
    def embedding_dim(self) -> int:
        """Получить размерность эмбеддинга."""
        if self._embedding_dim is None:
            if self._provider:
                return self._provider.dimension
            dim = self.config.embedding_config.ollama.dim
            if dim is None:
                raise RuntimeError("Размерность эмбеддинга не определена")
            return dim
        return self._embedding_dim

    def get_model_name(self) -> str:
        """
        Получить название текущей модели эмбеддинга.

        Returns:
            Название модели в формате "provider/model".
        """
        return self._current_model

    async def close(self) -> None:
        """Закрыть соединения провайдера."""
        if self._provider:
            await self._provider.close()
        self._provider = None
        self._provider_initialized = False

    def refresh_config(self, new_settings: "Settings") -> None:
        """Обновить ссылку на Settings после reload.

        Args:
            new_settings: Новый экземпляр Settings.
        """
        self.config = new_settings
        self.provider_name = new_settings.ollama_embedding_provider
        self._current_model = self._get_model_from_config()
        self._provider = None
        self._provider_initialized = False
        self._embedding_dim = None
        logger.debug("EmbeddingsClient обновлён: провайдер=%s", self.provider_name)

    async def reload_provider(self, config: Settings | None = None) -> None:
        """
        Перезагрузить провайдер с новыми настройками.

        Вызывается при изменении настроек эмбеддингов в runtime.

        Args:
            config: Новые настройки (опционально, используется текущий если не указан).
        """
        logger.info("Перезагрузка embedding провайдера...")

        # Обновляем конфиг если предоставлен
        if config:
            self.config = config

        # Закрываем старый провайдер и сбрасываем флаг инициализации
        await self.close()
        self._provider_initialized = False
        self._embedding_dim = None

        # Обновляем название провайдера и модели из конфига
        self.provider_name = self.config.ollama_embedding_provider
        self._current_model = self._get_model_from_config()

        # Инициализируем новый провайдер (с новой размерностью из БД)
        await self.initialize_provider()

        logger.info(
            "Embedding провайдер перезапущен: %s, "
            "модель=%s, dim=%s",
            self.provider_name,
            self._current_model,
            self._embedding_dim,
        )

    async def get_embedding(self, text: str) -> list[float]:
        """
        Получить эмбеддинг текста с retry-логикой.

        Args:
            text: Текст для векторизации.

        Returns:
            Вектор эмбеддинга.

        Raises:
            EmbeddingsError: При неудаче после всех попыток.
        """
        try:
            return await self.provider.get_embedding(text)
        except EmbeddingProviderError as e:
            logger.error("Ошибка эмбеддинга: %s", type(e).__name__)
            raise EmbeddingsError(f"Ошибка генерации эмбеддинга: {e}")
        except Exception as e:
            # PY-004: Client boundary — wraps unexpected errors into EmbeddingsError for caller
            logger.error("Неожиданная ошибка эмбеддинга: %s", type(e).__name__)
            raise EmbeddingsError(f"Неожиданная ошибка: {e}")

    async def get_embeddings_batch(
        self,
        texts: list[str],
        batch_size: int = 10
    ) -> list[list[float]]:
        """
        Получить эмбеддинги для нескольких текстов (пакетно).

        Args:
            texts: Список текстов для векторизации.
            batch_size: Размер пакета для параллельной обработки.

        Returns:
            Список векторов эмбеддингов.
        """
        # Если провайдер поддерживает пакетную обработку, используем её
        if hasattr(self.provider, 'get_embeddings_batch'):
            try:
                return await self.provider.get_embeddings_batch(texts, batch_size)
            except EmbeddingProviderError as e:
                logger.error("Ошибка пакетной генерации эмбеддингов: %s", type(e).__name__)
                raise EmbeddingsError(f"Ошибка пакетной генерации: {e}")

        # Иначе обрабатываем последовательно
        results = []
        for text in texts:
            embedding = await self.get_embedding(text)
            results.append(embedding)
        return results

    async def check_health(self) -> bool:
        """
        Проверить доступность API провайдера.

        Returns:
            True если сервис доступен, False иначе.
        """
        try:
            return await self.provider.check_health()
        except Exception as e:
            # PY-004: Health-check boundary — broad except justified; returns False on any failure
            logger.error("Ошибка проверки здоровья провайдера: %s", type(e).__name__)
            return False

    async def get_models(self) -> list[str]:
        """
        Получить список доступных моделей.

        Returns:
            Список названий моделей.
        """
        try:
            return await self.provider.get_models()
        except Exception as e:
            # PY-004: Discovery boundary — broad except justified; returns empty list on failure
            logger.error("Ошибка получения списка моделей: %s", type(e).__name__)
            return []

    async def __aenter__(self) -> "EmbeddingsClient":
        """Контекстный менеджер: вход."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Контекстный менеджер: выход."""
        await self.close()

    def __repr__(self) -> str:
        return (
            f"EmbeddingsClient("
            f"provider={self.provider_name!r})"
        )


__all__ = [
    "EmbeddingsClient",
    "EmbeddingsError",
]
