"""
LM Studio Embedding провайдер.

Использует LM Studio API для генерации эмбеддингов.
LM Studio предоставляет OpenAI-совместимый API для embedding моделей.

API Endpoint:
    POST http://localhost:1234/v1/embeddings
    {
        "model": "text-embedding-model",
        "input": "текст",
        "encoding_format": "float"
    }

    Response:
    {
        "data": [{
            "embedding": [0.1, 0.2, ...],
            "index": 0
        }],
        "usage": {"total_tokens": 10}
    }

Документация:
- https://lmstudio.ai/docs

Пример использования:
    from src.embeddings.providers.lmstudio import LMStudioEmbeddingProvider

    provider = LMStudioEmbeddingProvider(
        base_url="http://localhost:1234",
        model="text-embedding-model",
        dimension=768
    )

    embedding = await provider.get_embedding("Привет, мир!")
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from .base import BaseEmbeddingProvider, EmbeddingProviderError

logger = logging.getLogger(__name__)


class LMStudioEmbeddingError(EmbeddingProviderError):
    """Ошибка LM Studio embedding провайдера."""
    pass


class LMStudioEmbeddingProvider(BaseEmbeddingProvider):
    """
    Провайдер для генерации эмбеддингов через LM Studio API.

    Поддерживает:
    - Retry-логику с экспоненциальной задержкой
    - Проверку доступности API
    - OpenAI-совместимый формат
    """

    def __init__(
        self,
        base_url: str = "http://localhost:1234",
        model: str = "text-embedding-model",
        dimension: int = 768,
        api_key: Optional[str] = None,
        max_retries: int = 3,
        timeout: int = 30,
        normalize: bool = False
    ):
        """
        Инициализация провайдера.

        Args:
            base_url: URL LM Studio API.
            model: Модель для эмбеддингов.
            dimension: Размерность вектора.
            api_key: API ключ (опционально, обычно не требуется).
            max_retries: Максимальное количество попыток.
            timeout: Таймаут запроса в секундах.
            normalize: Нормализовать вектор (L2 норма).
        """
        super().__init__(
            base_url=base_url,
            model=model,
            dimension=dimension,
            api_key=api_key,
            max_retries=max_retries,
            timeout=timeout
        )

        self.normalize = normalize
        self.base_delay = 1.0
        self._client: Optional[httpx.AsyncClient] = None

        logger.info(
            f"LMStudioEmbeddingProvider инициализирован: "
            f"URL={base_url}, модель={model}, dim={dimension}"
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """Получить или создать HTTP клиент."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=10.0)
            )
        return self._client

    async def close(self) -> None:
        """Закрыть HTTP клиент."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def get_embedding(self, text: str) -> List[float]:
        """
        Получить эмбеддинг текста с retry-логикой.

        Args:
            text: Текст для векторизации.

        Returns:
            Вектор эмбеддинга.

        Raises:
            LMStudioEmbeddingError: При неудаче после всех попыток.
        """
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                logger.debug(
                    f"Попытка {attempt + 1}/{self.max_retries}: генерация эмбеддинга"
                )

                embedding = await self._generate_embedding(text)

                # Нормализация если требуется
                if self.normalize:
                    embedding = self._normalize_vector(embedding)

                # Проверка размерности
                if len(embedding) != self.dimension:
                    logger.warning(
                        f"Неверная размерность: {len(embedding)} "
                        f"(ожидалось {self.dimension})"
                    )

                logger.debug(
                    f"Эмбеддинг получен успешно, размерность: {len(embedding)}"
                )
                return embedding

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    f"Попытка {attempt + 1} неудачна: HTTP ошибка {e.response.status_code}"
                )

                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    logger.info(f"Повтор через {delay}с...")
                    await asyncio.sleep(delay)
                continue

            except httpx.RequestError as e:
                last_error = e
                logger.warning(
                    f"Попытка {attempt + 1} неудачна: {type(e).__name__}: {e}"
                )

                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    logger.info(f"Повтор через {delay}с...")
                    await asyncio.sleep(delay)
                continue

            except Exception as e:
                logger.error(f"Критическая ошибка: {type(e).__name__}: {e}")
                raise LMStudioEmbeddingError(f"Ошибка генерации эмбеддинга: {e}")

        # Все попытки исчерпаны
        raise LMStudioEmbeddingError(
            f"Не удалось получить эмбеддинг после {self.max_retries} попыток: {last_error}"
        )

    async def _generate_embedding(self, text: str) -> List[float]:
        """
        Один запрос к LM Studio API для получения эмбеддинга.

        Args:
            text: Текст для векторизации.

        Returns:
            Вектор эмбеддинга.

        Raises:
            httpx.HTTPStatusError: При ошибке HTTP статуса.
            httpx.RequestError: При ошибке запроса.
            LMStudioEmbeddingError: При ошибке в ответе API.
        """
        client = await self._get_client()

        # Формируем URL с /v1 если нет
        api_base = self.base_url
        if "/v1" not in api_base:
            api_base = f"{api_base}/v1"

        url = f"{api_base}/embeddings"

        # Формирование payload
        payload: Dict[str, Any] = {
            "model": self.model,
            "input": text,
            "encoding_format": "float"
        }

        # Заголовки
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        logger.debug(f"Запрос к LM Studio: {url}, модель: {self.model}")

        async with client.stream("POST", url, json=payload, headers=headers) as response:
            if response.status_code == 404:
                raise LMStudioEmbeddingError(
                    f"Модель '{self.model}' не найдена в LM Studio"
                )

            if response.status_code != 200:
                response_text = await response.aread()
                request = httpx.Request("POST", url, headers=headers, json=payload)
                raise httpx.HTTPStatusError(
                    f"HTTP {response.status_code}: {response_text.decode()[:200]}",
                    request=request,
                    response=response
                )

            data = response.json()

            # Извлечение эмбеддинга из ответа
            try:
                embedding_data = data.get("data", [])

                if not embedding_data:
                    raise LMStudioEmbeddingError(
                        f"Пустой эмбеддинг в ответе LM Studio: {data}"
                    )

                embedding = embedding_data[0].get("embedding", [])

                if not embedding:
                    raise LMStudioEmbeddingError(
                        "Пустой вектор в ответе LM Studio"
                    )

                return [float(x) for x in embedding]

            except (KeyError, IndexError) as e:
                logger.error(f"Некорректный формат ответа от LM Studio: {data}")
                raise LMStudioEmbeddingError(
                    f"Некорректный формат ответа LM Studio: {e}"
                )

    def _normalize_vector(self, vector: List[float]) -> List[float]:
        """
        L2 нормализация вектора.

        Args:
            vector: Вектор для нормализации.

        Returns:
            Нормализованный вектор.
        """
        import math

        magnitude = math.sqrt(sum(x * x for x in vector))

        if magnitude == 0:
            return vector

        return [x / magnitude for x in vector]

    async def check_health(self) -> bool:
        """
        Проверить доступность LM Studio API.

        Returns:
            True если API доступен, False иначе.
        """
        try:
            client = await self._get_client()

            # Проверка через запрос к /v1/models
            api_base = self.base_url
            if "/v1" not in api_base:
                api_base = f"{api_base}/v1"

            url = f"{api_base}/models"

            async with client.stream("GET", url) as response:
                await response.aread()

                if response.status_code == 200:
                    logger.info(f"LM Studio API доступно ({self.base_url})")
                    return True
                else:
                    logger.warning(
                        f"LM Studio API вернул статус {response.status_code}"
                    )
                    return False

        except httpx.RequestError as e:
            logger.warning(f"LM Studio API недоступно: {type(e).__name__}: {e}")
            return False

        except Exception as e:
            logger.warning(f"Ошибка проверки LM Studio API: {type(e).__name__}: {e}")
            return False

    async def get_models(self) -> List[str]:
        """
        Получить список доступных моделей.

        Returns:
            Список названий моделей.
        """
        try:
            client = await self._get_client()

            # Проверка через запрос к /v1/models
            api_base = self.base_url
            if "/v1" not in api_base:
                api_base = f"{api_base}/v1"

            url = f"{api_base}/models"

            async with client.stream("GET", url) as response:
                await response.aread()

                if response.status_code != 200:
                    logger.warning(f"LM Studio вернул статус {response.status_code}")
                    return []

                data = response.json()
                models = data.get("data", [])

                # Извлекаем ID моделей
                result = [model.get("id", "") for model in models if model.get("id")]

                logger.info(f"Получено {len(result)} моделей от LM Studio")
                return result

        except Exception as e:
            logger.error(f"Ошибка получения списка моделей LM Studio: {e}")
            return []

    def __repr__(self) -> str:
        return (
            f"LMStudioEmbeddingProvider("
            f"model={self.model!r}, "
            f"dimension={self.dimension}, "
            f"base_url={self.base_url!r})"
        )


__all__ = [
    "LMStudioEmbeddingProvider",
    "LMStudioEmbeddingError",
]
