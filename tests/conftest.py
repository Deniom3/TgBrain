"""
Fixtures для тестирования TgBrain.

Главный conftest.py — импортирует все fixtures из разбитых модулей
и содержит pytest hooks.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Generator

import pytest

# Отключаем path validation ДО импорта src модулей.
# chunk_generator.py (строка 27) читает SKIP_PATH_VALIDATION на module-level,
# поэтому эта установка необходима ДО любых wildcard импортов из суб-модулей,
# которые могут transitively импортировать chunk_generator.py.
os.environ["SKIP_PATH_VALIDATION"] = "true"

# Импорты из разбитых модулей
from tests.conftest_db import (
    _create_mock_pool,  # noqa: F401
    _is_production_url,  # noqa: F401
    db_pool,  # noqa: F401
    db_pool_with_session_data,  # noqa: F401
    integration_tests_enabled,  # noqa: F401
    mock_db_pool,  # noqa: F401
    real_db_pool,  # noqa: F401
)
from tests.conftest_repositories import (  # noqa: F401
    app_settings_repo,  # noqa: F401
    embedding_providers_repo,  # noqa: F401
    flood_wait_repo,  # noqa: F401
    llm_providers_repo,  # noqa: F401
    pending_cleanup_repo,  # noqa: F401
    request_stats_repo,  # noqa: F401
    summary_cleanup_repo,  # noqa: F401
    telegram_auth_repo,  # noqa: F401
)
from tests.conftest_api import (  # noqa: F401
    app,  # noqa: F401
    integration_import_client,  # noqa: F401
    test_app,  # noqa: F401
    test_client,  # noqa: F401
)
from tests.conftest_fixtures import (  # noqa: F401
    create_test_export_file,  # noqa: F401
    initialized_rag_search,  # noqa: F401
    large_json_export,  # noqa: F401
    mixed_chat_types_json,  # noqa: F401
    mock_chat_settings_repo,  # noqa: F401
    mock_embedding_repo,  # noqa: F401
    mock_rag_service,  # noqa: F401
    mock_summary_repo,  # noqa: F401
    mock_summary_usecase,  # noqa: F401
    mock_webhook_service,  # noqa: F401
    sample_embedding,  # noqa: F401
    sample_json_export,  # noqa: F401
    sample_message,  # noqa: F401
    sample_message_records,  # noqa: F401
    settings,  # noqa: F401
    test_db_settings,  # noqa: F401
    timezone_naive_json,  # noqa: F401
)


def pytest_configure(config):
    """Регистрация custom pytest marks и настройка sys.path."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    config.addinivalue_line("markers", "integration: integration tests requiring Docker")
    config.addinivalue_line("markers", "e2e: end-to-end tests requiring full environment")


def pytest_collection_modifyitems(config, items):
    """Пропуск integration и e2e тестов без соответствующих флагов."""
    if config.getoption("--integration"):
        return
    skip_integration = pytest.mark.skip(reason="Требуется --integration для запуска")
    skip_e2e = pytest.mark.skip(reason="Требуется --e2e для запуска")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
        if "e2e" in item.keywords:
            item.add_marker(skip_e2e)


def pytest_addoption(parser):
    """Добавление опций --integration и --e2e для запуска соответствующих тестов."""
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Run integration tests (requires Docker with PostgreSQL + Ollama)",
    )
    parser.addoption(
        "--e2e",
        action="store_true",
        default=False,
        help="Run end-to-end tests (requires full environment)",
    )


@pytest.fixture(autouse=True)
def skip_path_validation() -> Generator[None, None, None]:
    """
    Гарантирует что SKIP_PATH_VALIDATION установлен для всех тестов.

    Восстанавливает значение после каждого теста.
    Работает в паре с module-level установкой выше:
    - module-level: для eager импортов src (chunk_generator.py читает при import)
    - fixture: для per-test изоляции и восстановления
    """
    old_value = os.environ.get("SKIP_PATH_VALIDATION")
    os.environ["SKIP_PATH_VALIDATION"] = "true"
    os.environ["ALLOW_STATE_RESET"] = "true"
    try:
        yield
    finally:
        if old_value is not None:
            os.environ["SKIP_PATH_VALIDATION"] = old_value
        else:
            os.environ.pop("SKIP_PATH_VALIDATION", None)


@pytest.fixture(scope="session")
def event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
    """
    Использовать WindowsProactorEventLoopPolicy для Windows.

    На Windows pytest-asyncio по умолчанию использует SelectorEventLoop,
    который не поддерживает subprocess. ProactorEventLoop решает эту проблему.
    На non-Windows платформах используется DefaultEventLoopPolicy.
    """
    if sys.platform == "win32":
        return asyncio.WindowsProactorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


# ==================== Fake stub'ы для протокол-проверок ====================


class FakeRAGService:
    """Фейк-реализация IRAGService для тестов протоколов."""

    async def check_chat_exists(self, chat_id: int) -> bool:
        return True

    async def clear_chat_cache(self) -> None:
        pass

    async def summary(self, period_hours: int | None = None, max_messages: int | None = None) -> str:
        return "summary"

    async def close(self) -> None:
        pass


class FakeEmbeddingsClient:
    """Фейк-реализация IEmbeddingsClient для тестов протоколов."""

    async def get_embedding(self, text: str) -> list[float]:
        return [0.1] * 768

    def get_model_name(self) -> str:
        return "test-model"

    @property
    def embedding_dim(self) -> int:
        return 768


class FakeLLMClient:
    """Фейк-реализация ILLMClient для тестов протоколов."""

    async def generate(self, prompt: str, **kwargs) -> str:
        return "response"

    @property
    def current_provider(self) -> str:
        return "test"
