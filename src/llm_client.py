"""
Унифицированный LLM клиент для TgBrain.

Использует фабрику провайдеров для создания соответствующего клиента.
Поддерживает автоматический fallback на резервных провайдеров.

Поддерживаемые провайдеры:
- Google Gemini (gemini)
- OpenRouter (openrouter)
- Ollama (ollama)
- LM Studio (lm-studio)

Пример использования:
    from src.config import Settings
    from src.llm_client import LLMClient
    
    settings = Settings()
    client = LLMClient(settings)
    
    response = await client.generate("Привет!")
    print(response)
"""

import logging
from typing import Dict, List, Optional, Protocol, Union

import httpx

from src.config import Settings
from src.providers import (
    ProviderFactory,
    GeminiProvider,
    OpenRouterProvider,
    LocalLLMProvider,
    LocalLLMError,
)

logger = logging.getLogger(__name__)


class LLMProvider(Protocol):
    """Protocol для LLM провайдеров."""

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> str:
        """Сгенерировать ответ от LLM."""
        ...

    async def check_health(self) -> bool:
        """Проверить здоровье провайдера."""
        ...

    async def get_models(self) -> List[str]:
        """Получить список доступных моделей."""
        ...

    async def close(self) -> None:
        """Закрыть соединения провайдера."""
        ...


class EmbeddingProvider(Protocol):
    """Protocol для embedding провайдеров."""

    async def get_embedding(self, text: str) -> List[float]:
        """Получить эмбеддинг текста."""
        ...

    async def check_health(self) -> bool:
        """Проверить доступность сервиса."""
        ...

    async def get_models(self) -> List[str]:
        """Получить список доступных моделей."""
        ...

    async def close(self) -> None:
        """Закрыть соединения провайдера."""
        ...


# Типы провайдеров
ProviderType = Union[GeminiProvider, OpenRouterProvider, LocalLLMProvider]

# Исключения для которых срабатывает fallback
FALLBACK_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    LocalLLMError,
)


