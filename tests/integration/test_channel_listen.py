"""
Тест получения событий из канала.
"""

import logging

import pytest

from telethon import TelegramClient, events

from src.config import Settings

pytestmark = pytest.mark.integration

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = Settings()

API_ID = settings.tg_api_id or 0
API_HASH = settings.tg_api_hash or ""
SESSION = settings.tg_session_name

# Получаем первый чат из настроек для теста
TARGET_CHAT = settings.tg_chat_enable_list[0] if settings.tg_chat_enable_list else None


async def main():
    if not TARGET_CHAT:
        print("❌ TG_CHAT_ENABLE не указан в .env")
        print("   Добавьте TG_CHAT_ENABLE=-1001234567890 в .env для тестирования")
        return

    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        print("❌ Не авторизован")
        return

    print("=" * 60)
    print(f"Ожидание сообщений из канала {TARGET_CHAT}...")
    print("Отправьте сообщение в канал, указанный в TG_CHAT_IDS")
    print("Нажмите Ctrl+C для выхода")
    print("=" * 60)

    @client.on(events.NewMessage(chats=[TARGET_CHAT]))
    async def handler(event):
        print("\n✅ ПОЛУЧЕНО СООБЩЕНИЕ!")
        print(f"   Chat ID: {event.chat_id}")
        print(f"   From: {event.sender_id}")
        print(f"   Text: {event.text[:100]}")
        print(f"   ID: {event.id}")

    # Ожидание событий
    try:
        await client.run_until_disconnected()
    except KeyboardInterrupt:
        print("\nОстановка...")
    finally:
        await client.disconnect()
