"""
Библиотека LLM провайдеров для TgBrain.

Поддерживаемые провайдеры:
- Google Gemini (gemini)
- OpenRouter (openrouter)
- Ollama (ollama)
- LM Studio (lm-studio)

Пример использования:
    from src.providers import create_llm_provider, ProviderFactory
    
    # Через фабрику
    provider = ProviderFactory.create(settings, "gemini")
    
    # Через удобную функцию
    provider = create_llm_provider(settings)
"""

from typing import Optional, Type, Union

from src.config import Settings

from .gemini_provider import GeminiProvider, GeminiError
from .local_llm_provider import LocalLLMProvider, LocalLLMError
from .openrouter_provider import OpenRouterProvider, OpenRouterError


class ProviderFactory:
    """Фабрика для создания LLM провайдеров."""
    
    # Маппинг имён провайдеров на классы
    PROVIDERS = {
        "gemini": GeminiProvider,
        "openrouter": OpenRouterProvider,
        "ollama": LocalLLMProvider,
        "lm-studio": LocalLLMProvider,
        "lm_studio": LocalLLMProvider,  # Альтернативное написание
    }
    
    # Алиасы для провайдеров
    ALIASES = {
        "google": "gemini",
        "open-router": "openrouter",
        "local": "ollama",
    }
    
    @classmethod
    def get_provider_class(cls, provider_name: str) -> Optional[Type]:
        """
        Получить класс провайдера по имени.
        
        Args:
            provider_name: Название провайдера.
        
        Returns:
            Класс провайдера или None если не найден.
        """
        # Проверяем алиасы
        provider_name = provider_name.lower()
        if provider_name in cls.ALIASES:
            provider_name = cls.ALIASES[provider_name]
        
        return cls.PROVIDERS.get(provider_name)
    
    @classmethod
    def create(cls, config: Settings, provider_name: Optional[str] = None):
        """
        Создать экземпляр провайдера.
        
        Args:
            config: Настройки приложения.
            provider_name: Название провайдера (опционально, берётся из config).
        
        Returns:
            Экземпляр провайдера.
        
        Raises:
            ValueError: Если провайдер не найден.
        """
        name = provider_name or config.llm_provider
        provider_class = cls.get_provider_class(name)
        
        if not provider_class:
            available = ", ".join(cls.PROVIDERS.keys())
            raise ValueError(
                f"Неизвестный провайдер: {name}. "
                f"Доступные: {available}"
            )
        
        return provider_class(config)


def create_llm_provider(config: Settings) -> Union[
    GeminiProvider,
    OpenRouterProvider,
    LocalLLMProvider
]:
    """
    Создать LLM провайдер на основе настроек.
    
    Удобная функция для быстрого создания провайдера.
    
    Args:
        config: Настройки приложения.
    
    Returns:
        Экземпляр провайдера.
    
    Raises:
        ValueError: Если провайдер не найден.
    
    Пример:
        settings = Settings()
        provider = create_llm_provider(settings)
        response = await provider.generate("Привет!")
    """
    return ProviderFactory.create(config)


def get_available_providers() -> list[str]:
    """
    Получить список доступных провайдеров.
    
    Returns:
        Список названий провайдеров.
    """
    return list(ProviderFactory.PROVIDERS.keys())


# Экспорт всех классов и функций
__all__ = [
    # Фабрика
    "ProviderFactory",
    
    # Удобные функции
    "create_llm_provider",
    "get_available_providers",
    
    # Провайдеры
    "GeminiProvider",
    "OpenRouterProvider",
    "LocalLLMProvider",
    
    # Ошибки
    "GeminiError",
    "OpenRouterError",
    "LocalLLMError",
]
