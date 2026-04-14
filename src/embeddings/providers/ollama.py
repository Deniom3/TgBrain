"""
Ollama Embedding провайдер.

Использует Ollama API для генерации эмбеддингов.
Поддерживает модели:
- nomic-embed-text (768 dim)
- mxbai-embed-large (1024 dim)
- all-minilm (384 dim)
- другие embedding модели Ollama

API Endpoint:
    POST /api/embeddings
    {
        "model": "nomic-embed-text",
        "prompt": "текст"
    }

    Response:
    {
        "embedding": [0.1, 0.2, ...]
    }

Пример использования:
    from src.embeddings.providers.ollama import OllamaEmbeddingProvider

    provider = OllamaEmbeddingProvider(
        base_url="http://localhost:11434",
        model="nomic-embed-text",
        dimension=768
    )

    embedding = await provider.get_embedding("Привет, мир!")
"""

import asyncio
import logging
from typing import List, Optional

import aiohttp

from .base import BaseEmbeddingProvider, EmbeddingProviderError

logger = logging.getLogger(__name__)


class OllamaEmbeddingError(EmbeddingProviderError):
    """Ошибка Ollama embedding провайдера."""
    pass


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    """
    Провайдер для генерации эмбеддингов через Ollama API.

    Поддерживает:
    - Retry-логику с экспоненциальной задержкой
    - Проверку доступности сервиса
    - Несколько экземпляров на разных серверах
    - Контекстный менеджер
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "nomic-embed-text",
        dimension: int = 768,
        api_key: Optional[str] = None,
        max_retries: int = 3,
        timeout: int = 30,
        instance_id: Optional[str] = None
    ):
        """
        Инициализация провайдера.

        Args:
            base_url: URL Ollama API.
            model: Модель для эмбеддингов.
            dimension: Размерность вектора.
            api_key: API ключ (не требуется для локального Ollama).
            max_retries: Максимальное количество попыток.
            timeout: Таймаут запроса в секундах.
            instance_id: Уникальный ID экземпляра (для различия серверов).
        """
        super().__init__(
            base_url=base_url,
            model=model,
            dimension=dimension,
            api_key=api_key,
            max_retries=max_retries,
            timeout=timeout
        )

        self.instance_id = instance_id or f"ollama_{id(self)}"
        self.base_delay = 1.0
        self._session: Optional[aiohttp.ClientSession] = None

        logger.info(
            f"OllamaEmbeddingProvider инициализирован: "
            f"URL={base_url}, модель={model}, dim={dimension}, id={instance_id}"
        )

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получить или создать HTTP сессию."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        return self._session

    async def close(self) -> None:
        """Закрыть HTTP сессию."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def get_embedding(self, text: str) -> List[float]:
        """
        Получить эмбеддинг текста с retry-логикой.

        Args:
            text: Текст для векторизации.

        Returns:
            Вектор эмбеддинга.

        Raises:
            OllamaEmbeddingError: При неудаче после всех попыток.
        """
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                logger.debug(
                    f"[{self.instance_id}] Попытка {attempt + 1}/{self.max_retries}: "
                    f"генерация эмбеддинга"
                )

                embedding = await self._generate_embedding(text)

                # Проверка размерности
                if len(embedding) != self.dimension:
                    logger.warning(
                        f"[{self.instance_id}] Неверная размерность: {len(embedding)} "
                        f"(ожидалось {self.dimension})"
                    )

                logger.debug(
                    f"[{self.instance_id}] Эмбеддинг получен успешно, "
                    f"размерность: {len(embedding)}"
                )
                return embedding

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_error = e
                logger.warning(
                    f"[{self.instance_id}] Попытка {attempt + 1} неудачна: "
                    f"{type(e).__name__}: {e}"
                )

                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)  # 1s, 2s, 4s
                    logger.info(
                        f"[{self.instance_id}] Повтор через {delay}с..."
                    )
                    await asyncio.sleep(delay)
                continue

            except Exception as e:
                # Неретраемые ошибки (модель не найдена, неверный ответ)
                logger.error(
                    f"[{self.instance_id}] Критическая ошибка: "
                    f"{type(e).__name__}: {e}"
                )
                raise OllamaEmbeddingError(f"Ошибка генерации эмбеддинга: {e}")

        # Все попытки исчерпаны
        raise OllamaEmbeddingError(
            f"[{self.instance_id}] Не удалось получить эмбеддинг после "
            f"{self.max_retries} попыток: {last_error}"
        )

    async def _generate_embedding(self, text: str) -> List[float]:
        """
        Один запрос к Ollama API для получения эмбеддинга.

        Args:
            text: Текст для векторизации.

        Returns:
            Вектор эмбеддинга.

        Raises:
            aiohttp.ClientError: При ошибке HTTP.
            OllamaEmbeddingError: При ошибке в ответе API.
        """
        session = await self._get_session()
        url = f"{self.base_url}/api/embeddings"

        payload = {
            "model": self.model,
            "prompt": text
        }

        logger.debug(
            f"[{self.instance_id}] Запрос к Ollama: {url}, модель: {self.model}"
        )

        async with session.post(url, json=payload) as response:
            if response.status == 404:
                raise OllamaEmbeddingError(
                    f"Модель '{self.model}' не найдена на сервере {self.base_url}"
                )

            if response.status != 200:
                response_text = await response.text()
                raise aiohttp.ClientError(
                    f"HTTP {response.status}: {response_text}"
                )

            data = await response.json()

            if "embedding" not in data:
                raise OllamaEmbeddingError(
                    f"Неверный формат ответа Ollama: {data.keys()}"
                )

            embedding = data["embedding"]

            if not isinstance(embedding, list):
                raise OllamaEmbeddingError(
                    f"Эмбеддинг не является списком: {type(embedding)}"
                )

            # Преобразование в float
            return [float(x) for x in embedding]

    async def check_health(self) -> bool:
        """
        Проверить доступность Ollama API.

        Returns:
            True если сервис доступен, False иначе.
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}/api/tags"

            async with session.get(url) as response:
                # Читаем ответ чтобы освободить соединение
                await response.read()

                if response.status == 200:
                    logger.info(
                        f"[{self.instance_id}] Ollama API доступен ({self.base_url})"
                    )
                    return True
                else:
                    logger.warning(
                        f"[{self.instance_id}] Ollama API вернул статус {response.status}"
                    )
                    return False

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.warning(
                f"[{self.instance_id}] Ollama API недоступен: "
                f"{type(e).__name__}: {e}"
            )
            return False

        except Exception as e:
            logger.error(
                f"[{self.instance_id}] Ошибка проверки здоровья Ollama: {e}"
            )
            return False

    async def get_models(self) -> List[str]:
        """
        Получить список доступных моделей.

        Returns:
            Список названий моделей.
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}/api/tags"

            async with session.get(url) as response:
                if response.status != 200:
                    return []

                # Читаем ответ перед парсингом JSON
                await response.read()
                data = await response.json()
                models = data.get("models", [])
                return [m.get("name", "") for m in models if m.get("name")]

        except Exception as e:
            logger.error(
                f"[{self.instance_id}] Ошибка получения списка моделей: {e}"
            )
            return []

    async def get_embedding_dimension(self, force: bool = False) -> int:
        """
        Получить размерность эмбеддинга для текущей модели.
        
        Args:
            force: Принудительно запросить у сервера (не использовать кэш).
        
        Returns:
            Размерность эмбеддинга или 0 если не удалось получить.
        """
        # Если размерность уже установлена и force=False, возвращаем её
        if not force and self.dimension and self.dimension > 0:
            logger.debug(
                f"[{self.instance_id}] Используем кэшированную размерность: {self.dimension}"
            )
            return self.dimension
        
        try:
            session = await self._get_session()
            
            # Шаг 1: Получаем информацию о модели через /api/show
            url = f"{self.base_url}/api/show"
            payload = {"name": self.model}
            
            logger.info(
                f"[{self.instance_id}] Получение размерности для модели {self.model}"
            )
            
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    logger.warning(
                        f"[{self.instance_id}] Не удалось получить info о модели: "
                        f"HTTP {response.status}"
                    )
                    # Пробуем через генерацию эмбеддинга
                    return await self._get_dimension_from_embedding()
                
                data = await response.json()
                model_info = data.get("model_info", {})
                
                # Ищем поле embedding_length (формат: <architecture>.embedding_length)
                for key, value in model_info.items():
                    if key.endswith(".embedding_length"):
                        dimension = int(value)
                        logger.info(
                            f"[{self.instance_id}] Размерность модели {self.model}: "
                            f"{dimension} (из {key})"
                        )
                        # Сохраняем в self.dimension для кэширования
                        self.dimension = dimension
                        return dimension
                
                # Если не найдено в model_info, пробуем сгенерировать эмбеддинг
                logger.info(
                    f"[{self.instance_id}] embedding_length не найдена в model_info, "
                    f"пробуем генерацию..."
                )
                return await self._get_dimension_from_embedding()
                
        except Exception as e:
            logger.error(
                f"[{self.instance_id}] Ошибка получения размерности: {e}"
            )
            # Пробуем через генерацию как fallback
            try:
                return await self._get_dimension_from_embedding()
            except Exception:
                return 0

    async def _get_dimension_from_embedding(self) -> int:
        """
        Получить размерность через генерацию эмбеддинга.
        
        Returns:
            Размерность вектора или 0 при ошибке.
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}/api/embeddings"
            payload = {"model": self.model, "prompt": "test"}
            
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    embedding = data.get("embedding", [])
                    dimension = len(embedding)
                    logger.info(
                        f"[{self.instance_id}] Размерность модели {self.model}: "
                        f"{dimension} (из генерации эмбеддинга)"
                    )
                    return dimension
                else:
                    logger.warning(
                        f"[{self.instance_id}] Не удалось получить эмбеддинг: "
                        f"HTTP {response.status}"
                    )
                    return 0
                    
        except Exception as e:
            logger.error(
                f"[{self.instance_id}] Ошибка генерации для определения размерности: {e}"
            )
            return 0

    def __repr__(self) -> str:
        return (
            f"OllamaEmbeddingProvider("
            f"instance_id={self.instance_id!r}, "
            f"model={self.model!r}, "
            f"dimension={self.dimension}, "
            f"base_url={self.base_url!r})"
        )


__all__ = [
    "OllamaEmbeddingProvider",
    "OllamaEmbeddingError",
]
