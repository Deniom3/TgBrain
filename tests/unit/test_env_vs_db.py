#!/usr/bin/env python3
"""
Тест проверки что .env не переопределяет настройки БД.

Сценарий:
1. Обновляем настройки через API (модель = test-model-v1)
2. Меняем .env (модель = test-model-v2)
3. Перезапускаем приложение
4. Проверяем что осталась модель из БД (test-model-v1), а не из .env
"""

import sys
import time

import httpx

BASE_URL = "http://localhost:8000"
TIMEOUT = httpx.Timeout(60.0, connect=10.0)


def print_section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def get_current_model():
    """Получить текущую модель OpenRouter."""
    with httpx.Client(timeout=TIMEOUT) as client:
        response = client.get(f"{BASE_URL}/api/v1/settings/llm/openrouter")
        if response.status_code == 200:
            return response.json().get('model')
    return None


def update_model(model: str):
    """Обновить модель через API."""
    with httpx.Client(timeout=TIMEOUT) as client:
        payload = {
            "is_active": True,
            "api_key": "sk-or-v1-test",
            "base_url": "https://openrouter.ai/api/v1",
            "model": model,
            "is_enabled": True,
            "priority": 2,
            "description": "Test"
        }
        response = client.put(
            f"{BASE_URL}/api/v1/settings/llm/openrouter",
            json=payload
        )
        return response.status_code == 200


def main():
    print_section("ТЕСТ: .env НЕ переопределяет БД")
    
    # Шаг 1: Получаем текущую модель
    print("Шаг 1: Получение текущей модели...")
    initial_model = get_current_model()
    print(f"   Текущая модель: {initial_model}")
    
    # Шаг 2: Обновляем модель через API
    test_model = "test-model-from-api-v1"
    print(f"\nШаг 2: Обновление модели через API на '{test_model}'...")
    if update_model(test_model):
        print("   ✅ Модель обновлена")
    else:
        print("   ❌ Ошибка обновления")
        return False
    
    # Шаг 3: Проверяем что модель сохранилась
    print("\nШаг 3: Проверка сохранения...")
    time.sleep(1)
    saved_model = get_current_model()
    print(f"   Сохранённая модель: {saved_model}")
    
    if saved_model != test_model:
        print(f"   ❌ Модель не сохранилась! Ожидалось '{test_model}', получено '{saved_model}'")
        return False
    print("   ✅ Модель сохранилась")
    
    # Шаг 4: Инструкция для пользователя
    print("\n" + "=" * 60)
    print("  ШАГ 4: ТРЕБУЕТСЯ ДЕЙСТВИЕ ПОЛЬЗОВАТЕЛЯ")
    print("=" * 60)
    print(f"""
  Текущая модель в БД: {saved_model}
  
  1. Откройте .env файл
  2. Найдите строку OPENROUTER_MODEL
  3. Измените на: OPENROUTER_MODEL=env-model-v2
  4. Сохраните файл
  5. Перезапустите приложение:
     docker-compose restart app
  6. Подождите 15 секунд
  7. Нажмите Enter для продолжения теста
  """)
    
    input("   Нажмите Enter когда перезапустите приложение...")
    
    # Шаг 5: Проверяем что модель осталась из БД
    print("\nШаг 5: Проверка после перезапуска...")
    time.sleep(2)
    final_model = get_current_model()
    print(f"   Модель после рестарта: {final_model}")
    
    if final_model == test_model:
        print(f"\n   ✅ УСПЕХ! Модель осталась из БД ({test_model})")
        print("   .env НЕ переопределил настройки БД")
        return True
    elif final_model == "env-model-v2":
        print(f"\n   ❌ ПРОБЛЕМА! Модель из .env ({final_model}) переопределила БД")
        print(f"   Ожидалось: {test_model}")
        return False
    else:
        print(f"\n   ⚠️ Неизвестная модель: {final_model}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("  ТЕСТ ПРИОРИТЕТА БД НАД .ENV")
    print("=" * 60)
    
    try:
        success = main()
        
        print("\n" + "=" * 60)
        if success:
            print("  ✅ ТЕСТ ПРОЙДЕН")
        else:
            print("  ❌ ТЕСТ НЕ ПРОЙДЕН")
        print("=" * 60)
        
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n   ❌ Ошибка: {e}")
        sys.exit(1)
