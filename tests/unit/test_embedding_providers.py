"""
Тесты для EmbeddingProvidersRepository.

Проверка CRUD операций для провайдеров эмбеддингов.

⚠️ SKIP: Скрипт использует реальную БД. Требует мокификации.
"""

import asyncio
import logging
from unittest.mock import MagicMock, AsyncMock
import asyncpg

import pytest
from src.database import init_db, close_pool
from src.settings.repositories.embedding_providers import EmbeddingProvidersRepository

pytestmark = pytest.mark.skip(reason="Скрипт использует реальную БД — требует мокификации")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def _make_mock_pool() -> MagicMock:
    """Создать мок asyncpg.Pool для тестов."""
    pool = MagicMock(spec=asyncpg.Pool)
    connection = AsyncMock()
    connection.fetchrow = AsyncMock(return_value=None)
    connection.fetch = AsyncMock(return_value=[])
    connection.execute = AsyncMock(return_value="UPDATE")

    class MockAcquireCtx:
        async def __aenter__(self) -> AsyncMock:
            return connection

        async def __aexit__(self, *args: object) -> None:
            return None

    pool.acquire = MagicMock(return_value=MockAcquireCtx())
    return pool


async def test_embedding_providers():
    """Тестирование CRUD операций для провайдеров эмбеддингов."""

    print("=" * 50)
    print("Тесты для EmbeddingProvidersRepository")
    print("=" * 50)

    # Инициализация БД
    print("\n[1] Инициализация БД...")
    try:
        await init_db()
        print("    ✅ Инициализация: OK")
    except Exception as e:
        print(f"    ❌ Инициализация: FAILED - {e}")
        return

    mock_pool = _make_mock_pool()
    repo = EmbeddingProvidersRepository(mock_pool)

    # 1. Создание провайдера Ollama
    print("\n[2] Тест: Создание провайдера Ollama...")
    ollama_provider = await repo.upsert(
        name="ollama",
        is_active=True,
        api_key=None,
        base_url="http://localhost:11434",
        model="nomic-embed-text",
        is_enabled=True,
        priority=1,
        description="Локальный Ollama сервер",
        embedding_dim=768,
        max_retries=3,
        timeout=30,
        normalize=False,
    )

    if ollama_provider:
        print(f"    ✅ Провайдер создан: id={ollama_provider.id}, name={ollama_provider.name}")
        print(f"       URL: {ollama_provider.base_url}, Model: {ollama_provider.model}")
        print(f"       Active: {ollama_provider.is_active}, Dim: {ollama_provider.embedding_dim}")
    else:
        print("    ❌ Ошибка создания провайдера")
        return

    # 2. Создание провайдера Gemini
    print("\n[3] Тест: Создание провайдера Gemini...")
    gemini_provider = await repo.upsert(
        name="gemini",
        is_active=False,
        api_key="test_api_key_12345",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        model="text-embedding-004",
        is_enabled=True,
        priority=2,
        description="Google Gemini Embeddings",
        embedding_dim=768,
        max_retries=3,
        timeout=30,
        normalize=False,
    )

    if gemini_provider:
        print(f"    ✅ Провайдер создан: id={gemini_provider.id}, name={gemini_provider.name}")
        print(f"       API Key: {'***' + gemini_provider.api_key[-5:] if gemini_provider.api_key else 'N/A'}")
    else:
        print("    ❌ Ошибка создания провайдера")

    # 3. Создание провайдера OpenRouter
    print("\n[4] Тест: Создание провайдера OpenRouter...")
    openrouter_provider = await repo.upsert(
        name="openrouter",
        is_active=False,
        api_key="openrouter_key_67890",
        base_url="https://openrouter.ai/api/v1",
        model="openai/text-embedding-3-small",
        is_enabled=True,
        priority=3,
        description="OpenRouter Embeddings",
        embedding_dim=1536,
        max_retries=3,
        timeout=30,
        normalize=True,
    )

    if openrouter_provider:
        print(f"    ✅ Провайдер создан: id={openrouter_provider.id}")
        print(f"       Dim: {openrouter_provider.embedding_dim}, Normalize: {openrouter_provider.normalize}")
    else:
        print("    ❌ Ошибка создания провайдера")

    # 4. Создание провайдера LM Studio
    print("\n[5] Тест: Создание провайдера LM Studio...")
    lmstudio_provider = await repo.upsert(
        name="lm-studio",
        is_active=False,
        api_key="lm_studio_optional_key",
        base_url="http://localhost:1234",
        model="text-embedding-model",
        is_enabled=True,
        priority=4,
        description="Локальный LM Studio",
        embedding_dim=768,
        max_retries=3,
        timeout=30,
        normalize=False,
    )

    if lmstudio_provider:
        print(f"    ✅ Провайдер создан: id={lmstudio_provider.id}")
        print(f"       API Key (опционально): {'***' + lmstudio_provider.api_key[-5:] if lmstudio_provider.api_key else 'N/A'}")
    else:
        print("    ❌ Ошибка создания провайдера")

    # 5. Получение всех провайдеров
    print("\n[6] Тест: Получение всех провайдеров...")
    all_providers = await repo.get_all()
    print(f"    ✅ Получено провайдеров: {len(all_providers)}")
    for p in all_providers:
        active_marker = "🔵" if p.is_active else "⚪"
        enabled_marker = "✅" if p.is_enabled else "❌"
        print(f"       {active_marker} {p.name}: {p.model} (enabled={enabled_marker}, dim={p.embedding_dim})")

    # 6. Получение конкретного провайдера
    print("\n[7] Тест: Получение провайдера по имени (ollama)...")
    provider = await repo.get("ollama")
    if provider:
        print(f"    ✅ Провайдер найден: {provider.name}")
        print(f"       Base URL: {provider.base_url}")
        print(f"       Model: {provider.model}")
    else:
        print("    ❌ Провайдер не найден")

    # 7. Обновление провайдера
    print("\n[8] Тест: Обновление провайдера (изменение параметров)...")
    updated = await repo.update(
        name="ollama",
        is_active=False,  # Деактивируем
        api_key=None,
        base_url="http://localhost:11434",
        model="nomic-embed-text",
        is_enabled=True,
        priority=1,
        description="Обновлённый Ollama",
        embedding_dim=768,
        max_retries=5,
        timeout=60,
        normalize=True,
    )

    if updated:
        print("    ✅ Провайдер обновлён")
        print(f"       Active: {updated.is_active}, Max Retries: {updated.max_retries}")
        print(f"       Timeout: {updated.timeout}, Normalize: {updated.normalize}")
    else:
        print("    ❌ Ошибка обновления")

    # 8. Активация провайдера
    print("\n[9] Тест: Активация провайдера (gemini)...")
    success = await repo.set_active("gemini")
    if success:
        print("    ✅ Провайдер gemini активирован")

        # Проверяем что ollama деактивирован
        ollama = await repo.get("ollama")
        if ollama and not ollama.is_active:
            print("    ✅ Провайдер ollama автоматически деактивирован")

        # Проверяем что gemini активен
        gemini = await repo.get("gemini")
        if gemini and gemini.is_active:
            print("    ✅ Провайдер gemini действительно активен")
    else:
        print("    ❌ Ошибка активации")

    # 9. Получение активного провайдера
    print("\n[10] Тест: Получение активного провайдера...")
    active_provider = await repo.get_active()
    if active_provider:
        print(f"    ✅ Активный провайдер: {active_provider.name}")
        print(f"       Model: {active_provider.model}")
    else:
        print("    ❌ Активный провайдер не найден")

    # 10. Удаление провайдера
    print("\n[11] Тест: Удаление провайдера (openrouter)...")
    deleted = await repo.delete("openrouter")
    if deleted:
        print("    ✅ Провайдер openrouter удалён")

        # Проверяем что удалён
        check = await repo.get("openrouter")
        if not check:
            print("    ✅ Подтверждено: провайдер не найден в БД")
        else:
            print("    ❌ Провайдер всё ещё существует")
    else:
        print("    ❌ Ошибка удаления")

    # 11. Финальная проверка
    print("\n[12] Финальная проверка: список всех провайдеров...")
    final_providers = await repo.get_all()
    print(f"    ✅ Всего провайдеров: {len(final_providers)}")
    for p in final_providers:
        active_marker = "🔵" if p.is_active else "⚪"
        print(f"       {active_marker} {p.name}: {p.model} (dim={p.embedding_dim})")

    print("\n" + "=" * 50)
    print("✅ Все тесты завершены!")
    print("=" * 50)

    # Очистка
    await close_pool()


if __name__ == "__main__":
    asyncio.run(test_embedding_providers())
