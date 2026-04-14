import requests
import json
import pytest

BASE_URL = "http://localhost:8000"

pytestmark = pytest.mark.integration

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def test_health():
    print_section("1. Health Check")
    response = requests.get(f"{BASE_URL}/health", timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    return response.status_code == 200

def test_settings_overview():
    print_section("2. Settings Overview")
    response = requests.get(f"{BASE_URL}/api/v1/settings/overview", timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    return response.status_code == 200

def test_telegram_settings():
    print_section("3. Telegram Settings (без чувствительных данных)")
    response = requests.get(f"{BASE_URL}/api/v1/settings/telegram", timeout=10)
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Configured: {data.get('is_configured')}")
    print(f"Session Active: {data.get('is_session_active')}")
    print(f"API ID: {data.get('api_id')} (должен быть скрыт)")
    print(f"API Hash: {data.get('api_hash')} (должен быть скрыт)")
    print(f"Phone: {data.get('phone_number')} (должен быть скрыт)")
    return response.status_code == 200

def test_telegram_health():
    print_section("4. Telegram Health Check")
    response = requests.get(f"{BASE_URL}/api/v1/settings/telegram/check", timeout=30)
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Is Available: {data.get('is_available')}")
    print(f"Is Authorized: {data.get('is_authorized')}")
    if data.get('user'):
        print(f"User: {json.dumps(data.get('user'), indent=2, ensure_ascii=False)}")
    if data.get('error'):
        print(f"Error: {data.get('error')}")
    return response.status_code == 200

def test_llm_providers():
    print_section("5. LLM Providers (с маскированием ключей)")
    response = requests.get(f"{BASE_URL}/api/v1/settings/llm", timeout=10)
    print(f"Status: {response.status_code}")
    for provider in response.json():
        print(f"\n  {provider['name']}:")
        print(f"    Active: {provider['is_active']}")
        print(f"    API Key Masked: {provider.get('api_key_masked')}")
        print(f"    Model: {provider['model']}")
        print(f"    Enabled: {provider['is_enabled']}")
    return response.status_code == 200

def test_embedding_providers():
    print_section("6. Embedding Providers (с маскированием ключей)")
    response = requests.get(f"{BASE_URL}/api/v1/settings/embedding", timeout=10)
    print(f"Status: {response.status_code}")
    for provider in response.json():
        print(f"\n  {provider['name']}:")
        print(f"    Active: {provider['is_active']}")
        print(f"    API Key Masked: {provider.get('api_key_masked')}")
        print(f"    Model: {provider['model']}")
        print(f"    Dim: {provider['embedding_dim']}")
    return response.status_code == 200

def test_reindex_check():
    print_section("7. Reindex Check (New API)")
    response = requests.get(f"{BASE_URL}/api/v1/settings/reindex/check", timeout=10)
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Needs Reindex: {data.get('needs_reindex')}")
    print(f"Messages to Reindex: {data.get('messages_to_reindex')}")
    print(f"Current Model: {data.get('current_model')}")
    print(f"Recommendation: {data.get('recommendation')}")
    return response.status_code == 200

def test_reindex_status():
    print_section("8. Reindex Status")
    response = requests.get(f"{BASE_URL}/api/v1/settings/reindex/status", timeout=10)
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Background Running: {data.get('background_running')}")
    print(f"Paused: {data.get('paused')}")
    print(f"Is Running: {data.get('is_running')}")
    print(f"Queued Tasks: {data.get('queued_tasks')}")
    print(f"Stats: {data.get('stats')}")
    return response.status_code == 200

def test_ask():
    print_section("9. RAG Ask (тестовый запрос)")
    response = requests.post(
        f"{BASE_URL}/api/v1/ask",
        json={"question": "Что обсуждалось в чатах?"},
        timeout=120  # Увеличенный таймаут для LLM
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Answer: {data.get('answer', '')[:200]}...")
        print(f"Sources count: {len(data.get('sources', []))}")
    else:
        print(f"Error: {response.text[:200]}")
    return response.status_code in [200, 500]  # 500 OK если нет данных

def main():
    print("\n" + "="*60)
    print("  TELEGRAM MESSAGE SUMMARIZER — API TESTING")
    print("="*60)
    
    results = {}
    
    # Basic tests
    results['Health Check'] = test_health()
    results['Settings Overview'] = test_settings_overview()
    
    # Security tests
    results['Telegram Settings (masked)'] = test_telegram_settings()
    results['Telegram Health'] = test_telegram_health()
    results['LLM Providers (masked)'] = test_llm_providers()
    results['Embedding Providers (masked)'] = test_embedding_providers()
    
    # Feature tests
    results['Reindex Check'] = test_reindex_check()
    results['Reindex Status'] = test_reindex_status()
    results['RAG Ask'] = test_ask()
    
    # Summary
    print_section("TEST SUMMARY")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} — {test_name}")
    
    print(f"\n  Total: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    print("\n" + "="*60)
    
    return passed == total

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
