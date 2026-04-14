"""
Тесты для App Setting и Webhook Body Template Value Objects.
"""

import pytest

from src.domain.exceptions import ValidationError
from src.domain.value_objects import AppSettingValue, WebhookBodyTemplate


class TestAppSettingValue:
    """Тесты для AppSettingValue Value Object."""

    def test_valid_string_value(self) -> None:
        """Валидное строковое значение."""
        value = AppSettingValue("some_value")
        assert value.value == "some_value"

    def test_none_value(self) -> None:
        """None значение разрешено."""
        value = AppSettingValue(None)
        assert value.value is None

    def test_empty_string_rejected(self) -> None:
        """Пустая строка отклоняется."""
        with pytest.raises(ValidationError, match="AppSettingValue не может быть пустой строкой"):
            AppSettingValue("")

    def test_non_string_rejected(self) -> None:
        """Не-string значение отклоняется."""
        with pytest.raises(ValidationError, match="AppSettingValue должен быть str или None"):
            AppSettingValue(123)  # type: ignore

    def test_int_rejected(self) -> None:
        """Int значение отклоняется."""
        with pytest.raises(ValidationError, match="AppSettingValue должен быть str или None"):
            AppSettingValue(42)  # type: ignore

    def test_bool_rejected(self) -> None:
        """Bool значение отклоняется."""
        with pytest.raises(ValidationError, match="AppSettingValue должен быть str или None"):
            AppSettingValue(True)  # type: ignore

    def test_list_rejected(self) -> None:
        """List значение отклоняется."""
        with pytest.raises(ValidationError, match="AppSettingValue должен быть str или None"):
            AppSettingValue(["value"])  # type: ignore

    def test_dict_rejected(self) -> None:
        """Dict значение отклоняется."""
        with pytest.raises(ValidationError, match="AppSettingValue должен быть str или None"):
            AppSettingValue({"key": "value"})  # type: ignore

    def test_str_representation(self) -> None:
        """Строковое представление."""
        value = AppSettingValue("test_value")
        assert str(value) == "test_value"

    def test_str_representation_none(self) -> None:
        """Строковое представление для None."""
        value = AppSettingValue(None)
        assert str(value) == ""

    def test_equality(self) -> None:
        """Проверка равенства."""
        value1 = AppSettingValue("test")
        value2 = AppSettingValue("test")
        assert value1 == value2

    def test_equality_none(self) -> None:
        """Проверка равенства для None."""
        value1 = AppSettingValue(None)
        value2 = AppSettingValue(None)
        assert value1 == value2

    def test_inequality(self) -> None:
        """Проверка неравенства."""
        value1 = AppSettingValue("test1")
        value2 = AppSettingValue("test2")
        assert value1 != value2

    def test_hash(self) -> None:
        """Проверка хэша."""
        value1 = AppSettingValue("test")
        value2 = AppSettingValue("test")
        assert hash(value1) == hash(value2)

    def test_hash_none(self) -> None:
        """Проверка хэша для None."""
        value1 = AppSettingValue(None)
        value2 = AppSettingValue(None)
        assert hash(value1) == hash(value2)


