"""
OpenRouter API провайдер для LLM.

Документация:
- https://openrouter.ai/docs
- https://openrouter.ai/models

API Endpoint:
    https://openrouter.ai/api/v1/chat/completions

Authentication:
    Заголовок: Authorization: Bearer YOUR_API_KEY

Особенности:
- Доступ к 300+ моделям через единый API
- Поддержка sequences (несколько вариантов ответа)
- Provider routing (выбор/исключение провайдеров)
- Специфичные заголовки для отслеживания использования
"""

import asyncio
import logging
from typing import Dict, List, Optional

import httpx

from src.config import Settings

logger = logging.getLogger(__name__)


class OpenRouterError(Exception):
    """Базовое исключение для ошибок OpenRouter API."""
    pass


class OpenRouterProvider:
    """
    Провайдер для OpenRouter API.
    
    Поддерживает:
    - Генерацию текста через 300+ моделей
    - Получение списка доступных моделей
    - Проверку здоровья API
    - Sequences (несколько вариантов ответа)
    - Provider routing
    - Retry-логику при временных ошибках
    """
    
    # Базовый URL API
    BASE_URL = "https://openrouter.ai/api/v1"
    
    # Популярные модели
    POPULAR_MODELS = [
        "auto",  # Автоматический выбор лучшей модели
        "anthropic/claude-3.5-sonnet",
        "meta-llama/llama-3.1-8b-instruct",
        "google/gemini-pro-1.5",
        "qwen/qwen-2.5-72b-instruct",
    ]
    
    def __init__(self, config: Settings):
        """
        Инициализация провайдера.

        Args:
            config: Настройки приложения.
        """
        self.api_key = config.llm_api_key
        self.model = config.llm_model_name or "auto"
        self.max_retries = 5
        self.base_delay = 3.0
        self.timeout = httpx.Timeout(120.0, connect=10.0)
        self.health_cache_ttl = 60  # Кэш health check на 60 секунд

        # Заголовки для API
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key or ''}",
            # Заголовки для отслеживания использования
            "HTTP-Referer": "https://github.com/TgBrain",
            "X-Title": "TgBrain",
        }

        self._client: Optional[httpx.AsyncClient] = None
        self._health_cache: Dict = {"status": None, "time": 0}
        self._health_lock: asyncio.Lock = asyncio.Lock()

        logger.info(f"OpenRouterProvider инициализирован (модель: {self.model})")
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Получить или создать HTTP клиент."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client
    
    async def close(self) -> None:
        """Закрыть HTTP клиент."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        sequences: Optional[int] = None,
        provider: Optional[Dict] = None
    ) -> str:
        """
        Генерация ответа от OpenRouter с retry-логикой.
        
        Args:
            prompt: Пользовательский запрос.
            system_prompt: Системная инструкция (опционально).
            temperature: Температура генерации (0.0-2.0).
            max_tokens: Максимальное количество токенов.
            sequences: Количество вариантов ответа (OpenRouter feature).
            provider: Настройки роутинга провайдера (OpenRouter feature).
                Пример: {"allow": ["Anthropic"], "ignore": ["Together"]}
        
        Returns:
            Текст ответа от модели.
        
        Raises:
            OpenRouterError: После неудачных попыток запроса.
        """
        # Формирование сообщений
        messages = []
        
        # Добавляем system prompt если указан
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        # Попытки запроса с retry-логикой
        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return await self._call_api(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    sequences=sequences,
                    provider=provider
                )
            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    f"Попытка {attempt}/{self.max_retries} не удалась: "
                    f"HTTP ошибка {e.response.status_code}"
                )
            except httpx.RequestError as e:
                last_error = e
                logger.warning(
                    f"Попытка {attempt}/{self.max_retries} не удалась: "
                    f"Ошибка запроса {type(e).__name__}"
                )
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Попытка {attempt}/{self.max_retries} не удалась: "
                    f"{type(e).__name__}: {e}"
                )
            
            # Задержка перед следующей попыткой
            if attempt < self.max_retries:
                await asyncio.sleep(self.base_delay)
        
        # Все попытки исчерпаны
        error_msg = f"Не удалось получить ответ от OpenRouter после {self.max_retries} попыток"
        logger.error(error_msg)
        if last_error:
            raise OpenRouterError(f"{error_msg}: {last_error}")
        raise OpenRouterError(error_msg)
    
    async def _call_api(
        self,
        messages: List[Dict],
        temperature: float,
        max_tokens: int,
        sequences: Optional[int] = None,
        provider: Optional[Dict] = None
    ) -> str:
        """
        Один запрос к OpenRouter API.
        
        Args:
            messages: Список сообщений в формате OpenAI.
            temperature: Температура генерации.
            max_tokens: Максимальное количество токенов.
            sequences: Количество вариантов ответа.
            provider: Настройки роутинга провайдера.
        
        Returns:
            Текст ответа от модели.
        
        Raises:
            httpx.HTTPStatusError: При ошибке HTTP статуса.
            httpx.RequestError: При ошибке запроса.
            OpenRouterError: При ошибке в ответе API.
        """
        client = await self._get_client()
        
        url = f"{self.BASE_URL}/chat/completions"
        
        # Формирование payload запроса
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        # OpenRouter специфичные параметры
        if sequences and sequences > 1:
            payload["num_sequences"] = sequences
        
        if provider:
            payload["provider"] = provider
        
        logger.debug(f"Запрос к OpenRouter: {url}, модель: {self.model}")
        
        async with client.stream("POST", url, json=payload, headers=self.headers) as response:
            # Читаем ответ перед парсингом
            await response.aread()
            
            if response.status_code == 401:
                raise OpenRouterError("Неверный API ключ OpenRouter")
            
            if response.status_code == 402:
                raise OpenRouterError("Недостаточно средств на балансе OpenRouter")
            
            if response.status_code == 429:
                raise OpenRouterError("Превышен лимит запросов (rate limit)")
            
            if response.status_code != 200:
                request = httpx.Request("POST", url, json=payload, headers=self.headers)
                raise httpx.HTTPStatusError(
                    f"HTTP {response.status_code}: {response.text[:200]}",
                    request=request,
                    response=response
                )
            
            data = response.json()
            
            # OpenRouter может вернуть ошибку в формате {"error": {"message": "...", "code": "..."}}
            if "error" in data:
                error_info = data["error"]
                error_msg = error_info.get("message", "Неизвестная ошибка")
                error_code = error_info.get("code", "unknown")
                logger.error(f"OpenRouter ошибка [{error_code}]: {error_msg}")
                raise OpenRouterError(f"OpenRouter API error [{error_code}]: {error_msg}")
            
            # Извлечение ответа из формата OpenAI
            try:
                choices = data.get("choices", [])
                if not choices:
                    raise OpenRouterError("Пустой ответ от OpenRouter (нет choices)")
                
                content = choices[0].get("message", {}).get("content", "")
                
                if not content:
                    raise OpenRouterError("Пустой текст в ответе OpenRouter")
                
                return content
                
            except (KeyError, IndexError) as e:
                logger.error(f"Некорректный формат ответа от OpenRouter: {data}")
                raise OpenRouterError(f"Некорректный формат ответа OpenRouter: {e}")
    
    async def check_health(self) -> bool:
        """
        Проверка доступности OpenRouter API (с кэшированием).

        Returns:
            True если API доступно, False иначе.
        """
        import time
        current_time = int(time.time())

        async with self._health_lock:
            # Проверка кэша
            if current_time - self._health_cache["time"] < self.health_cache_ttl:
                return self._health_cache["status"] or False

            try:
                client = await self._get_client()

                # Проверка через запрос к списку моделей
                url = f"{self.BASE_URL}/models"

                async with client.stream("GET", url, headers=self.headers) as response:
                    await response.aread()

                    if response.status_code == 200:
                        logger.info("OpenRouter API доступно")
                        result = True
                    elif response.status_code == 401:
                        logger.error("OpenRouter API: неверный API ключ")
                        result = False
                    else:
                        logger.warning(f"OpenRouter API вернул статус {response.status_code}")
                        result = False

            except httpx.RequestError as e:
                logger.warning(f"OpenRouter API недоступно: {type(e).__name__}: {e}")
                result = False
            except Exception as e:
                logger.warning(f"Ошибка проверки OpenRouter API: {type(e).__name__}: {e}")
                result = False

            # Сохранение в кэш
            self._health_cache["status"] = result
            self._health_cache["time"] = current_time

            return result
    
    async def get_models(self) -> List[str]:
        """
        Получение списка доступных моделей OpenRouter.
        
        Returns:
            Список названий моделей.
        """
        try:
            client = await self._get_client()
            url = f"{self.BASE_URL}/models"
            
            async with client.stream("GET", url, headers=self.headers) as response:
                await response.aread()
                
                if response.status_code != 200:
                    logger.warning(f"OpenRouter вернул статус {response.status_code}")
                    return []
                
                data = response.json()
                models = data.get("data", [])
                
                # Извлекаем имена моделей
                result = [model.get("id", "") for model in models if model.get("id")]
                
                logger.info(f"Получено {len(result)} моделей от OpenRouter")
                return result
                
        except Exception as e:
            logger.error(f"Ошибка получения списка моделей OpenRouter: {e}")
            return []
    
    async def get_popular_models(self) -> List[Dict]:
        """
        Получение списка популярных моделей.
        
        Returns:
            Список популярных моделей с информацией.
        """
        all_models = await self.get_models()
        
        popular = []
        for model_id in self.POPULAR_MODELS:
            if model_id in all_models or model_id == "auto":
                popular.append({
                    "id": model_id,
                    "name": model_id,
                    "description": "Популярная модель" if model_id != "auto" else "Автоматический выбор"
                })
        
        return popular
    
    def __repr__(self) -> str:
        return f"OpenRouterProvider(model={self.model!r})"


# Для импорта в других модулях
__all__ = ["OpenRouterProvider", "OpenRouterError"]
