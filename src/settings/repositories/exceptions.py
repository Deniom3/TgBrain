"""
Исключения модуля настроек.

Вынесены в отдельный модуль для предотвращения циклических импортов
между chat_settings.py и chat_summary_settings.py.
"""


class ChatSettingsStorageError(Exception):
    """Ошибка доступа к хранилищу настроек чата."""
