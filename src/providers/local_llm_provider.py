"""
Локальные LLM провайдеры (Ollama, LM Studio).

Поддерживаемые провайдеры:
- Ollama (http://localhost:11434)
- LM Studio (http://localhost:1234)
- Другие OpenAI-совместимые локальные серверы

API Endpoints:
    Ollama (legacy): http://localhost:11434/api/generate
    Ollama (OpenAI): http://localhost:11434/v1/chat/completions
    LM Studio: http://localhost:1234/v1/chat/completions

Authentication:
    Не требуется для локальных серверов
"""

import asyncio
import logging
from typing import Dict, List, Optional

import httpx

from src.config import Settings

logger = logging.getLogger(__name__)


class LocalLLMError(Exception):
    """Базовое исключение для ошибок локальных LLM."""
    pass


class LocalLLMProvider:
    """
    Провайдер для локальных LLM (Ollama, LM Studio).
    
    Поддерживает:
    - Ollama (legacy API и OpenAI-совместимый)
    - LM Studio (OpenAI-совместимый)
    - Другие OpenAI-совместимые серверы
    - Автоопределение типа API
    - Retry-логику при временных ошибках
    """
    
    # Типы API
    API_TYPE_LEGACY_OLLAMA = "legacy_ollama"
    API_TYPE_OPENAI_COMPAT = "openai_compat"
    
    def __init__(self, config: Settings):
        """
        Инициализация провайдера.
        
        Args:
            config: Настройки приложения.
        """
        self.provider_name = config.llm_provider
        self.api_key = config.llm_api_key
        self.base_url = config.llm_base_url.rstrip("/")
        self.model = config.llm_model_name
        self.max_retries = 3
        self.base_delay = 2.0
        self.timeout = httpx.Timeout(120.0, connect=10.0)
        self.health_cache_ttl = 60  # Кэш health check на 60 секунд

        # Определяем тип API
        self.api_type = self._detect_api_type()

        # Заголовки для API
        self.headers = {
            "Content-Type": "application/json",
        }

        # Добавляем Authorization если есть API ключ (для LM Studio)
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"

        self._client: Optional[httpx.AsyncClient] = None
        self._health_cache: Dict = {"status": None, "time": 0}
        self._health_lock: asyncio.Lock = asyncio.Lock()

        logger.info(f"LocalLLMProvider инициализирован (тип: {self.api_type}, модель: {self.model})")
    
    def _detect_api_type(self) -> str:
        """
        Определение типа API по URL и провайдеру.
        
        Returns:
            Тип API (legacy_ollama или openai_compat).
        """
        # Legacy Ollama API используется только если:
        # 1. provider == "ollama"
        # 2. URL не содержит "/v1"
        # 3. URL содержит порт 11434 (стандартный порт Ollama)
        if (
            self.provider_name == "ollama" and
            "/v1" not in self.base_url and
            ":11434" in self.base_url
        ):
            return self.API_TYPE_LEGACY_OLLAMA
        
        # Все остальные случаи - OpenAI-совместимый API
        return self.API_TYPE_OPENAI_COMPAT
    
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
        Генерация ответа от локальной LLM с retry-логикой.
        
        Args:
            prompt: Пользовательский запрос.
            system_prompt: Системная инструкция (опционально).
            temperature: Температура генерации (0.0-2.0).
            max_tokens: Максимальное количество токенов.
        
        Returns:
            Текст ответа от модели.
        
        Raises:
            LocalLLMError: После неудачных попыток запроса.
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
                    max_tokens=max_tokens
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
        error_msg = f"Не удалось получить ответ от LLM после {self.max_retries} попыток"
        logger.error(error_msg)
        if last_error:
            raise LocalLLMError(f"{error_msg}: {last_error}")
        raise LocalLLMError(error_msg)
    
    async def _call_api(
        self,
        messages: List[Dict],
        temperature: float,
        max_tokens: int
    ) -> str:
        """
        Один запрос к LLM API.
        
        Args:
            messages: Список сообщений.
            temperature: Температура генерации.
            max_tokens: Максимальное количество токенов.
        
        Returns:
            Текст ответа от модели.
        
        Raises:
            httpx.HTTPStatusError: При ошибке HTTP статуса.
            httpx.RequestError: При ошибке запроса.
            LocalLLMError: При ошибке в ответе API.
        """
        client = await self._get_client()
        
        # Выбираем endpoint в зависимости от типа API
        if self.api_type == self.API_TYPE_LEGACY_OLLAMA:
            return await self._call_ollama_legacy(client, messages, temperature, max_tokens)
        else:
            return await self._call_openai_compat(client, messages, temperature, max_tokens)
    
    async def _call_openai_compat(
        self,
        client: httpx.AsyncClient,
        messages: List[Dict],
        temperature: float,
        max_tokens: int
    ) -> str:
        """
        Запрос к OpenAI-совместимому API (Ollama v1, LM Studio).
        
        Args:
            client: HTTP клиент.
            messages: Список сообщений.
            temperature: Температура генерации.
            max_tokens: Максимальное количество токенов.
        
        Returns:
            Текст ответа от модели.
        """
        # Формируем URL с /v1 если нет
        api_base = self.base_url
        if "/v1" not in api_base:
            api_base = f"{api_base}/v1"
        
        url = f"{api_base}/chat/completions"
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        logger.debug(f"Запрос к LLM: {url}, модель: {self.model}")
        
        async with client.stream("POST", url, json=payload, headers=self.headers) as response:
            # Читаем ответ перед парсингом
            await response.aread()
            
            if response.status_code == 404:
                raise LocalLLMError(f"Модель '{self.model}' не найдена")
            
            if response.status_code != 200:
                request = httpx.Request("POST", url, json=payload, headers=self.headers)
                raise httpx.HTTPStatusError(
                    f"HTTP {response.status_code}: {response.text[:200]}",
                    request=request,
                    response=response
                )
            
            data = response.json()
            
            # Извлечение ответа из формата OpenAI
            try:
                choices = data.get("choices", [])
                if not choices:
                    raise LocalLLMError("Пустой ответ от LLM (нет choices)")
                
                content = choices[0].get("message", {}).get("content", "")
                
                if not content:
                    raise LocalLLMError("Пустой текст в ответе LLM")
                
                return content
                
            except (KeyError, IndexError) as e:
                logger.error(f"Некорректный формат ответа от LLM: {data}")
                raise LocalLLMError(f"Некорректный формат ответа LLM: {e}")
    
    async def _call_ollama_legacy(
        self,
        client: httpx.AsyncClient,
        messages: List[Dict],
        temperature: float,
        max_tokens: int
    ) -> str:
        """
        Запрос к старому API Ollama (/api/generate).
        
        Args:
            client: HTTP клиент.
            messages: Список сообщений.
            temperature: Температура генерации.
            max_tokens: Максимальное количество токенов.
        
        Returns:
            Текст ответа от модели.
        """
        # Объединяем все сообщения в один промпт
        prompt_parts = []
        system_prompt = ""
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_prompt = content
            else:
                prompt_parts.append(f"{role.upper()}: {content}")
        
        # Добавляем system prompt в начало если есть
        if system_prompt:
            prompt_parts.insert(0, f"SYSTEM: {system_prompt}")
        
        prompt = "\n\n".join(prompt_parts)
        
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        
        logger.debug(f"Запрос к Ollama (legacy): {url}, модель: {self.model}")
        
        async with client.stream("POST", url, json=payload) as response:
            # Читаем ответ перед парсингом
            await response.aread()
            
            if response.status_code == 404:
                raise LocalLLMError(f"Модель '{self.model}' не найдена")
            
            if response.status_code != 200:
                request = httpx.Request("POST", url, json=payload)
                raise httpx.HTTPStatusError(
                    f"HTTP {response.status_code}: {response.text[:200]}",
                    request=request,
                    response=response
                )
            
            data = response.json()
            
            # Формат ответа Ollama: {"response": "...", "done": true}
            content = data.get("response", "")
            
            if not content:
                raise LocalLLMError("Пустой ответ от Ollama")
            
            return content
    
    async def check_health(self) -> bool:
        """
        Проверка доступности LLM API (с кэшированием).

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

                # Для Ollama legacy проверяем /api/tags
                if self.api_type == self.API_TYPE_LEGACY_OLLAMA:
                    health_url = f"{self.base_url}/api/tags"
                else:
                    # Для OpenAI-совместимых проверяем /v1/models
                    api_base = self.base_url
                    if "/v1" not in api_base:
                        api_base = f"{api_base}/v1"
                    health_url = f"{api_base}/models"

                async with client.stream("GET", health_url, headers=self.headers) as response:
                    await response.aread()

                    if response.status_code == 200:
                        logger.info(f"LLM API доступно (check: {health_url})")
                        result = True
                    else:
                        logger.warning(f"LLM API вернул статус {response.status_code}")
                        result = False

            except httpx.RequestError as e:
                logger.warning(f"LLM API недоступно: {type(e).__name__}: {e}")
                result = False
            except Exception as e:
                logger.warning(f"Ошибка проверки LLM API: {type(e).__name__}: {e}")
                result = False

            # Сохранение в кэш
            self._health_cache["status"] = result
            self._health_cache["time"] = current_time

            return result
    
    async def get_models(self) -> List[str]:
        """
        Получение списка доступных моделей.
        
        Returns:
            Список названий моделей.
        """
        try:
            client = await self._get_client()
            
            # Для Ollama legacy используем /api/tags
            if self.api_type == self.API_TYPE_LEGACY_OLLAMA:
                url = f"{self.base_url}/api/tags"
            else:
                # Для OpenAI-совместимых используем /v1/models
                api_base = self.base_url
                if "/v1" not in api_base:
                    api_base = f"{api_base}/v1"
                url = f"{api_base}/models"
            
            async with client.stream("GET", url, headers=self.headers) as response:
                await response.aread()
                
                if response.status_code != 200:
                    logger.warning(f"LLM вернул статус {response.status_code}")
                    return []
                
                data = response.json()
                
                # Формат Ollama: {"models": [{"name": "...", ...}, ...]}
                # Формат OpenAI: {"data": [{"id": "...", ...}, ...]}
                if self.api_type == self.API_TYPE_LEGACY_OLLAMA:
                    models = data.get("models", [])
                    return [model.get("name", "") for model in models if model.get("name")]
                else:
                    models = data.get("data", [])
                    return [model.get("id", "") for model in models if model.get("id")]
                
        except Exception as e:
            logger.error(f"Ошибка получения списка моделей: {e}")
            return []
    
    def __repr__(self) -> str:
        return f"LocalLLMProvider(type={self.api_type!r}, model={self.model!r})"


# Для импорта в других модулях
__all__ = ["LocalLLMProvider", "LocalLLMError"]
