"""
Модульные тесты для модуля filters.

Тестируют функции фильтрации сообщений:
- is_advertisement() — определение рекламы
- should_process_message() — решение об обработке
"""

import pytest

from src.ingestion.filters import is_advertisement, should_process_message


class TestIsAdvertisement:
    """Тесты функции is_advertisement."""

    @pytest.mark.parametrize(
        "text",
        [
            "Реклама лучшего курса программирования",
            "Промо-код на скидку 50%",
            "Спонсор выпуска — компания TechCorp",
            "Партнёрство с ведущим брендом",
            "Подписывайтесь на наш канал",
            "Подписывайтесь на канал @tech_news",
            "@channel_bot - канал новостей",
            "@promo_bot канал скидок",
            "erid: abc123def456",
            "erid=xyz789",
            "Реклама в Telegram",
            "Продвижение каналов в соцсетях",
            "Продвижение чатов и групп",
        ],
    )
    def test_is_advertisement_true_patterns(self, text):
        """
        Определяет рекламные паттерны в тексте.

        Проверяет:
        - Все известные рекламные паттерны определяются как реклама
        """
        assert is_advertisement(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "Привет, как дела?",
            "Сегодня отличный день для программирования",
            "Кто-нибудь знает решение этой задачи?",
            "Просто обычный текст без рекламы",
            "Обсуждаем последние новости технологии",
            "Пожалуйста, помогите с кодом",
        ],
    )
    def test_is_advertisement_false(self, text):
        """
        Обычный текст не определяется как реклама.

        Проверяет:
        - Нейтральный текст возвращает False
        """
        assert is_advertisement(text) is False

    def test_is_advertisement_case_insensitive(self):
        """
        Проверка регистронезависимости.

        Проверяет:
        - РЕКЛАМА, реклама, Реклама — все определяются одинаково
        """
        assert is_advertisement("РЕКЛАМА лучшего продукта") is True
        assert is_advertisement("реклама лучшего продукта") is True
        assert is_advertisement("Реклама лучшего продукта") is True


class TestShouldProcessMessage:
    """Тесты функции should_process_message."""

    def test_should_process_bot_rejected(self):
        """
        Сообщения от ботов отклоняются.

        Проверяет:
        - is_bot=True → (False, "bot")
        """
        result = should_process_message(
            text="Это длинное сообщение от бота для тестирования",
            is_bot=True,
            is_action=False,
        )
        assert result == (False, "bot")

    def test_should_process_action_rejected(self):
        """
        Action сообщения отклоняются.

        Проверяет:
        - is_action=True → (False, "action")
        """
        result = should_process_message(
            text="Это длинное сообщение действие для тестирования",
            is_bot=False,
            is_action=True,
        )
        assert result == (False, "action")

    def test_should_process_short_rejected(self):
        """
        Короткие сообщения (< 15 символов) отклоняются.

        Проверяет:
        - Текст короче 15 символов → (False, "short (...)")
        """
        result = should_process_message(
            text="Короткое",
            is_bot=False,
            is_action=False,
        )
        assert result[0] is False
        assert result[1].startswith("short (")

    def test_should_process_empty_rejected(self):
        """
        Пустые сообщения и только пробелы отклоняются.

        Проверяет:
        - Пустая строка → (False, "short (...)")
        - Строка из пробелов → (False, "short (...)")
        """
        result = should_process_message(
            text="",
            is_bot=False,
            is_action=False,
        )
        assert result[0] is False
        assert result[1].startswith("short (")

        result = should_process_message(
            text="   ",
            is_bot=False,
            is_action=False,
        )
        assert result[0] is False
        assert result[1].startswith("short (")

    def test_should_process_advertisement_rejected(self):
        """
        Рекламные сообщения отклоняются.

        Проверяет:
        - Текст с рекламными паттернами → (False, "advertisement")
        """
        result = should_process_message(
            text="Реклама лучшего курса программирования и разработки",
            is_bot=False,
            is_action=False,
        )
        assert result == (False, "advertisement")

    def test_should_process_valid_accepted(self):
        """
        Валидное сообщение принимается.

        Проверяет:
        - Обычный текст достаточной длины → (True, "")
        """
        result = should_process_message(
            text="Это совершенно обычное сообщение для проверки работы функции обработки",
            is_bot=False,
            is_action=False,
        )
        assert result == (True, "")
