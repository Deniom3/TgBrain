"""
SQL-запросы для переиндексации.

Содержит все SQL-запросы, используемые для переиндексации сообщений:
- Получение сообщений для переиндексации
- Подсчёт сообщений для переиндексации
- Обновление эмбеддинга с моделью
- Получение статистики по моделям
- Изменение размерности вектора
- Получение текущей размерности вектора
"""

# SQL-запрос для получения сообщений для переиндексации
# Включает сообщения без эмбеддинга (NULL) ИЛИ с устаревшей моделью
SQL_GET_MESSAGES_FOR_REINDEX = """
SELECT id, message_text
FROM messages
WHERE embedding IS NULL
   OR embedding_model IS NULL
   OR embedding_model != $1::TEXT
ORDER BY id
LIMIT $2 OFFSET $3
"""

# SQL-запрос для подсчёта сообщений для переиндексации
# Включает сообщения без эмбеддинга (NULL) ИЛИ с устаревшей моделью
SQL_GET_MESSAGES_COUNT_FOR_REINDEX = """
SELECT COUNT(*) as count
FROM messages
WHERE embedding IS NULL
   OR embedding_model IS NULL
   OR embedding_model != $1::TEXT
"""

# SQL-запрос для обновления эмбеддинга с моделью
SQL_UPDATE_MESSAGE_EMBEDDING_WITH_MODEL = """
UPDATE messages
SET embedding = $2::VECTOR,
    embedding_model = $3::TEXT
WHERE id = $1
"""

# SQL-запрос для получения статистики по моделям эмбеддингов
SQL_GET_EMBEDDING_MODEL_STATS = """
SELECT
    embedding_model,
    COUNT(*) as message_count,
    MIN(message_date) as first_message,
    MAX(message_date) as last_message
FROM messages
WHERE embedding IS NOT NULL
GROUP BY embedding_model
ORDER BY message_count DESC
"""

# SQL-запрос для изменения размерности вектора
SQL_ALTER_EMBEDDING_DIMENSION = """
SELECT alter_embedding_dimension($1::INTEGER)
"""

# SQL-запрос для получения текущей размерности вектора
# Получаем реальную размерность из системных таблиц pgvector
SQL_GET_CURRENT_EMBEDDING_DIMENSION = """
SELECT 
    COALESCE(
        (SELECT atttypmod 
         FROM pg_attribute 
         WHERE attrelid = 'messages'::regclass 
         AND attname = 'embedding'),
        0
    ) as current_dim
"""

__all__ = [
    "SQL_GET_MESSAGES_FOR_REINDEX",
    "SQL_GET_MESSAGES_COUNT_FOR_REINDEX",
    "SQL_UPDATE_MESSAGE_EMBEDDING_WITH_MODEL",
    "SQL_GET_EMBEDDING_MODEL_STATS",
    "SQL_ALTER_EMBEDDING_DIMENSION",
    "SQL_GET_CURRENT_EMBEDDING_DIMENSION",
]
