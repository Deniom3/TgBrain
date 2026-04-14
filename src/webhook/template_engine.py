"""
Template Engine — шаблонизация {{variable}} для webhook.
"""

import logging
import re
from typing import Any, Union

logger = logging.getLogger(__name__)

# Валидный паттерн для имён переменных: буквы, цифры, подчёркивание, точки
# Переменные с префиксом 'secrets.' запрещены из соображений безопасности
VALID_VARIABLE_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_.]*$')
SECRETS_PREFIX = "secrets."

# Паттерн для целых чисел (с опциональным знаком)
INTEGER_PATTERN = re.compile(r'^[+-]?\d+$')

# Паттерн для дробных чисел (с опциональным знаком и точкой)
FLOAT_PATTERN = re.compile(r'^[+-]?\d+\.\d+$')


class TemplateEngine:
    """Движок шаблонизации для webhook.

    Поддерживает переменные {{variable}} для подстановки значений из context.
    Переменные с префиксом 'secrets.' запрещены из соображений безопасности.
    """

    @staticmethod
    def _convert_string_to_number(value: str) -> Union[int, float, str]:
        """
        Конвертировать строку в int или float если возможно.
        
        Args:
            value: Строка для конвертации.
            
        Returns:
            int если строка представляет целое число,
            float если строка представляет дробное число,
            str если конвертация невозможна.
        """
        if INTEGER_PATTERN.match(value):
            return int(value)
        if FLOAT_PATTERN.match(value):
            return float(value)
        return value

    @staticmethod
    def _validate_variable_name(name: str) -> None:
        """
        Валидировать имя переменной перед рендерингом.

        Args:
            name: Имя переменной для валидации.

        Raises:
            ValueError: Если имя переменной невалидно или использует запрещённый префикс 'secrets.'.
        """
        if not VALID_VARIABLE_PATTERN.match(name):
            raise ValueError(
                f"Невалидное имя переменной: {name}. "
                "Допустимы буквы, цифры, подчёркивание и точки, "
                "начинающиеся с буквы или подчёркивания"
            )
        
        # Запрет переменных с префиксом 'secrets.' из соображений безопасности
        if name.lower().startswith(SECRETS_PREFIX):
            raise ValueError(
                f"Переменные с префиксом 'secrets.' запрещены: {name}. "
                "Используйте явную передачу чувствительных данных через context."
            )

    @staticmethod
    def render(template: str, **context: Any) -> Union[str, int, float]:
        """
        Заменить {{variable}} на значения из context.
        
        После рендеринга выполняется конвертация результата в int/float
        если строка представляет число (целое или дробное).

        Args:
            template: Шаблон с {{variable}}.
            **context: Переменные для подстановки.

        Returns:
            Строка с подставленными значениями,
            либо int/float если результат представляет число.
            
        Raises:
            ValueError: Если имя переменной невалидно.
        """
        pattern = re.compile(r"\{\{([a-zA-Z_][a-zA-Z0-9_.]*)\}\}")

        def replace_match(match: re.Match[str]) -> str:
            var_name = match.group(1)
            TemplateEngine._validate_variable_name(var_name)
            if var_name in context:
                value = context[var_name]
                if value is None:
                    return ""
                return str(value)
            return match.group(0)

        result = pattern.sub(replace_match, template)

        if isinstance(result, str):
            return TemplateEngine._convert_string_to_number(result)
        return result

    @staticmethod
    def render_dict(template_dict: dict[str, Any], **context: Any) -> dict[str, Any]:
        """
        Рекурсивная шаблонизация dict.
        
        После рендеринга строковых значений выполняется конвертация в int/float
        если строка представляет число (целое или дробное).

        Args:
            template_dict: Шаблон dict.
            **context: Переменные для подстановки.

        Returns:
            Dict с подставленными значениями (строковые числовые значения
            конвертируются в int/float).
            
        Raises:
            ValueError: Если имя переменной в template невалидно.
        """
        result: dict[str, Any] = {}
        for key, value in template_dict.items():
            # Валидация ключей dict для защиты от injection
            TemplateEngine._validate_variable_name(key)
            
            if isinstance(value, str):
                result[key] = TemplateEngine.render(value, **context)
            elif isinstance(value, dict):
                result[key] = TemplateEngine.render_dict(value, **context)
            elif isinstance(value, list):
                result[key] = TemplateEngine.render_list(value, **context)
            else:
                result[key] = value
        return result

    @staticmethod
    def render_list(template_list: list[Any], **context: Any) -> list[Any]:
        """
        Рекурсивная шаблонизация list.
        
        После рендеринга строковых значений выполняется конвертация в int/float
        если строка представляет число (целое или дробное).

        Args:
            template_list: Шаблон list.
            **context: Переменные для подстановки.

        Returns:
            List с подставленными значениями (строковые числовые значения
            конвертируются в int/float).
            
        Raises:
            ValueError: Если имя переменной в template невалидно.
        """
        result: list[Any] = []
        for item in template_list:
            if isinstance(item, str):
                result.append(TemplateEngine.render(item, **context))
            elif isinstance(item, dict):
                result.append(TemplateEngine.render_dict(item, **context))
            elif isinstance(item, list):
                result.append(TemplateEngine.render_list(item, **context))
            else:
                result.append(item)
        return result
