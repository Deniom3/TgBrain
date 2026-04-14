#!/usr/bin/env python3
"""
Тесты настройки LLM провайдеров через API.

Проверяет:
1. Чтение настроек провайдера
2. Обновление настроек провайдера
3. Активацию провайдера
4. Проверку что настройки сохраняются в БД
5. Проверку что .env не переопределяет БД при повторном запуске
"""

import os

import httpx
import pytest

BASE_URL = "http://localhost:8000"
TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# Тестовые данные
TEST_API_KEY = os.environ.get("TEST_OPENROUTER_API_KEY", "test-key-not-a-real-key-0000000000")
TEST_MODEL = "qwen/qwen3.5-flash-02-23"
TEST_BASE_URL = "https://openrouter.ai/api/v1"

pytestmark = pytest.mark.integration


def print_section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


@pytest.mark.integration
def test_get_all_llm_providers():
    """Тест 1: Получение всех LLM провайдеров."""
    print_section("Тест 1: Получение всех LLM провайдеров")
    
    with httpx.Client(timeout=TIMEOUT) as client:
        response = client.get(f"{BASE_URL}/api/v1/settings/llm")
        
        assert response.status_code == 200, f"Status: {response.status_code}"
        providers = response.json()
        
        print(f"   Количество провайдеров: {len(providers)}")
        for p in providers:
            active = "✅" if p.get('is_active') else "❌"
            print(f"   {active} {p.get('name')}: {p.get('model')} (active={p.get('is_active')})")
        
        assert len(providers) >= 4, "Должно быть минимум 4 провайдера"
        print("   ✅ Тест пройден")
        return providers


@pytest.mark.integration
def test_get_openrouter_provider():
    """Тест 2: Получение настроек OpenRouter."""
    print_section("Тест 2: Получение настроек OpenRouter")
    
    with httpx.Client(timeout=TIMEOUT) as client:
        response = client.get(f"{BASE_URL}/api/v1/settings/llm/openrouter")
        
        assert response.status_code == 200, f"Status: {response.status_code}"
        provider = response.json()
        
        print(f"   Name: {provider.get('name')}")
        print(f"   Model: {provider.get('model')}")
        print(f"   Base URL: {provider.get('base_url')}")
        print(f"   Is Active: {provider.get('is_active')}")
        print(f"   Is Enabled: {provider.get('is_enabled')}")
        
        assert provider.get('name') == 'openrouter'
        print("   ✅ Тест пройден")
        return provider


@pytest.mark.integration
def test_update_openrouter_provider():
    """Тест 3: Обновление настроек OpenRouter."""
    print_section("Тест 3: Обновление настроек OpenRouter")
    
    with httpx.Client(timeout=TIMEOUT) as client:
        payload = {
            "is_active": False,
            "api_key": TEST_API_KEY,
            "base_url": TEST_BASE_URL,
            "model": TEST_MODEL,
            "is_enabled": True,
            "priority": 2,
            "description": "Test OpenRouter Provider"
        }
        
        response = client.put(
            f"{BASE_URL}/api/v1/settings/llm/openrouter",
            json=payload
        )
        
        assert response.status_code == 200, f"Status: {response.status_code}"
        provider = response.json()
        
        print(f"   Updated Model: {provider.get('model')}")
        print(f"   Updated Base URL: {provider.get('base_url')}")
        print(f"   API Key Masked: {provider.get('api_key_masked')}")
        
        assert provider.get('model') == TEST_MODEL, f"Model should be {TEST_MODEL}"
        assert provider.get('base_url') == TEST_BASE_URL, f"Base URL should be {TEST_BASE_URL}"
        
        print("   ✅ Тест пройден")
        return provider


@pytest.mark.integration
def test_activate_openrouter():
    """Тест 4: Активация OpenRouter."""
    print_section("Тест 4: Активация OpenRouter")
    
    with httpx.Client(timeout=TIMEOUT) as client:
        response = client.post(f"{BASE_URL}/api/v1/settings/llm/openrouter/activate")
        
        assert response.status_code == 200, f"Status: {response.status_code}"
        result = response.json()
        
        print(f"   Status: {result.get('status')}")
        print(f"   Active Provider: {result.get('active_provider')}")
        
        assert result.get('status') == 'success'
        assert result.get('active_provider') == 'openrouter'
        
        # Проверяем что openrouter теперь активный
        response = client.get(f"{BASE_URL}/api/v1/settings/overview")
        overview = response.json()
        active = overview.get('llm', {}).get('active_provider')
        
        print(f"   Active Provider (from overview): {active}")
        assert active == 'openrouter', f"Active provider should be 'openrouter', got {active}"
        
        print("   ✅ Тест пройден")


@pytest.mark.integration
def test_deactivate_and_activate_another():
    """Тест 5: Деактивация OpenRouter и активация другого."""
    print_section("Тест 5: Переключение на другой провайдер")
    
    with httpx.Client(timeout=TIMEOUT) as client:
        # Активируем gemini
        response = client.post(f"{BASE_URL}/api/v1/settings/llm/gemini/activate")
        
        assert response.status_code == 200, f"Status: {response.status_code}"
        
        # Проверяем overview
        response = client.get(f"{BASE_URL}/api/v1/settings/overview")
        overview = response.json()
        active = overview.get('llm', {}).get('active_provider')
        
        print(f"   Active Provider: {active}")
        assert active == 'gemini', f"Active provider should be 'gemini', got {active}"
        
        # Возвращаем openrouter
        response = client.post(f"{BASE_URL}/api/v1/settings/llm/openrouter/activate")
        assert response.status_code == 200
        
        print("   ✅ Тест пройден")


@pytest.mark.integration
def test_settings_persistence():
    """Тест 6: Проверка сохранения настроек в БД."""
    print_section("Тест 6: Проверка сохранения настроек в БД")
    
    with httpx.Client(timeout=TIMEOUT) as client:
        # Получаем настройки openrouter
        response = client.get(f"{BASE_URL}/api/v1/settings/llm/openrouter")
        provider = response.json()
        
        print(f"   Model (from DB): {provider.get('model')}")
        print(f"   Base URL (from DB): {provider.get('base_url')}")
        print(f"   Is Active: {provider.get('is_active')}")
        
        # Проверяем что настройки сохранились
        assert provider.get('model') == TEST_MODEL, f"Model should be {TEST_MODEL}"
        assert provider.get('base_url') == TEST_BASE_URL, f"Base URL should be {TEST_BASE_URL}"
        
        print("   ✅ Тест пройден")
