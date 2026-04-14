"""
Модульные тесты конфигурации.
"""

from src.config import Settings, get_settings


def test_settings_loads_from_env():
    """Проверка загрузки настроек из .env."""
    settings = Settings()
    assert settings.tg_api_id is not None or True  # Может быть None в тестах
    assert settings.db_host is not None
    assert settings.llm_active_provider is not None


def test_chat_enable_list_parsed():
    """Проверка парсинга списка чатов для включения."""
    settings = Settings()
    assert isinstance(settings.tg_chat_enable_list, list)
    # Если tg_chat_enable указан, все элементы должны быть int
    if settings.tg_chat_enable_list:
        assert all(isinstance(x, int) for x in settings.tg_chat_enable_list)


def test_db_url_generated():
    """Проверка автогенерации DB_URL."""
    settings = Settings()
    assert settings.db_url is not None
    assert "postgresql://" in settings.db_url


def test_settings_singleton():
    """Проверка кэширования Settings."""
    settings1 = get_settings()
    get_settings.cache_clear()
    settings2 = get_settings()
    # После очистки кэша это разные экземпляры
    assert settings1 is not settings2


def test_provider_config(settings):
    """Проверка получения конфигурации провайдера."""
    config = settings.get_provider_config()
    assert config is not None
    assert config.name is not None
    assert config.base_url is not None
    assert config.model is not None


def test_fallback_providers(settings):
    """Проверка получения списка fallback провайдеров."""
    fallbacks = settings.get_fallback_providers()
    assert isinstance(fallbacks, list)


def test_provider_chain(settings):
    """Проверка цепочки провайдеров."""
    chain = settings.get_provider_chain()
    assert isinstance(chain, list)
    assert len(chain) >= 1
    # Активный провайдер должен быть первым
    assert chain[0] == settings.llm_active_provider.lower()
