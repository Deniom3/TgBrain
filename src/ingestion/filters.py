"""
Ingestion — фильтрация сообщений из Telegram.
"""

import re
from typing import Tuple

# Паттерны для определения рекламы
AD_PATTERNS = [
    r'реклама',
    r'промо',
    r'erid\s*[:=]?\s*\w+',
    r'подписывайтесь?\s+(на|канал)',
    r'спонсор',
    r'партнёрство',
    r'@\w+\s*-\s*(канал|бот|чат)',
    r'@\w+\s+(канал|бот|чат)',
    r'реклама\s+в\s+telegram',
    r'продвижение\s+(каналов?|чатов?)',
]

AD_REGEX = re.compile('|'.join(AD_PATTERNS), re.IGNORECASE)

# Минимальная длина сообщения для обработки
MIN_MESSAGE_LENGTH = 15


def is_advertisement(text: str) -> bool:
    """
    Проверка текста на рекламу.

    Args:
        text: Текст для проверки.

    Returns:
        True если текст содержит рекламу.
    """
    return bool(AD_REGEX.search(text.lower()))


def should_process_message(
    text: str,
    is_bot: bool,
    is_action: bool
) -> Tuple[bool, str]:
    """
    Проверка, должно ли сообщение быть обработано.

    Args:
        text: Текст сообщения.
        is_bot: Отправлено ли ботом.
        is_action: Является ли действием.

    Returns:
        Кортеж (должно_ли_обрабатывать, причина_отклонения).
    """
    if is_bot:
        return False, "bot"

    if is_action:
        return False, "action"

    text = text.strip()
    if not text or len(text) < MIN_MESSAGE_LENGTH:
        return False, f"short ({len(text)} chars)"

    if is_advertisement(text):
        return False, "advertisement"

    return True, ""
