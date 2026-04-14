"""
Тесты для TemplateEngine — шаблонизация {{variable}}.
"""

from typing import Any

from src.webhook.template_engine import TemplateEngine


class TestTemplateEngineRender:
    """Тесты метода render для строк."""

    def test_render_single_variable(self) -> None:
        """Замена одной переменной."""
        template = "Hello, {{name}}!"
        result = TemplateEngine.render(template, name="World")
        assert result == "Hello, World!"

    def test_render_multiple_variables(self) -> None:
        """Замена нескольких переменных."""
        template = "{{greeting}}, {{name}}!"
        result = TemplateEngine.render(template, greeting="Hello", name="World")
        assert result == "Hello, World!"

    def test_render_same_variable_twice(self) -> None:
        """Одна переменная используется несколько раз."""
        template = "{{name}} says hello to {{name}}"
        result = TemplateEngine.render(template, name="Alice")
        assert result == "Alice says hello to Alice"

    def test_render_no_variables(self) -> None:
        """Шаблон без переменных."""
        template = "Hello, World!"
        result = TemplateEngine.render(template)
        assert result == "Hello, World!"

    def test_render_unused_variables(self) -> None:
        """Переменные в context не используются в шаблоне."""
        template = "Hello, World!"
        result = TemplateEngine.render(template, unused="value")
        assert result == "Hello, World!"

    def test_render_integer_variable(self) -> None:
        """Переменная типа int."""
        template = "Count: {{count}}"
        result = TemplateEngine.render(template, count=42)
        assert result == "Count: 42"

    def test_render_float_variable(self) -> None:
        """Переменная типа float."""
        template = "Price: {{price}}"
        result = TemplateEngine.render(template, price=19.99)
        assert result == "Price: 19.99"

    def test_render_boolean_variable(self) -> None:
        """Переменная типа bool."""
        template = "Enabled: {{enabled}}"
        result = TemplateEngine.render(template, enabled=True)
        assert result == "Enabled: True"

    def test_render_none_variable(self) -> None:
        """Переменная типа None заменяется на пустую строку."""
        template = "Value: {{value}}"
        result = TemplateEngine.render(template, value=None)
        assert result == "Value: "

    def test_render_empty_string_variable(self) -> None:
        """Пустая строка в переменной."""
        template = "Text: {{text}}"
        result = TemplateEngine.render(template, text="")
        assert result == "Text: "

    def test_render_variable_with_special_chars(self) -> None:
        """Переменная со специальными символами."""
        template = "URL: {{url}}"
        result = TemplateEngine.render(
            template, url="https://example.com/path?query=1"
        )
        assert result == "URL: https://example.com/path?query=1"

    def test_render_variable_with_newlines(self) -> None:
        """Переменная с переносами строк."""
        template = "Summary: {{summary}}"
        result = TemplateEngine.render(template, summary="Line1\nLine2")
        assert result == "Summary: Line1\nLine2"

    def test_render_partial_match_not_replaced(self) -> None:
        """Частичное совпадение не заменяется."""
        template = "{{name}} and {{nam}}"
        result = TemplateEngine.render(template, name="Alice")
        assert result == "Alice and {{nam}}"

    def test_render_nested_braces_not_replaced(self) -> None:
        """Вложенные фигурные скобки не заменяются."""
        template = "{{{name}}}"
        result = TemplateEngine.render(template, name="Alice")
        assert result == "{Alice}"

    def test_render_string_result_converted_to_int(self) -> None:
        """Строковый результат '123' конвертируется в int."""
        template = "{{value}}"
        result = TemplateEngine.render(template, value="123")
        assert result == 123
        assert isinstance(result, int)

    def test_render_string_result_converted_to_negative_int(self) -> None:
        """Строковый результат '-456' конвертируется в int."""
        template = "{{value}}"
        result = TemplateEngine.render(template, value="-456")
        assert result == -456
        assert isinstance(result, int)

    def test_render_string_result_converted_to_positive_int(self) -> None:
        """Строковый результат '+789' конвертируется в int."""
        template = "{{value}}"
        result = TemplateEngine.render(template, value="+789")
        assert result == 789
        assert isinstance(result, int)

    def test_render_string_result_converted_to_float(self) -> None:
        """Строковый результат '12.34' конвертируется в float."""
        template = "{{value}}"
        result = TemplateEngine.render(template, value="12.34")
        assert result == 12.34
        assert isinstance(result, float)

    def test_render_string_result_converted_to_negative_float(self) -> None:
        """Строковый результат '-56.78' конвертируется в float."""
        template = "{{value}}"
        result = TemplateEngine.render(template, value="-56.78")
        assert result == -56.78
        assert isinstance(result, float)

    def test_render_string_result_converted_to_positive_float(self) -> None:
        """Строковый результат '+90.12' конвертируется в float."""
        template = "{{value}}"
        result = TemplateEngine.render(template, value="+90.12")
        assert result == 90.12
        assert isinstance(result, float)

    def test_render_string_result_not_converted_if_contains_text(self) -> None:
        """Строка с текстом не конвертируется."""
        template = "{{value}}"
        result = TemplateEngine.render(template, value="123abc")
        assert result == "123abc"
        assert isinstance(result, str)

    def test_render_string_result_not_converted_if_decimal_only(self) -> None:
        """Строка '.123' не конвертируется (нет цифры перед точкой)."""
        template = "{{value}}"
        result = TemplateEngine.render(template, value=".123")
        assert result == ".123"
        assert isinstance(result, str)

    def test_render_string_result_not_converted_if_trailing_dot(self) -> None:
        """Строка '123.' не конвертируется (нет цифры после точки)."""
        template = "{{value}}"
        result = TemplateEngine.render(template, value="123.")
        assert result == "123."
        assert isinstance(result, str)

    def test_render_string_result_not_converted_if_empty(self) -> None:
        """Пустая строка не конвертируется."""
        template = "{{value}}"
        result = TemplateEngine.render(template, value="")
        assert result == ""
        assert isinstance(result, str)

    def test_render_chat_id_use_case(self) -> None:
        """Use case: chat_id для Telegram API должен быть int."""
        template = "{{chat_id}}"
        result = TemplateEngine.render(template, chat_id="-1001234567890")
        assert result == -1001234567890
        assert isinstance(result, int)

    def test_render_mixed_text_and_number_not_converted(self) -> None:
        """Текст с числом внутри не конвертируется."""
        template = "Chat ID: {{chat_id}}"
        result = TemplateEngine.render(template, chat_id="12345")
        assert result == "Chat ID: 12345"
        assert isinstance(result, str)


