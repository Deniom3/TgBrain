"""
OpenRouter Embedding провайдер.

Использует OpenRouter API для генерации эмбеддингов через OpenAI-совместимые модели.
Поддерживаемые модели (примеры):
- openai/text-embedding-3-small (1536 dim)
- openai/text-embedding-3-large (3072 dim)
- openai/text-embedding-ada-002 (1536 dim)
- другие embedding модели доступные через OpenRouter

API Endpoint:
    POST https://openrouter.ai/api/v1/embeddings
    {
        "model": "openai/text-embedding-3-small",
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
- https://openrouter.ai/docs
- https://openrouter.ai/models

Пример использования:
    from src.embeddings.providers.openrouter import OpenRouterEmbeddingProvider

    provider = OpenRouterEmbeddingProvider(
        api_key="your-api-key",
        model="openai/text-embedding-3-small",
        dimension=1536
    )

    embedding = await provider.get_embedding("Привет, мир!")
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from .base import BaseEmbeddingProvider, EmbeddingProviderError

logger = logging.getLogger(__name__)


class OpenRouterEmbeddingError(EmbeddingProviderError):
    """Ошибка OpenRouter embedding провайдера."""
    pass


class OpenRouterEmbeddingProvider(BaseEmbeddingProvider):
    """
    Провайдер для генерации эмбеддингов через OpenRouter API.

    Поддерживает:
    - Retry-логику с экспоненциальной задержкой
    - Проверку доступности API
    - Пакетную обработку (batch)
    - Нормализацию векторов (опционально)
    """

    # Базовый URL API
    BASE_URL = "https://openrouter.ai/api/v1"

    # Популярные embedding модели
    EMBEDDING_MODELS = {
        "openai/text-embedding-3-small": 1536,
        "openai/text-embedding-3-large": 3072,
        "openai/text-embedding-ada-002": 1536,
    }

    def __init__(
        self,
        api_key: str,
        model: str = "openai/text-embedding-3-small",
        dimension: int = 1536,
        base_url: Optional[str] = None,
        max_retries: int = 3,
        timeout: int = 30,
        normalize: bool = False,
        batch_size: int = 20
    ):
        """
        Инициализация провайдера.

        Args:
            api_key: API ключ OpenRouter.
            model: Модель для эмбеддингов.
            dimension: Размерность вектора.
            base_url: Базовый URL API (опционально).
            max_retries: Максимальное количество попыток.
            timeout: Таймаут запроса в секундах.
            normalize: Нормализовать вектор (L2 норма).
            batch_size: Размер пакета для пакетной обработки.
        """
        # Определяем dimension из модели если не указан
        if model in self.EMBEDDING_MODELS and dimension == 1536:
            dimension = self.EMBEDDING_MODELS[model]

        super().__init__(
            base_url=base_url or self.BASE_URL,
            model=model,
            dimension=dimension,
            api_key=api_key,
            max_retries=max_retries,
            timeout=timeout
        )

        self.normalize = normalize
        self.batch_size = batch_size
        self.base_delay = 3.0
        self._client: Optional[httpx.AsyncClient] = None

        # Заголовки для API
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            # Заголовки для отслеживания использования
            "HTTP-Referer": "https://github.com/TgBrain",
            "X-Title": "TgBrain",
        }

        logger.info(
            f"OpenRouterEmbeddingProvider инициализирован: "
            f"модель={model}, dim={dimension}, batch_size={batch_size}"
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
            OpenRouterEmbeddingError: При неудаче после всех попыток.
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

                # Не ретраим ошибки аутентификации
                if e.response.status_code in [401, 402]:
                    if e.response.status_code == 401:
                        raise OpenRouterEmbeddingError(
                            "Неверный API ключ OpenRouter"
                        )
                    else:
                        raise OpenRouterEmbeddingError(
                            "Недостаточно средств на балансе OpenRouter"
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
                raise OpenRouterEmbeddingError(f"Ошибка генерации эмбеддинга: {e}")

        # Все попытки исчерпаны
        raise OpenRouterEmbeddingError(
            f"Не удалось получить эмбеддинг после {self.max_retries} попыток: {last_error}"
        )

    async def _generate_embedding(self, text: str) -> List[float]:
        """
        Один запрос к OpenRouter API для получения эмбеддинга.

        Args:
            text: Текст для векторизации.

        Returns:
            Вектор эмбеддинга.

        Raises:
            httpx.HTTPStatusError: При ошибке HTTP статуса.
            httpx.RequestError: При ошибке запроса.
            OpenRouterEmbeddingError: При ошибке в ответе API.
        """
        client = await self._get_client()

        url = f"{self.base_url}/embeddings"

        # Формирование payload
        payload: Dict[str, Any] = {
            "model": self.model,
            "input": text,
            "encoding_format": "float"
        }

        logger.debug(f"Запрос к OpenRouter: {url}, модель: {self.model}")

        response = await client.post(url, json=payload, headers=self.headers)
        try:
            if response.status_code == 401:
                raise OpenRouterEmbeddingError("Неверный API ключ OpenRouter")

            if response.status_code == 402:
                raise OpenRouterEmbeddingError(
                    "Недостаточно средств на балансе OpenRouter"
                )

            if response.status_code == 429:
                raise OpenRouterEmbeddingError(
                    "Превышен лимит запросов (rate limit)"
                )

            if response.status_code != 200:
                response_text = await response.aread()
                raise httpx.HTTPStatusError(
                    f"HTTP {response.status_code}: {response_text.decode()[:200]}",
                    request=response.request,
                    response=response
                )

            data = response.json()

            # OpenRouter может вернуть ошибку в формате {"error": {...}}
            if "error" in data:
                error_info = data["error"]
                error_msg = error_info.get("message", "Неизвестная ошибка")
                error_code = error_info.get("code", "unknown")
                logger.error(f"OpenRouter ошибка [{error_code}]: {error_msg}")
                raise OpenRouterEmbeddingError(
                    f"OpenRouter API error [{error_code}]: {error_msg}"
                )

            # Извлечение эмбеддинга из ответа
            try:
                embedding_data = data.get("data", [])

                if not embedding_data:
                    raise OpenRouterEmbeddingError(
                        f"Пустой эмбеддинг в ответе OpenRouter: {data}"
                    )

                embedding = embedding_data[0].get("embedding", [])

                if not embedding:
                    raise OpenRouterEmbeddingError(
                        "Пустой вектор в ответе OpenRouter"
                    )

                return [float(x) for x in embedding]

            except (KeyError, IndexError) as e:
                logger.error(f"Некорректный формат ответа от OpenRouter: {data}")
                raise OpenRouterEmbeddingError(
                    f"Некорректный формат ответа OpenRouter: {e}"
                )
        finally:
            await response.aclose()

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
        Проверить доступность OpenRouter API.

        Returns:
            True если API доступен, False иначе.
        """
        try:
            client = await self._get_client()

            # Проверка через запрос к списку моделей
            url = f"{self.base_url}/models"

            async with client.stream("GET", url, headers=self.headers) as response:
                await response.aread()

                if response.status_code == 200:
                    logger.info("OpenRouter API доступно")
                    return True
                elif response.status_code == 401:
                    logger.error("OpenRouter API: неверный API ключ")
                    return False
                else:
                    logger.warning(
                        f"OpenRouter API вернул статус {response.status_code}"
                    )
                    return False

        except httpx.RequestError as e:
            logger.warning(f"OpenRouter API недоступно: {type(e).__name__}: {e}")
            return False

        except Exception as e:
            logger.warning(f"Ошибка проверки OpenRouter API: {type(e).__name__}: {e}")
            return False

    async def get_models(self) -> List[str]:
        """
        Получить список доступных моделей для эмбеддингов.

        Returns:
            Список названий моделей.
        """
        try:
            client = await self._get_client()
            url = f"{self.base_url}/models"

            async with client.stream("GET", url, headers=self.headers) as response:
                await response.aread()

                if response.status_code != 200:
                    logger.warning(f"OpenRouter вернул статус {response.status_code}")
                    return []

                data = response.json()
                models = data.get("data", [])

                # Фильтруем только embedding модели
                result = []
                for model in models:
                    model_id = model.get("id", "")
                    name = model.get("name", model_id)

                    # Проверяем по названию на наличие "embedding"
                    if "embedding" in name.lower() or "embedding" in model_id.lower():
                        result.append(model_id)

                logger.info(
                    f"Получено {len(result)} embedding моделей от OpenRouter"
                )
                return result

        except Exception as e:
            logger.error(f"Ошибка получения списка моделей OpenRouter: {e}")
            return []

    async def get_embeddings_batch(
        self,
        texts: List[str],
        batch_size: Optional[int] = None
    ) -> List[List[float]]:
        """
        Получить эмбеддинги для нескольких текстов (пакетно).

        OpenRouter поддерживает пакетную обработку до 2048 текстов за раз.

        Args:
            texts: Список текстов для векторизации.
            batch_size: Размер пакета (переопределяет self.batch_size).

        Returns:
            Список векторов эмбеддингов.

        Raises:
            OpenRouterEmbeddingError: При ошибке генерации.
        """
        if not texts:
            return []

        batch_size = batch_size or self.batch_size
        results: List[List[float]] = []

        # Разбиение на пакеты
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = await self._generate_embeddings_batch(batch)
            results.extend(batch_embeddings)

        return results

    async def _generate_embeddings_batch(
        self,
        texts: List[str]
    ) -> List[List[float]]:
        """
        Один пакетный запрос к OpenRouter API.

        Args:
            texts: Список текстов (до 2048).

        Returns:
            Список векторов эмбеддингов.
        """
        client = await self._get_client()
        url = f"{self.base_url}/embeddings"

        payload: Dict[str, Any] = {
            "model": self.model,
            "input": texts,
            "encoding_format": "float"
        }

        logger.debug(
            f"Пакетный запрос к OpenRouter: {len(texts)} текстов, модель: {self.model}"
        )

        async with client.stream("POST", url, json=payload, headers=self.headers) as response:
            if response.status_code != 200:
                response_text = await response.aread()
                raise OpenRouterEmbeddingError(
                    f"HTTP {response.status_code}: {response_text.decode()[:200]}"
                )

            data = response.json()

            # Извлечение эмбеддингов из ответа
            try:
                embedding_data = data.get("data", [])

                # Сортируем по индексу для сохранения порядка
                embedding_data.sort(key=lambda x: x.get("index", 0))

                embeddings = []
                for item in embedding_data:
                    embedding = item.get("embedding", [])
                    if self.normalize:
                        embedding = self._normalize_vector(embedding)
                    embeddings.append([float(x) for x in embedding])

                return embeddings

            except Exception as e:
                logger.error(f"Некорректный формат ответа от OpenRouter: {data}")
                raise OpenRouterEmbeddingError(
                    f"Некорректный формат ответа OpenRouter: {e}"
                )

    def __repr__(self) -> str:
        return (
            f"OpenRouterEmbeddingProvider("
            f"model={self.model!r}, "
            f"dimension={self.dimension}, "
            f"batch_size={self.batch_size})"
        )


__all__ = [
    "OpenRouterEmbeddingProvider",
    "OpenRouterEmbeddingError",
]
