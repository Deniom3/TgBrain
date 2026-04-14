"""
Конфигурация приложения через pydantic-settings.
"""

from .cors import parse_cors_origins
from .exceptions import ConfigurationError
from .loader import load_settings_from_db, reload_settings, validate_settings, validate_telegram_auth
from .masking import mask_api_key
from .providers import ProviderConfig, ProviderConfigMixin
from .settings import (
    EmbeddingProvidersConfig,
    GeminiEmbeddingConfig,
    LMStudioEmbeddingConfig,
    OllamaEmbeddingConfig,
    OpenRouterEmbeddingConfig,
    Settings,
    SettingsWithProviders,
    get_settings,
    settings,
)

__all__ = [
    "ConfigurationError",
    "EmbeddingProvidersConfig",
    "GeminiEmbeddingConfig",
    "LMStudioEmbeddingConfig",
    "OllamaEmbeddingConfig",
    "OpenRouterEmbeddingConfig",
    "Settings",
    "SettingsWithProviders",
    "get_settings",
    "load_settings_from_db",
    "mask_api_key",
    "parse_cors_origins",
    "ProviderConfig",
    "ProviderConfigMixin",
    "reload_settings",
    "settings",
    "validate_settings",
    "validate_telegram_auth",
]