class TestTemplateEngineRenderDict:
    """Тесты метода render_dict для словарей."""

    def test_render_dict_flat(self) -> None:
        """Плоский словарь."""
        template_dict = {"key1": "{{value1}}", "key2": "{{value2}}"}
        result = TemplateEngine.render_dict(template_dict, value1="A", value2="B")
        assert result == {"key1": "A", "key2": "B"}

    def test_render_dict_nested(self) -> None:
        """Вложенный словарь."""
        template_dict = {
            "outer": {"inner": "{{value}}"}
        }
        result = TemplateEngine.render_dict(template_dict, value="X")
        assert result == {"outer": {"inner": "X"}}

    def test_render_dict_with_list(self) -> None:
        """Словарь со списком."""
        template_dict = {"items": ["{{item1}}", "{{item2}}"]}
        result = TemplateEngine.render_dict(template_dict, item1="A", item2="B")
        assert result == {"items": ["A", "B"]}

    def test_render_dict_non_string_values(self) -> None:
        """Нестроковые значения."""
        template_dict = {"count": 42, "enabled": True, "price": 19.99}
        result = TemplateEngine.render_dict(template_dict)
        assert result == {"count": 42, "enabled": True, "price": 19.99}

    def test_render_dict_empty(self) -> None:
        """Пустой словарь."""
        template_dict: dict = {}
        result = TemplateEngine.render_dict(template_dict)
        assert result == {}

    def test_render_dict_deeply_nested(self) -> None:
        """Глубоко вложенный словарь."""
        template_dict = {
            "level1": {
                "level2": {
                    "level3": "{{value}}"
                }
            }
        }
        result = TemplateEngine.render_dict(template_dict, value="deep")
        assert result == {"level1": {"level2": {"level3": "deep"}}}

    def test_render_dict_string_number_converted_to_int(self) -> None:
        """Строковое число в dict конвертируется в int."""
        template_dict = {"chat_id": "{{value}}"}
        result = TemplateEngine.render_dict(template_dict, value="12345")
        assert result == {"chat_id": 12345}
        assert isinstance(result["chat_id"], int)

    def test_render_dict_string_number_converted_to_float(self) -> None:
        """Строковое число с точкой в dict конвертируется в float."""
        template_dict = {"price": "{{value}}"}
        result = TemplateEngine.render_dict(template_dict, value="19.99")
        assert result == {"price": 19.99}
        assert isinstance(result["price"], float)

    def test_render_dict_nested_string_number_converted(self) -> None:
        """Строковое число во вложенном dict конвертируется."""
        template_dict = {
            "telegram": {
                "chat_id": "{{chat_id}}"
            }
        }
        result = TemplateEngine.render_dict(template_dict, chat_id="-1001234567890")
        assert result == {"telegram": {"chat_id": -1001234567890}}
        assert isinstance(result["telegram"]["chat_id"], int)

    def test_render_dict_mixed_types(self) -> None:
        """Dict со смешанными типами данных."""
        template_dict: dict[str, Any] = {
            "chat_id": "{{chat_id}}",
            "text": "{{text}}",
            "price": "{{price}}",
            "count": "42"
        }
        result = TemplateEngine.render_dict(
            template_dict,
            chat_id="12345",
            text="Hello",
            price="99.99"
        )
        assert result == {
            "chat_id": 12345,
            "text": "Hello",
            "price": 99.99,
            "count": 42
        }
        assert isinstance(result["chat_id"], int)
        assert isinstance(result["text"], str)
        assert isinstance(result["price"], float)
        assert isinstance(result["count"], int)