class LLMClient:
    """
    Унифицированный клиент для работы с LLM.
    
    Автоматически выбирает провайдер на основе настроек и делегирует
    вызовы соответствующему классу.
    
    Поддерживает автоматический fallback на резервных провайдеров
    при недоступности основного (для локальных моделей).
    
    Поддерживает:
    - Генерацию текста
    - Проверку здоровья API
    - Получение списка моделей
    - Retry-логику (зависит от провайдера)
    - Автоматический fallback для локальных провайдеров
    """
    
    def __init__(self, config: Settings):
        """
        Инициализация LLM клиента.
        
        Args:
            config: Настройки приложения.
        """
        self.config = config
        self.provider_name = config.llm_active_provider.lower()
        self.model = config.llm_model_name
        self.auto_fallback = config.llm_auto_fallback
        self.fallback_timeout = config.llm_fallback_timeout
        
        # Текущий провайдер
        self._provider: Optional[ProviderType] = None
        self._current_provider_name: Optional[str] = None
        
        # Кэш доступных провайдеров
        self._available_providers: Dict[str, bool] = {}
        
        logger.info(f"LLMClient инициализирован (основной: {self.provider_name}, fallback: {self.auto_fallback})")
    
    def _create_provider(self, provider_name: str) -> ProviderType:
        """Создать провайдер по имени.

        Args:
            provider_name: Название провайдера (например, "gemini", "ollama").

        Returns:
            Экземпляр провайдера.
        """
        provider = ProviderFactory.create(self.config, provider_name)
        logger.debug(f"Создан провайдер: {provider_name}")
        return provider
    
    async def _check_provider_health(self, provider: ProviderType) -> bool:
        """Проверить здоровье провайдера с таймаутом."""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self.fallback_timeout)):
                # Просто вызываем check_health провайдера
                return await provider.check_health()
        except Exception:
            return False
    
    async def _get_available_provider(self) -> tuple[ProviderType, str]:
        """
        Получить доступный провайдер (основной или fallback).
        
        Returns:
            Кортеж (провайдер, название провайдера).
        
        Raises:
            ValueError: Если ни один провайдер не доступен.
        """
        # Получаем цепочку провайдеров
        provider_chain = self.config.get_provider_chain()
        
        logger.info(f"Проверка провайдеров: {provider_chain}")
        
        for provider_name in provider_chain:
            # Проверяем кэш
            if provider_name in self._available_providers:
                if self._available_providers[provider_name]:
                    logger.debug(f"Провайдер {provider_name} доступен (из кэша)")
                    # Создаём провайдер если нет
                    if not self._provider or self._current_provider_name != provider_name:
                        provider = self._create_provider(provider_name)
                        self._provider = provider
                        self._current_provider_name = provider_name
                    return self._provider, provider_name
                else:
                    logger.debug(f"Провайдер {provider_name} недоступен (из кэша)")
                    continue  # Пропускает недоступный
            
            # Создаём провайдер
            provider = self._create_provider(provider_name)
            
            # Проверяем здоровье
            is_local = self.config.is_local_provider(provider_name)
            
            if is_local and self.auto_fallback:
                # Для локальных провайдеров проверяем доступность
                logger.info(f"Проверка доступности локального провайдера: {provider_name}")
                health = await self._check_provider_health(provider)
                
                if health:
                    self._available_providers[provider_name] = True
                    logger.info(f"✅ Локальный провайдер {provider_name} доступен")
                    return provider, provider_name
                else:
                    self._available_providers[provider_name] = False
                    logger.warning(f"❌ Локальный провайдер {provider_name} недоступен")
                    continue
            else:
                # Для облачных провайдеров считаем доступными
                self._available_providers[provider_name] = True
                logger.info(f"✅ Облачный провайдер {provider_name} доступен")
                return provider, provider_name
        
        # Ни один провайдер не доступен
        raise ValueError(
            f"Ни один провайдер не доступен: {provider_chain}. "
            f"Проверьте подключение к интернету и настройки."
        )
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> str:
        """
        Генерация ответа от LLM с автоматическим fallback.
        
        Args:
            prompt: Пользовательский запрос.
            system_prompt: Системная инструкция (опционально).
            temperature: Температура генерации (0.0-2.0).
            max_tokens: Максимальное количество токенов.
            **kwargs: Дополнительные параметры (зависят от провайдера).
        
        Returns:
            Текст ответа от модели.
        
        Raises:
            ValueError: Если ни один провайдер не доступен.
        """
        # Получаем доступный провайдер
        provider, provider_name = await self._get_available_provider()
        
        # Если сменился провайдер, закрываем старый
        if self._current_provider_name != provider_name:
            if self._provider:
                await self._provider.close()
            self._provider = provider
            self._current_provider_name = provider_name
            
            if provider_name != self.provider_name:
                logger.warning(f"⚠️ Переключение на fallback провайдер: {provider_name}")
        
        if self._provider is None:
            raise RuntimeError("LLM провайдер не инициализирован")
        
        try:
            response = await self._provider.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            # Успешный запрос - помечаем провайдер как доступный
            self._available_providers[provider_name] = True
            
            return response
            
        except FALLBACK_EXCEPTIONS as e:
            # Ошибка подключения - помечаем провайдер как недоступный
            logger.warning(f"Ошибка провайдера {provider_name}: {type(e).__name__}: {e}")
            self._available_providers[provider_name] = False
            
            # НЕ очищаем кэш — пусть следующий вызов использует fallback
            # Пробуем следующий провайдер
            logger.info("Попытка использования fallback провайдера...")
            return await self.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
    
    async def check_health(self) -> bool:
        """
        Проверка доступности провайдеров с fallback-логикой.

        Проверяет провайдеров по цепочке (как generate) и возвращает
        статус первого доступного.

        Returns:
            True если хотя бы один провайдер доступен, False иначе.
        """
        provider_chain = self.config.get_provider_chain()

        for provider_name in provider_chain:
            if provider_name in self._available_providers:
                if self._available_providers[provider_name]:
                    return True
                continue

            provider = self._create_provider(provider_name)
            is_local = self.config.is_local_provider(provider_name)

            if is_local and self.auto_fallback:
                health = await self._check_provider_health(provider)
                self._available_providers[provider_name] = health
                if health:
                    return True
            else:
                self._available_providers[provider_name] = True
                return True

        return False
    
    async def get_models(self) -> List[str]:
        """
        Получение списка доступных моделей.
        
        Returns:
            Список названий моделей.
        """
        if not self._provider:
            self._provider = self._create_provider(self.provider_name)
            self._current_provider_name = self.provider_name
        
        return await self._provider.get_models()
    
    async def close(self) -> None:
        """Закрыть соединения провайдера."""
        if self._provider:
            await self._provider.close()
            self._provider = None
            self._current_provider_name = None
        
        self._available_providers.clear()
        logger.info("LLMClient закрыт")
    
    @property
    def current_provider(self) -> str:
        """Получить название текущего провайдера."""
        return self._current_provider_name or self.provider_name
    
    def __repr__(self) -> str:
        return f"LLMClient(provider={self.current_provider!r}, model={self.model!r})"

    def refresh_config(self, new_config: Settings) -> None:
        """Обновить ссылку на Settings после reload.

        Args:
            new_config: Новый экземпляр Settings.
        """
        self.config = new_config
        self.provider_name = new_config.llm_active_provider.lower()
        self.model = new_config.llm_model_name
        self.auto_fallback = new_config.llm_auto_fallback
        self.fallback_timeout = new_config.llm_fallback_timeout
        self._available_providers.clear()
        self._provider = None
        self._current_provider_name = None
        logger.info("LLMClient обновлён: провайдер=%s", self.provider_name)
        logger.debug(
            "LLMClient config refreshed: provider=%s, model=%s",
            new_config.llm_active_provider,
            new_config.llm_model_name,
        )


# Для импорта в других модулях
__all__ = ["LLMClient", "LLMProvider", "EmbeddingProvider"]
