"""
Google Gemini Embedding провайдер.

Использует Google Gemini API для генерации эмбеддингов.
Поддерживаемые модели:
- text-embedding-004 (768 dim)
- gemini-embedding-exp-03-07 (экспериментальная)

API Endpoint:
    POST https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent
    {
        "content": {
            "parts": [{"text": "текст"}]
        },
        "outputDimensionality": 768
    }

    Response:
    {
        "embedding": {
            "values": [0.1, 0.2, ...]
        }
    }

Документация:
- https://ai.google.dev/gemini-api/docs/embeddings
- https://ai.google.dev/gemini-api/docs/models/gemini

Пример использования:
    from src.embeddings.providers.gemini import GeminiEmbeddingProvider

    provider = GeminiEmbeddingProvider(
        api_key="your-api-key",
        model="text-embedding-004",
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


class GeminiEmbeddingError(EmbeddingProviderError):
    """Ошибка Gemini embedding провайдера."""
    pass


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    """
    Провайдер для генерации эмбеддингов через Google Gemini API.

    Поддерживает:
    - Retry-логику с экспоненциальной задержкой
    - Проверку доступности API
    - Нормализацию векторов (опционально)
    - Пакетную обработку
    """

    # Базовый URL API
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    # Модели для эмбеддингов
    EMBEDDING_MODELS = {
        "text-embedding-004": 768,
        "gemini-embedding-exp-03-07": 3072,
    }

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-004",
        dimension: int = 768,
        base_url: Optional[str] = None,
        max_retries: int = 3,
        timeout: int = 30,
        normalize: bool = False
    ):
        """
        Инициализация провайдера.

        Args:
            api_key: API ключ Google Gemini.
            model: Модель для эмбеддингов.
            dimension: Размерность вектора.
            base_url: Базовый URL API (опционально).
            max_retries: Максимальное количество попыток.
            timeout: Таймаут запроса в секундах.
            normalize: Нормализовать вектор (L2 норма).
        """
        # Определяем dimension из модели если не указан
        if model in self.EMBEDDING_MODELS and dimension == 768:
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
        self.base_delay = 2.0
        self._client: Optional[httpx.AsyncClient] = None

        logger.info(
            f"GeminiEmbeddingProvider инициализирован: "
            f"модель={model}, dim={dimension}, normalize={normalize}"
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
            GeminiEmbeddingError: При неудаче после всех попыток.
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

                # Не ретраим ошибки аутентификации и авторизации
                if e.response.status_code in [401, 403]:
                    raise GeminiEmbeddingError(
                        f"Ошибка аутентификации Gemini API: {e.response.status_code}"
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
                raise GeminiEmbeddingError(f"Ошибка генерации эмбеддинга: {e}")

        # Все попытки исчерпаны
        raise GeminiEmbeddingError(
            f"Не удалось получить эмбеддинг после {self.max_retries} попыток: {last_error}"
        )

    async def _generate_embedding(self, text: str) -> List[float]:
        """
        Один запрос к Gemini API для получения эмбеддинга.

        Args:
            text: Текст для векторизации.

        Returns:
            Вектор эмбеддинга.

        Raises:
            httpx.HTTPStatusError: При ошибке HTTP статуса.
            httpx.RequestError: При ошибке запроса.
            GeminiEmbeddingError: При ошибке в ответе API.
        """
        client = await self._get_client()

        # Формирование URL
        url = f"{self.base_url}/models/{self.model}:embedContent"

        # Добавляем API ключ как query параметр
        params = {"key": self.api_key}

        # Формирование payload
        payload: Dict[str, Any] = {
            "content": {
                "parts": [{"text": text}]
            },
            "outputDimensionality": self.dimension
        }

        # Task type для оптимизации (документация Gemini)
        # RETRIEVAL_DOCUMENT - для индексации документов
        # RETRIEVAL_QUERY - для поисковых запросов
        # SEMANTIC_SIMILARITY - для сравнения текстов
        payload["taskType"] = "RETRIEVAL_DOCUMENT"

        logger.debug(f"Запрос к Gemini: {url}, модель: {self.model}")

        async with client.stream("POST", url, json=payload, params=params) as response:
            if response.status_code == 401:
                raise GeminiEmbeddingError("Неверный API ключ Gemini")

            if response.status_code == 403:
                raise GeminiEmbeddingError(
                    "Доступ запрещён. Проверьте квоты API и права доступа."
                )

            if response.status_code == 429:
                raise GeminiEmbeddingError(
                    "Превышен лимит запросов (rate limit). "
                    "Free tier: 15 RPM, 1M TPM"
                )

            if response.status_code != 200:
                response_text = await response.aread()
                request = httpx.Request("POST", url, params=params, json=payload)
                raise httpx.HTTPStatusError(
                    f"HTTP {response.status_code}: {response_text.decode()[:200]}",
                    request=request,
                    response=response
                )

            data = response.json()

            # Извлечение эмбеддинга из ответа
            try:
                embedding_obj = data.get("embedding", {})
                embedding = embedding_obj.get("values", [])

                if not embedding:
                    raise GeminiEmbeddingError(
                        f"Пустой эмбеддинг в ответе Gemini: {data}"
                    )

                return [float(x) for x in embedding]

            except (KeyError, IndexError) as e:
                logger.error(f"Некорректный формат ответа от Gemini: {data}")
                raise GeminiEmbeddingError(
                    f"Некорректный формат ответа Gemini: {e}"
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
        Проверить доступность Gemini API.

        Returns:
            True если API доступен, False иначе.
        """
        try:
            client = await self._get_client()

            # Проверка через запрос к списку моделей
            url = f"{self.base_url}/models"
            params = {"key": self.api_key}

            async with client.stream("GET", url, params=params) as response:
                await response.aread()

                if response.status_code == 200:
                    logger.info("Gemini API доступно")
                    return True
                elif response.status_code == 401:
                    logger.error("Gemini API: неверный API ключ")
                    return False
                elif response.status_code == 403:
                    logger.error("Gemini API: доступ запрещён")
                    return False
                else:
                    logger.warning(f"Gemini API вернул статус {response.status_code}")
                    return False

        except httpx.RequestError as e:
            logger.warning(f"Gemini API недоступно: {type(e).__name__}: {e}")
            return False

        except Exception as e:
            logger.warning(f"Ошибка проверки Gemini API: {type(e).__name__}: {e}")
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
            params = {"key": self.api_key}

            async with client.stream("GET", url, params=params) as response:
                await response.aread()

                if response.status_code != 200:
                    logger.warning(f"Gemini вернул статус {response.status_code}")
                    return []

                data = response.json()
                models = data.get("models", [])

                # Фильтруем только embedding модели
                result = []
                for model in models:
                    name = model.get("name", "")
                    # API возвращает имя в формате "models/text-embedding-004"
                    if name.startswith("models/"):
                        name = name[7:]

                    # Проверяем поддержку embedContent
                    methods = model.get("supportedGenerationMethods", [])
                    if "embedContent" in methods or "embeddings" in name.lower():
                        result.append(name)

                logger.info(f"Получено {len(result)} embedding моделей от Gemini")
                return result

        except Exception as e:
            logger.error(f"Ошибка получения списка моделей Gemini: {e}")
            return []

    def __repr__(self) -> str:
        return (
            f"GeminiEmbeddingProvider("
            f"model={self.model!r}, "
            f"dimension={self.dimension}, "
            f"normalize={self.normalize})"
        )


__all__ = [
    "GeminiEmbeddingProvider",
    "GeminiEmbeddingError",
]