class TestTemplateEngineRenderList:
    """Тесты метода render_list для списков."""

    def test_render_list_flat(self) -> None:
        """Плоский список."""
        template_list = ["{{item1}}", "{{item2}}"]
        result = TemplateEngine.render_list(template_list, item1="A", item2="B")
        assert result == ["A", "B"]

    def test_render_list_with_dict(self) -> None:
        """Список со словарями."""
        template_list = [{"key": "{{value}}"}]
        result = TemplateEngine.render_list(template_list, value="X")
        assert result == [{"key": "X"}]

    def test_render_list_nested(self) -> None:
        """Вложенный список."""
        template_list = [["{{item}}"]]
        result = TemplateEngine.render_list(template_list, item="X")
        assert result == [["X"]]

    def test_render_list_non_string_values(self) -> None:
        """Нестроковые значения."""
        template_list = [42, True, 19.99, None]
        result = TemplateEngine.render_list(template_list)
        assert result == [42, True, 19.99, None]

    def test_render_list_empty(self) -> None:
        """Пустой список."""
        template_list: list = []
        result = TemplateEngine.render_list(template_list)
        assert result == []

    def test_render_list_string_number_converted_to_int(self) -> None:
        """Строковое число в list конвертируется в int."""
        template_list = ["{{value}}"]
        result = TemplateEngine.render_list(template_list, value="123")
        assert result == [123]
        assert isinstance(result[0], int)

    def test_render_list_string_number_converted_to_float(self) -> None:
        """Строковое число с точкой в list конвертируется в float."""
        template_list = ["{{value}}"]
        result = TemplateEngine.render_list(template_list, value="45.67")
        assert result == [45.67]
        assert isinstance(result[0], float)

    def test_render_list_multiple_numbers(self) -> None:
        """Список с несколькими числами."""
        template_list = ["{{a}}", "{{b}}", "{{c}}"]
        result = TemplateEngine.render_list(template_list, a="1", b="2.5", c="3")
        assert result == [1, 2.5, 3]
        assert isinstance(result[0], int)
        assert isinstance(result[1], float)
        assert isinstance(result[2], int)

    def test_render_list_mixed_text_and_numbers(self) -> None:
        """Список с текстом и числами."""
        template_list = ["{{text}}", "{{number}}"]
        result = TemplateEngine.render_list(template_list, text="hello", number="42")
        assert result == ["hello", 42]
        assert isinstance(result[0], str)
        assert isinstance(result[1], int)

    def test_render_list_nested_dict_with_number(self) -> None:
        """Вложенный dict с числом в списке."""
        template_list = [{"chat_id": "{{chat_id}}"}]
        result = TemplateEngine.render_list(template_list, chat_id="-1001234567890")
        assert result == [{"chat_id": -1001234567890}]
        assert isinstance(result[0]["chat_id"], int)

    def test_render_list_telegram_payload_use_case(self) -> None:
        """Use case: payload для Telegram API с chat_id как int."""
        template_list: list[Any] = [
            {"chat_id": "{{chat_id}}", "text": "{{message}}"},
            {"chat_id": "{{chat_id}}", "text": "{{message}}"}
        ]
        result = TemplateEngine.render_list(
            template_list,
            chat_id="-1001234567890",
            message="Hello"
        )
        assert result == [
            {"chat_id": -1001234567890, "text": "Hello"},
            {"chat_id": -1001234567890, "text": "Hello"}
        ]
        assert isinstance(result[0]["chat_id"], int)
        assert isinstance(result[1]["chat_id"], int)