class TestWebhookBodyTemplate:
    """Тесты для WebhookBodyTemplate Value Object."""

    def test_valid_template_with_summary(self) -> None:
        """Валидный шаблон с summary."""
        template = WebhookBodyTemplate({"summary": "{{summary}}"})
        assert template.template == {"summary": "{{summary}}"}

    def test_valid_template_with_chat_title(self) -> None:
        """Валидный шаблон с chat_title."""
        template = WebhookBodyTemplate({"chat_title": "{{chat_title}}"})
        assert template.template == {"chat_title": "{{chat_title}}"}

    def test_valid_template_with_messages_count(self) -> None:
        """Валидный шаблон с messages_count."""
        template = WebhookBodyTemplate({"messages_count": "{{messages_count}}"})
        assert template.template == {"messages_count": "{{messages_count}}"}

    def test_valid_template_with_period_start(self) -> None:
        """Валидный шаблон с period_start."""
        template = WebhookBodyTemplate({"period_start": "{{period_start}}"})
        assert template.template == {"period_start": "{{period_start}}"}

    def test_valid_template_with_period_end(self) -> None:
        """Валидный шаблон с period_end."""
        template = WebhookBodyTemplate({"period_end": "{{period_end}}"})
        assert template.template == {"period_end": "{{period_end}}"}

    def test_valid_template_with_chat_id(self) -> None:
        """Валидный шаблон с chat_id."""
        template = WebhookBodyTemplate({"chat_id": "{{chat_id}}"})
        assert template.template == {"chat_id": "{{chat_id}}"}

    def test_valid_template_with_message_thread_id(self) -> None:
        """Валидный шаблон с message_thread_id."""
        template = WebhookBodyTemplate({"message_thread_id": "{{message_thread_id}}"})
        assert template.template == {"message_thread_id": "{{message_thread_id}}"}

    def test_valid_template_with_multiple_fields(self) -> None:
        """Валидный шаблон с несколькими полями."""
        template = WebhookBodyTemplate({
            "summary": "{{summary}}",
            "chat_title": "{{chat_title}}",
            "messages_count": "{{messages_count}}",
        })
        assert len(template.template) == 3

    def test_valid_template_with_static_values(self) -> None:
        """Валидный шаблон со статическими значениями."""
        template = WebhookBodyTemplate({"summary": "Static summary text"})
        assert template.template == {"summary": "Static summary text"}

    def test_empty_template_rejected(self) -> None:
        """Пустой шаблон отклоняется."""
        with pytest.raises(ValidationError, match="WebhookBodyTemplate не может быть пустым"):
            WebhookBodyTemplate({})

    def test_non_dict_rejected(self) -> None:
        """Не-dict значение отклоняется."""
        with pytest.raises(ValidationError, match="WebhookBodyTemplate должен быть dict"):
            WebhookBodyTemplate("not a dict")  # type: ignore

    def test_list_rejected(self) -> None:
        """List значение отклоняется."""
        with pytest.raises(ValidationError, match="WebhookBodyTemplate должен быть dict"):
            WebhookBodyTemplate(["item"])  # type: ignore

    def test_none_rejected(self) -> None:
        """None значение отклоняется."""
        with pytest.raises(ValidationError, match="WebhookBodyTemplate должен быть dict"):
            WebhookBodyTemplate(None)  # type: ignore

    def test_int_rejected(self) -> None:
        """Int значение отклоняется."""
        with pytest.raises(ValidationError, match="WebhookBodyTemplate должен быть dict"):
            WebhookBodyTemplate(123)  # type: ignore

    def test_unknown_field_rejected(self) -> None:
        """Неизвестное поле отклоняется."""
        with pytest.raises(ValidationError, match="Неизвестное поле в шаблоне: unknown_field"):
            WebhookBodyTemplate({"unknown_field": "value"})

    def test_multiple_unknown_fields_rejected(self) -> None:
        """Несколько неизвестных полей отклоняются."""
        with pytest.raises(ValidationError, match="Неизвестное поле в шаблоне: invalid"):
            WebhookBodyTemplate({"invalid": "value", "summary": "{{summary}}"})

    def test_mixed_valid_and_unknown_rejected(self) -> None:
        """Смесь валидных и неизвестных полей отклоняется."""
        with pytest.raises(ValidationError, match="Неизвестное поле в шаблоне: extra"):
            WebhookBodyTemplate({
                "summary": "{{summary}}",
                "extra": "not_allowed",
            })

    def test_render_with_variable(self) -> None:
        """Рендеринг шаблона с переменной."""
        template = WebhookBodyTemplate({"summary": "{{summary}}"})
        context: dict[str, object] = {"summary": "Test summary content"}
        result = template.render(context)
        assert result == {"summary": "Test summary content"}

    def test_render_with_multiple_variables(self) -> None:
        """Рендеринг шаблона с несколькими переменными."""
        template = WebhookBodyTemplate({
            "summary": "{{summary}}",
            "chat_title": "{{chat_title}}",
            "messages_count": "{{messages_count}}",
        })
        context: dict[str, object] = {
            "summary": "Daily summary",
            "chat_title": "Test Chat",
            "messages_count": "100",
        }
        result = template.render(context)
        assert result == {
            "summary": "Daily summary",
            "chat_title": "Test Chat",
            "messages_count": "100",
        }

    def test_render_with_static_value(self) -> None:
        """Рендеринг шаблона со статическим значением."""
        template = WebhookBodyTemplate({"summary": "Static notification"})
        context: dict[str, object] = {"chat_title": "Test Chat"}
        result = template.render(context)
        assert result == {"summary": "Static notification"}

    def test_render_with_missing_variable(self) -> None:
        """Рендеринг шаблона с отсутствующей переменной."""
        template = WebhookBodyTemplate({"summary": "{{missing}}"})
        context: dict[str, object] = {"chat_title": "Test Chat"}
        result = template.render(context)
        assert result == {"summary": "{{missing}}"}

    def test_render_mixed_static_and_dynamic(self) -> None:
        """Рендеринг шаблона со смесью статических и динамических значений."""
        template = WebhookBodyTemplate({
            "summary": "{{summary}}",
            "messages_count": "100",
            "chat_title": "{{chat_title}}",
        })
        context: dict[str, object] = {"summary": "Test content", "chat_title": "Test Chat"}
        result = template.render(context)
        assert result == {
            "summary": "Test content",
            "messages_count": "100",
            "chat_title": "Test Chat",
        }

    def test_equality(self) -> None:
        """Проверка равенства."""
        template1 = WebhookBodyTemplate({"summary": "{{summary}}"})
        template2 = WebhookBodyTemplate({"summary": "{{summary}}"})
        assert template1 == template2

    def test_inequality(self) -> None:
        """Проверка неравенства."""
        template1 = WebhookBodyTemplate({"summary": "{{summary}}"})
        template2 = WebhookBodyTemplate({"chat_title": "{{chat_title}}"})
        assert template1 != template2

    def test_hash(self) -> None:
        """Проверка хэша."""
        template1 = WebhookBodyTemplate({"summary": "{{summary}}"})
        template2 = WebhookBodyTemplate({"summary": "{{summary}}"})
        assert hash(template1) == hash(template2)

    def test_old_key_period_rejected(self) -> None:
        """Удалённый ключ period отклоняется."""
        with pytest.raises(ValidationError, match="Неизвестное поле в шаблоне: period"):
            WebhookBodyTemplate({"period": "24h"})

    def test_old_key_chat_name_rejected(self) -> None:
        """Удалённый ключ chat_name отклоняется."""
        with pytest.raises(ValidationError, match="Неизвестное поле в шаблоне: chat_name"):
            WebhookBodyTemplate({"chat_name": "Test Chat"})

    def test_old_key_date_rejected(self) -> None:
        """Удалённый ключ date отклоняется."""
        with pytest.raises(ValidationError, match="Неизвестное поле в шаблоне: date"):
            WebhookBodyTemplate({"date": "2026-04-01"})
