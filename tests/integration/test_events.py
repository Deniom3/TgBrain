"""
Тест получения событий с подробным логированием.
"""

import logging

import pytest

from telethon import TelegramClient, events

from src.config import Settings

pytestmark = pytest.mark.integration

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = Settings()

API_ID = settings.tg_api_id or 0
API_HASH = settings.tg_api_hash or ""
SESSION = settings.tg_session_name

# Чаты для мониторинга из настроек
TARGET_CHATS = settings.tg_chat_enable_list if settings.tg_chat_enable_list else []


async def main():
    if not TARGET_CHATS:
        print("❌ TG_CHAT_ENABLE не указан в .env")
        print("   Добавьте TG_CHAT_ENABLE=-1001234567890 в .env для тестирования")
        return

    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        print("❌ Не авторизован")
        return

    print("=" * 70)
    print(f"Ожидание сообщений из чатов: {TARGET_CHATS}")
    print("Отправьте сообщение в чаты, указанные в TG_CHAT_ENABLE")
    print("Нажмите Ctrl+C для выхода")
    print("=" * 70)

    @client.on(events.NewMessage())
    async def handler(event):
        chat_id = event.chat_id
        sender_id = event.sender_id
        text = event.text[:50] if event.text else "(медиа)"
        is_out = "📤" if event.out else "📥"

        print(f"\n{is_out} СОБЫТИЕ ПОЛУЧЕНО!")
        print(f"   Chat ID: {chat_id}")
        print(f"   Sender ID: {sender_id}")
        print(f"   Text: {text}")
        print(f"   In targets: {chat_id in TARGET_CHATS or (sender_id and sender_id in TARGET_CHATS)}")

        # Проверка фильтрации
        if chat_id in TARGET_CHATS:
            print("   ✅ Chat ID в списке мониторинга")
        if sender_id and sender_id in TARGET_CHATS:
            print("   ✅ Sender ID в списке мониторинга")

    # Ожидание событий
    try:
        await client.run_until_disconnected()
    except KeyboardInterrupt:
        print("\nОстановка...")
    finally:
        await client.disconnect()
