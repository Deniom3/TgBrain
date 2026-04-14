"""
Базовый класс для embedding провайдеров.

Определяет интерфейс для всех провайдеров эмбеддингов:
- Ollama
- Gemini
- OpenRouter (модели с embeddings)
- Другие OpenAI-совместимые API

Пример использования:
    from src.embeddings.providers.base import BaseEmbeddingProvider

    class MyEmbeddingProvider(BaseEmbeddingProvider):
        async def get_embedding(self, text: str) -> List[float]:
            # Реализация
            pass
"""

from abc import ABC, abstractmethod
from typing import List, Optional


class EmbeddingProviderError(Exception):
    """Базовое исключение для ошибок embedding провайдера."""
    pass


class BaseEmbeddingProvider(ABC):
    """
    Абстрактный базовый класс для embedding провайдеров.

    Все провайдеры должны реализовать:
    - get_embedding(): получение вектора эмбеддинга
    - check_health(): проверка доступности API
    - get_models(): получение списка моделей

    Поддерживает:
    - Асинхронные операции
    - Контекстный менеджер
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        dimension: int,
        api_key: Optional[str] = None,
        max_retries: int = 3,
        timeout: int = 30
    ):
        """
        Инициализация провайдера.

        Args:
            base_url: URL API провайдера.
            model: Название модели для эмбеддингов.
            dimension: Ожидаемая размерность вектора.
            api_key: API ключ (опционально).
            max_retries: Максимальное количество попыток.
            timeout: Таймаут запроса в секундах.
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.dimension = dimension
        self.api_key = api_key
        self.max_retries = max_retries
        self.timeout = timeout

    @abstractmethod
    async def get_embedding(self, text: str) -> List[float]:
        """
        Получить эмбеддинг текста.

        Args:
            text: Текст для векторизации.

        Returns:
            Вектор эмбеддинга (список float).

        Raises:
            EmbeddingProviderError: При ошибке генерации.
        """
        pass

    @abstractmethod
    async def check_health(self) -> bool:
        """
        Проверить доступность API провайдера.

        Returns:
            True если API доступен, False иначе.
        """
        pass

    @abstractmethod
    async def get_models(self) -> List[str]:
        """
        Получить список доступных моделей.

        Returns:
            Список названий моделей.
        """
        pass

    async def get_embedding_dimension(self) -> int:
        """
        Получить размерность эмбеддинга для текущей модели.
        
        По умолчанию возвращает значение из self.dimension.
        Переопределяется в провайдерах для авто-определения.
        
        Returns:
            Размерность эмбеддинга.
        """
        return self.dimension

    async def get_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 10
    ) -> List[List[float]]:
        """
        Получить эмбеддинги для нескольких текстов (пакетно).

        Args:
            texts: Список текстов для векторизации.
            batch_size: Размер пакета для параллельной обработки.

        Returns:
            Список векторов эмбеддингов.
        """
        import asyncio

        async def process_batch(batch: List[str]) -> List[List[float]]:
            return await asyncio.gather(*[self.get_embedding(text) for text in batch])

        # Разбиение на пакеты
        batches = [
            texts[i:i + batch_size]
            for i in range(0, len(texts), batch_size)
        ]

        # Обработка пакетов
        results = []
        for batch in batches:
            batch_results = await process_batch(batch)
            results.extend(batch_results)

        return results

    def validate_embedding(self, embedding: List[float]) -> bool:
        """
        Проверить корректность эмбеддинга.

        Args:
            embedding: Вектор для проверки.

        Returns:
            True если вектор корректен.
        """
        if not isinstance(embedding, list):
            return False

        if len(embedding) != self.dimension:
            return False

        # Проверка что все элементы - числа
        for val in embedding:
            if not isinstance(val, (int, float)):
                return False

        return True

    async def close(self) -> None:
        """
        Освободить ресурсы (соединения, клиенты).

        По умолчанию ничего не делает, переопределяется в подклассах.
        """
        pass

    async def __aenter__(self):
        """Контекстный менеджер: вход."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Контекстный менеджер: выход."""
        await self.close()

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"model={self.model!r}, "
            f"dimension={self.dimension}, "
            f"base_url={self.base_url!r})"
        )


__all__ = [
    "BaseEmbeddingProvider",
    "EmbeddingProviderError",
]
