"""
Конфигурация провайдеров для TgBrain.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from .masking import mask_api_key


@dataclass
class ProviderConfig:
    """Конфигурация отдельного провайдера."""
    name: str
    api_key: Optional[str]
    base_url: str
    model: str
    enabled: bool = True


class ProviderConfigMixin:
    """
    Миксин для управления конфигурацией провайдеров.
    
    Предназначен для использования с классом Settings.
    Атрибуты ниже определены в Settings классе.
    """
    
    # Атрибуты которые предоставляются Settings классом
    llm_active_provider: str
    llm_fallback_providers: str
    llm_auto_fallback: bool
    tg_api_id: Optional[int]
    tg_api_hash: Optional[str]
    db_password: str
    gemini_api_key: Optional[str]
    gemini_base_url: str
    gemini_model: str
    openrouter_api_key: Optional[str]
    openrouter_base_url: str
    openrouter_model: str
    ollama_llm_enabled: bool
    ollama_llm_base_url: str
    ollama_llm_model: str
    lm_studio_enabled: bool
    lm_studio_base_url: str
    lm_studio_model: str

    def get_provider_config(self, provider_name: Optional[str] = None) -> ProviderConfig:
        """
        Получить конфигурацию провайдера по имени.

        Args:
            provider_name: Название провайдера (опционально).

        Returns:
            Конфигурация провайдера.

        Raises:
            ValueError: Если провайдер не найден.
        """
        from .settings import Settings

        settings = self if isinstance(self, Settings) else Settings()
        name = (provider_name or settings.llm_active_provider).lower()

        providers = {
            "gemini": ProviderConfig(
                name="gemini",
                api_key=settings.gemini_api_key,
                base_url=settings.gemini_base_url,
                model=settings.gemini_model,
                enabled=True
            ),
            "openrouter": ProviderConfig(
                name="openrouter",
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
                model=settings.openrouter_model,
                enabled=True
            ),
            "ollama": ProviderConfig(
                name="ollama",
                api_key=None,
                base_url=settings.ollama_llm_base_url,
                model=settings.ollama_llm_model,
                enabled=settings.ollama_llm_enabled
            ),
            "lm-studio": ProviderConfig(
                name="lm-studio",
                api_key=None,
                base_url=settings.lm_studio_base_url,
                model=settings.lm_studio_model,
                enabled=settings.lm_studio_enabled
            ),
            "lm_studio": ProviderConfig(
                name="lm-studio",
                api_key=None,
                base_url=settings.lm_studio_base_url,
                model=settings.lm_studio_model,
                enabled=settings.lm_studio_enabled
            ),
        }

        if name not in providers:
            available = ", ".join(providers.keys())
            raise ValueError(f"Неизвестный провайдер: {name}. Доступные: {available}")

        return providers[name]

    @property
    def llm_provider(self) -> str:
        """Получить название активного провайдера."""
        return self.llm_active_provider.lower()

    @property
    def llm_api_key(self) -> Optional[str]:
        """Получить API ключ активного провайдера."""
        config = self.get_provider_config()
        return config.api_key

    @property
    def llm_base_url(self) -> str:
        """Получить базовый URL активного провайдера."""
        config = self.get_provider_config()
        return config.base_url

    @property
    def llm_model_name(self) -> str:
        """Получить название модели активного провайдера."""
        config = self.get_provider_config()
        return config.model

    def get_fallback_providers(self) -> List[str]:
        """Получить список fallback провайдеров."""
        if not self.llm_fallback_providers:
            return []
        return [p.strip().lower() for p in self.llm_fallback_providers.split(",")]

    def is_local_provider(self, provider_name: str) -> bool:
        """Проверить, является ли провайдер локальным."""
        return provider_name.lower() in ["ollama", "lm-studio", "lm_studio"]

    def get_provider_chain(self) -> List[str]:
        """Получить цепочку провайдеров (активный + fallback)."""
        chain = [self.llm_active_provider.lower()]
        if self.llm_auto_fallback:
            fallbacks = self.get_fallback_providers()
            for fallback in fallbacks:
                if fallback not in chain:
                    chain.append(fallback)
        return chain

    def get_all_providers(self) -> Dict[str, ProviderConfig]:
        """Получить конфигурацию всех провайдеров."""
        from .settings import Settings

        settings = self if isinstance(self, Settings) else Settings()

        return {
            "gemini": ProviderConfig(
                name="gemini",
                api_key=settings.gemini_api_key,
                base_url=settings.gemini_base_url,
                model=settings.gemini_model,
                enabled=True
            ),
            "openrouter": ProviderConfig(
                name="openrouter",
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
                model=settings.openrouter_model,
                enabled=True
            ),
            "ollama": ProviderConfig(
                name="ollama",
                api_key=None,
                base_url=settings.ollama_llm_base_url,
                model=settings.ollama_llm_model,
                enabled=settings.ollama_llm_enabled
            ),
            "lm-studio": ProviderConfig(
                name="lm-studio",
                api_key=None,
                base_url=settings.lm_studio_base_url,
                model=settings.lm_studio_model,
                enabled=settings.lm_studio_enabled
            ),
        }

    def validate_required(self) -> List[str]:
        """
        Проверка обязательных полей.

        Returns:
            Список ошибок валидации (пустой если всё ок).
        """
        from .settings import Settings

        settings = self if isinstance(self, Settings) else Settings()
        errors = []

        if not settings.db_password:
            errors.append("DB_PASSWORD не указан")

        # Проверка активного провайдера
        try:
            provider_config = settings.get_provider_config()
            if provider_config.api_key is None and provider_config.name not in ["ollama", "lm-studio"]:
                errors.append(f"API ключ для {provider_config.name} не указан")
        except ValueError as e:
            errors.append(str(e))

        return errors

    def validate_telegram_auth(self) -> List[str]:
        """
        Проверка наличия Telegram авторизации в БД.

        Returns:
            Список ошибок валидации (пустой если всё ок).
        """
        errors = []
        if not self.tg_api_id:
            errors.append("TG_API_ID не настроен в БД")
        if not self.tg_api_hash:
            errors.append("TG_API_HASH не настроен в БД")
        return errors

    def print_config(self) -> None:
        """Вывод конфигурации в лог (без чувствительных данных)."""
        from .settings import Settings

        settings = self if isinstance(self, Settings) else Settings()
        logger = logging.getLogger(__name__)
        embedding_cfg = settings.embedding_config

        logger.info("=" * 50)
        logger.info("Конфигурация приложения")
        logger.info("=" * 50)
        logger.info(f"Telegram API ID: {settings.tg_api_id}")
        logger.info("Telegram сессия: (хранится в БД)")
        logger.info("Чаты для мониторинга: (из БД через ChatSettingsRepository)")
        logger.info(f"БД: {settings.db_host}:{settings.db_port}/{settings.db_name}")
        logger.info(f"Активный LLM провайдер: {settings.llm_active_provider}")

        # Информация о провайдере
        try:
            provider_config = settings.get_provider_config()
            api_key_masked = mask_api_key(provider_config.api_key)
            logger.info(f"  API Key: {api_key_masked}")
            logger.info(f"  Base URL: {provider_config.base_url}")
            logger.info(f"  Model: {provider_config.model}")
        except ValueError:
            pass

        ollama = embedding_cfg.ollama
        logger.info(f"Ollama Embedding: {ollama.url} ({ollama.model})")
        logger.info(f"Embedding провайдер: {settings.ollama_embedding_provider}")
        logger.info(f"Log Level: {settings.log_level}")
        logger.info("=" * 50)
