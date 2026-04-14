"""
Исключения для RAG поиска.

Модуль предоставляет иерархию исключений для обработки ошибок
в модуле RAG поиска.
"""


class RagSearchError(Exception):
    """Базовое исключение RAG поиска."""


class DatabaseQueryError(RagSearchError):
    """Ошибка выполнения запроса к БД."""


class InvalidEmbeddingError(RagSearchError):
    """Некорректный вектор эмбеддинга."""
