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
    is_action: bool,
    filter_bots: bool = True,
    filter_actions: bool = True,
    filter_min_length: int = 15,
    filter_ads: bool = True,
) -> Tuple[bool, str]:
    """
    Проверка, должно ли сообщение быть обработано.

    Args:
        text: Текст сообщения.
        is_bot: Отправлено ли ботом.
        is_action: Является ли действием.
        filter_bots: Фильтровать сообщения от ботов.
        filter_actions: Фильтровать служебные действия.
        filter_min_length: Минимальная длина сообщения (0 — отключить).
        filter_ads: Фильтровать рекламные сообщения.

    Returns:
        Кортеж (должно_ли_обрабатывать, причина_отклонения).
    """
    if is_bot and filter_bots:
        return False, "bot"

    if is_action and filter_actions:
        return False, "action"

    if filter_min_length > 0 and (not text or len(text.strip()) < filter_min_length):
        return False, f"short ({len(text.strip())} chars)"

    if filter_ads and is_advertisement(text):
        return False, "advertisement"

    return True, ""