class TestTemplateEngineConvertStringToNumber:
    """Тесты метода _convert_string_to_number."""

    def test_convert_valid_integer_positive(self) -> None:
        """Конвертация положительного целого числа."""
        result = TemplateEngine._convert_string_to_number("123")
        assert result == 123
        assert isinstance(result, int)

    def test_convert_valid_integer_negative(self) -> None:
        """Конвертация отрицательного целого числа."""
        result = TemplateEngine._convert_string_to_number("-456")
        assert result == -456
        assert isinstance(result, int)

    def test_convert_valid_integer_with_plus(self) -> None:
        """Конвертация целого числа с плюсом."""
        result = TemplateEngine._convert_string_to_number("+789")
        assert result == 789
        assert isinstance(result, int)

    def test_convert_valid_float_positive(self) -> None:
        """Конвертация положительного дробного числа."""
        result = TemplateEngine._convert_string_to_number("12.34")
        assert result == 12.34
        assert isinstance(result, float)

    def test_convert_valid_float_negative(self) -> None:
        """Конвертация отрицательного дробного числа."""
        result = TemplateEngine._convert_string_to_number("-56.78")
        assert result == -56.78
        assert isinstance(result, float)

    def test_convert_valid_float_with_plus(self) -> None:
        """Конвертация дробного числа с плюсом."""
        result = TemplateEngine._convert_string_to_number("+90.12")
        assert result == 90.12
        assert isinstance(result, float)

    def test_convert_invalid_string_with_letters(self) -> None:
        """Строка с буквами не конвертируется."""
        result = TemplateEngine._convert_string_to_number("123abc")
        assert result == "123abc"
        assert isinstance(result, str)

    def test_convert_invalid_string_only_letters(self) -> None:
        """Строка только с буквами не конвертируется."""
        result = TemplateEngine._convert_string_to_number("hello")
        assert result == "hello"
        assert isinstance(result, str)

    def test_convert_invalid_empty_string(self) -> None:
        """Пустая строка не конвертируется."""
        result = TemplateEngine._convert_string_to_number("")
        assert result == ""
        assert isinstance(result, str)

    def test_convert_invalid_decimal_no_integer_part(self) -> None:
        """Число без целой части не конвертируется."""
        result = TemplateEngine._convert_string_to_number(".123")
        assert result == ".123"
        assert isinstance(result, str)

    def test_convert_invalid_decimal_no_fractional_part(self) -> None:
        """Число без дробной части не конвертируется."""
        result = TemplateEngine._convert_string_to_number("123.")
        assert result == "123."
        assert isinstance(result, str)

    def test_convert_invalid_multiple_dots(self) -> None:
        """Число с несколькими точками не конвертируется."""
        result = TemplateEngine._convert_string_to_number("1.2.3")
        assert result == "1.2.3"
        assert isinstance(result, str)

    def test_convert_invalid_whitespace(self) -> None:
        """Число с пробелами не конвертируется."""
        result = TemplateEngine._convert_string_to_number(" 123 ")
        assert result == " 123 "
        assert isinstance(result, str)

    def test_convert_zero_integer(self) -> None:
        """Конвертация нуля."""
        result = TemplateEngine._convert_string_to_number("0")
        assert result == 0
        assert isinstance(result, int)

    def test_convert_zero_float(self) -> None:
        """Конвертация 0.0."""
        result = TemplateEngine._convert_string_to_number("0.0")
        assert result == 0.0
        assert isinstance(result, float)
