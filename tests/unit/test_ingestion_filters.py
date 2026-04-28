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

    def test_bot_allowed_filter_bots_false(self):
        """
        Бот пропускается, если filter_bots=False.

        Проверяет:
        - is_bot=True, filter_bots=False → (True, "")
        """
        should, reason = should_process_message(
            "this is a normal length message", is_bot=True, is_action=False,
            filter_bots=False,
        )
        assert should is True
        assert reason == ""

    def test_action_allowed_filter_actions_false(self):
        """
        Action пропускается, если filter_actions=False.

        Проверяет:
        - is_action=True, filter_actions=False → (True, "")
        """
        should, reason = should_process_message(
            "this is a normal length message", is_bot=False, is_action=True,
            filter_actions=False,
        )
        assert should is True
        assert reason == ""

    def test_length_zero_disables_filter(self):
        """
        filter_min_length=0 отключает фильтр длины.

        Проверяет:
        - Короткий текст при filter_min_length=0 → (True, "")
        """
        should, reason = should_process_message(
            "hi", is_bot=False, is_action=False,
            filter_min_length=0,
        )
        assert should is True
        assert reason == ""

    def test_length_custom_min(self):
        """
        Произвольное значение filter_min_length отклоняет короткий текст.

        Проверяет:
        - Текст короче filter_min_length → (False, "short ...")
        """
        should, reason = should_process_message(
            "hi", is_bot=False, is_action=False,
            filter_min_length=5,
        )
        assert should is False
        assert "short" in reason

    def test_ads_disabled_filter_ads_false(self):
        """
        Рекламный текст пропускается, если filter_ads=False.

        Проверяет:
        - Реклама при filter_ads=False → (True, "")
        """
        should, reason = should_process_message(
            "реклама подписывайтесь на канал", is_bot=False, is_action=False,
            filter_ads=False,
        )
        assert should is True
        assert reason == ""

    def test_bot_allowed_action_still_filtered(self):
        """
        Бот пропущен (filter_bots=False), но action отклонён (filter_actions=True).

        Проверяет:
        - is_bot=True, is_action=True, filter_bots=False, filter_actions=True → (False, "action")
        """
        should, reason = should_process_message(
            "test", is_bot=True, is_action=True,
            filter_bots=False, filter_actions=True,
        )
        assert should is False
        assert reason == "action"

    def test_bot_allowed_short_filtered(self):
        """
        Бот пропущен (filter_bots=False), но короткий текст отклонён.

        Проверяет:
        - is_bot=True, filter_bots=False, короткий текст → (False, "short ...")
        """
        should, reason = should_process_message(
            "", is_bot=True, is_action=False,
            filter_bots=False, filter_min_length=15,
        )
        assert should is False
        assert "short" in reason

    def test_all_filters_disabled(self):
        """
        Все фильтры отключены — любое сообщение пропускается.

        Проверяет:
        - Бот + action + реклама + короткий текст, все фильтры=False → (True, "")
        """
        should, reason = should_process_message(
            "реклама", is_bot=True, is_action=True,
            filter_bots=False, filter_actions=False,
            filter_min_length=0, filter_ads=False,
        )
        assert should is True
        assert reason == ""
