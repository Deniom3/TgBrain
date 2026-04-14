"""
Google Gemini API провайдер для LLM.

Документация:
- https://ai.google.dev/gemini-api/docs/api-key
- https://ai.google.dev/gemini-api/docs/models/gemini

API Endpoint:
    https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent

Authentication:
    Заголовок: x-goog-api-key: YOUR_API_KEY

Free Tier (на 2026):
    - gemini-2.5-flash (бесплатно с лимитами)
    - gemini-2.5-flash-lite (бесплатно с лимитами)
    - gemini-embeddings (бесплатно)
    
Rate Limits Free Tier:
    - 15 запросов в минуту (RPM)
    - 1 000 000 токенов в минуту (TPM)
    - 1500 запросов в день
"""

import asyncio
import logging
from typing import Dict, List, Optional

import httpx

from src.config import Settings

logger = logging.getLogger(__name__)


class GeminiError(Exception):
    """Базовое исключение для ошибок Gemini API."""
    pass


class GeminiRateLimitError(GeminiError):
    """Ошибка rate limit Gemini API (429)."""

    def __init__(self, message: str, retry_after: Optional[float] = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class GeminiProvider:
    """
    Провайдер для Google Gemini API.
    
    Поддерживает:
    - Генерацию текста через Gemini модели
    - Получение списка доступных моделей
    - Проверку здоровья API
    - Retry-логику при временных ошибках
    """
    
    # Базовый URL API
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    
    # Модели доступные в free tier
    FREE_TIER_MODELS = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-embeddings",
    ]
    
    def __init__(self, config: Settings):
        """
        Инициализация провайдера.

        Args:
            config: Настройки приложения.
        """
        self.api_key = config.llm_api_key
        self.model = config.llm_model_name
        self.max_retries = 3
        self.base_delay = 2.0
        self.timeout = httpx.Timeout(120.0, connect=10.0)
        self.health_cache_ttl = 60  # Кэш health check на 60 секунд

        # Заголовки для API
        self.headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key or ""
        }

        self._client: Optional[httpx.AsyncClient] = None
        self._health_cache: Dict = {"status": None, "time": 0}
        self._health_lock: asyncio.Lock = asyncio.Lock()

        logger.info(f"GeminiProvider инициализирован (модель: {self.model})")
    
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
        max_tokens: int = 2048
    ) -> str:
        """
        Генерация ответа от Gemini с retry-логикой.
        
        Args:
            prompt: Пользовательский запрос.
            system_prompt: Системная инструкция (опционально).
            temperature: Температура генерации (0.0-2.0).
            max_tokens: Максимальное количество токенов.
        
        Returns:
            Текст ответа от модели.
        
        Raises:
            GeminiError: После неудачных попыток запроса.
        """
        # Формирование содержимого запроса
        contents = []
        
        # Добавляем system prompt если указан
        if system_prompt:
            contents.append({
                "role": "user",
                "parts": [{"text": system_prompt}]
            })
            contents.append({
                "role": "model", 
                "parts": [{"text": "Понял, буду следовать инструкциям."}]
            })
        
        # Добавляем пользовательский запрос
        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })
        
        # Попытки запроса с retry-логикой
        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return await self._call_api(
                    contents=contents,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            except GeminiRateLimitError as e:
                last_error = e
                exponential_delay = self.base_delay * (2 ** attempt)
                delay = max(exponential_delay, e.retry_after) if e.retry_after else exponential_delay
                logger.warning(
                    f"Попытка {attempt}/{self.max_retries} не удалась: "
                    f"Rate limit (429), задержка {delay:.1f}с"
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(delay)
            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    f"Попытка {attempt}/{self.max_retries} не удалась: "
                    f"HTTP ошибка {e.response.status_code}"
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.base_delay)
            except httpx.RequestError as e:
                last_error = e
                logger.warning(
                    f"Попытка {attempt}/{self.max_retries} не удалась: "
                    f"Ошибка запроса {type(e).__name__}"
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.base_delay)
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Попытка {attempt}/{self.max_retries} не удалась: "
                    f"{type(e).__name__}: {e}"
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.base_delay)
        
        # Все попытки исчерпаны
        error_msg = f"Не удалось получить ответ от Gemini после {self.max_retries} попыток"
        logger.error(error_msg)
        if last_error:
            raise GeminiError(f"{error_msg}: {last_error}")
        raise GeminiError(error_msg)
    
    async def _call_api(
        self,
        contents: List[Dict],
        temperature: float,
        max_tokens: int
    ) -> str:
        """
        Один запрос к Gemini API.
        
        Args:
            contents: Содержимое запроса в формате Gemini.
            temperature: Температура генерации.
            max_tokens: Максимальное количество токенов.
        
        Returns:
            Текст ответа от модели.
        
        Raises:
            httpx.HTTPStatusError: При ошибке HTTP статуса.
            httpx.RequestError: При ошибке запроса.
            GeminiError: При ошибке в ответе API.
        """
        client = await self._get_client()
        
        # Формирование URL для запроса
        model_name = self.model or "gemini-2.5-flash"
        url = f"{self.BASE_URL}/models/{model_name}:generateContent"
        
        # Формирование payload запроса
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }
        
        logger.debug(f"Запрос к Gemini: {url}, модель: {model_name}")
        
        async with client.stream("POST", url, json=payload, headers=self.headers) as response:
            # Читаем ответ перед парсингом
            await response.aread()
            
            if response.status_code == 401:
                raise GeminiError("Неверный API ключ Gemini")
            
            if response.status_code == 403:
                raise GeminiError("Доступ запрещён. Проверьте квоты API.")
            
            if response.status_code == 429:
                retry_after_header = response.headers.get("retry-after")
                retry_after: Optional[float] = None
                if retry_after_header:
                    try:
                        retry_after = float(retry_after_header)
                    except (ValueError, TypeError):
                        pass
                raise GeminiRateLimitError(
                    "Превышен лимит запросов (rate limit)",
                    retry_after=retry_after,
                )
            
            if response.status_code != 200:
                request = httpx.Request("POST", url, json=payload, headers=self.headers)
                raise httpx.HTTPStatusError(
                    f"HTTP {response.status_code}: {response.text[:200]}",
                    request=request,
                    response=response
                )
            
            data = response.json()
            
            # Извлечение ответа из формата Gemini
            try:
                candidates = data.get("candidates", [])
                if not candidates:
                    raise GeminiError("Пустой ответ от Gemini (нет candidates)")
                
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                
                if not parts:
                    raise GeminiError("Пустой ответ от Gemini (нет parts)")
                
                text = parts[0].get("text", "")
                
                if not text:
                    raise GeminiError("Пустой текст в ответе Gemini")
                
                return text
                
            except (KeyError, IndexError) as e:
                logger.error(f"Некорректный формат ответа от Gemini: {data}")
                raise GeminiError(f"Некорректный формат ответа Gemini: {e}")
    
    async def check_health(self) -> bool:
        """
        Проверка доступности Gemini API (с кэшированием).

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
                        logger.info("Gemini API доступно")
                        result = True
                    elif response.status_code == 401:
                        logger.error("Gemini API: неверный API ключ")
                        result = False
                    elif response.status_code == 403:
                        logger.error("Gemini API: доступ запрещён")
                        result = False
                    else:
                        logger.warning(f"Gemini API вернул статус {response.status_code}")
                        result = False

            except httpx.RequestError as e:
                logger.warning(f"Gemini API недоступно: {type(e).__name__}: {e}")
                result = False
            except Exception as e:
                logger.warning(f"Ошибка проверки Gemini API: {type(e).__name__}: {e}")
                result = False

            # Сохранение в кэш
            self._health_cache["status"] = result
            self._health_cache["time"] = current_time

            return result
    
    async def get_models(self) -> List[str]:
        """
        Получение списка доступных моделей Gemini.
        
        Returns:
            Список названий моделей.
        """
        try:
            client = await self._get_client()
            url = f"{self.BASE_URL}/models"
            
            async with client.stream("GET", url, headers=self.headers) as response:
                await response.aread()
                
                if response.status_code != 200:
                    logger.warning(f"Gemini вернул статус {response.status_code}")
                    return []
                
                data = response.json()
                models = data.get("models", [])
                
                # Извлекаем имена моделей
                result = []
                for model in models:
                    name = model.get("name", "")
                    # API возвращает имя в формате "models/gemini-2.5-flash"
                    # Извлекаем только название модели
                    if name.startswith("models/"):
                        name = name[7:]  # Удаляем префикс "models/"

                    # Фильтруем только генеративные модели
                    if "generateContent" in model.get("supportedGenerationMethods", []):
                        result.append(name)
                
                logger.info(f"Получено {len(result)} моделей от Gemini")
                return result
                
        except Exception as e:
            logger.error(f"Ошибка получения списка моделей Gemini: {e}")
            return []
    
    async def get_free_tier_models(self) -> List[Dict]:
        """
        Получение списка моделей доступных в free tier.
        
        Returns:
            Список моделей с информацией.
        """
        all_models = await self.get_models()
        
        free_models = []
        for model in all_models:
            # Проверяем, есть ли модель в списке free tier
            if any(free_model in model for free_model in self.FREE_TIER_MODELS):
                free_models.append({
                    "name": model,
                    "free_tier": True,
                    "description": "Доступно в бесплатном тарифе"
                })
        
        return free_models
    
    def __repr__(self) -> str:
        return f"GeminiProvider(model={self.model!r})"


# Для импорта в других модулях
__all__ = ["GeminiProvider", "GeminiError", "GeminiRateLimitError"]
