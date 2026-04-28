"""
SQL запросы для работы с сообщениями.

CRUD операции для таблицы messages.
"""

# Запросы для работы с сообщениями

SQL_INSERT_MESSAGE = """
INSERT INTO messages (
    id, chat_id, sender_id, sender_name, message_text,
    message_date, message_link, embedding, embedding_model, is_processed, is_bot
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
ON CONFLICT (id) DO NOTHING
"""

SQL_INSERT_MESSAGE_WITH_EMBEDDING = """
INSERT INTO messages (
    id, chat_id, sender_id, sender_name, message_text,
    message_date, message_link, embedding, embedding_model, is_processed, is_bot
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::VECTOR, $9, $10, $11)
ON CONFLICT (id) DO UPDATE SET
    embedding = EXCLUDED.embedding,
    embedding_model = EXCLUDED.embedding_model,
    is_processed = EXCLUDED.is_processed,
    is_bot = EXCLUDED.is_bot
"""

SQL_GET_UNPROCESSED_MESSAGES = """
SELECT id, chat_id, sender_id, sender_name, message_text,
       message_date, message_link, embedding, embedding_model, is_processed, created_at
FROM messages
WHERE is_processed = FALSE
ORDER BY message_date ASC
LIMIT $1
"""

SQL_GET_MESSAGES_BY_CHAT_ID = """
SELECT id, chat_id, sender_id, sender_name, message_text,
       message_date, message_link, embedding, embedding_model, is_processed, created_at
FROM messages
WHERE chat_id = $1
ORDER BY message_date DESC
LIMIT $2 OFFSET $3
"""

SQL_UPDATE_MESSAGE_EMBEDDING = """
UPDATE messages SET embedding = $2::VECTOR, embedding_model = $3, is_processed = TRUE
WHERE id = $1
"""

SQL_UPDATE_MESSAGE_EMBEDDING_WITH_MODEL = """
UPDATE messages
SET embedding = $2::VECTOR, embedding_model = $3, is_processed = TRUE
WHERE id = $1
"""

SQL_DELETE_OLD_MESSAGES = """
DELETE FROM messages WHERE message_date < $1
"""

# Запросы для переиндексации

SQL_GET_MESSAGES_FOR_REINDEX = """
SELECT id, chat_id, sender_id, sender_name, message_text,
       message_date, message_link, embedding, embedding_model, is_processed, created_at
FROM messages
WHERE embedding_model IS NULL OR embedding_model != $1
ORDER BY message_date ASC
LIMIT $2 OFFSET $3
"""

SQL_GET_MESSAGES_COUNT_FOR_REINDEX = """
SELECT COUNT(*) as count
FROM messages
WHERE embedding_model IS NULL OR embedding_model != $1
"""

SQL_GET_EMBEDDING_MODEL_STATS = """
SELECT
    embedding_model,
    COUNT(*) as message_count,
    MIN(message_date) as first_message,
    MAX(message_date) as last_message
FROM messages
WHERE embedding_model IS NOT NULL
GROUP BY embedding_model
ORDER BY message_count DESC
"""

# =============================================================================
# ✨ RAG Search — SQL запросы для расширенного поиска
# =============================================================================

SQL_GET_MESSAGE_NEIGHBORS = """
-- Получение соседних сообщений от того же отправителя
-- Параметры: $1=chat_id, $2=sender_id, $3=date_from, $4=embedding_vector, $5=date_to, $6=message_id, $7=limit
SELECT
    m.id, m.message_text, m.message_date, m.message_link,
    m.sender_name, m.sender_id, c.title as chat_title,
    1 - (m.embedding <=> $4::VECTOR) as similarity_score
FROM messages m
JOIN chat_settings c ON m.chat_id = c.chat_id
WHERE m.chat_id = $1
  AND m.sender_id = $2
  AND m.message_date BETWEEN $3 AND $5
  AND m.id != $6
ORDER BY m.message_date
LIMIT $7
"""

SQL_GET_CONSECUTIVE_MESSAGES = """
-- Получение последовательных сообщений от одного отправителя
-- Параметры: $1=chat_id, $2=sender_id, $3=date_from, $4=embedding_vector, $5=date_to
SELECT
    m.id, m.message_text, m.message_date, m.message_link,
    m.sender_name, m.sender_id, c.title as chat_title,
    1 - (m.embedding <=> $4::VECTOR) as similarity_score
FROM messages m
JOIN chat_settings c ON m.chat_id = c.chat_id
WHERE m.chat_id = $1
  AND m.sender_id = $2
  AND m.message_date BETWEEN $3 AND $5
ORDER BY m.message_date
"""

SQL_GET_MESSAGES_IN_TIME_WINDOW = """
-- Получение всех сообщений в заданном временном окне
-- Параметры: $1=chat_id, $2=date_from, $3=date_to, $4=limit
SELECT
    m.id, m.message_text, m.message_date, m.message_link,
    m.sender_name, m.sender_id, c.title as chat_title
FROM messages m
JOIN chat_settings c ON m.chat_id = c.chat_id
WHERE m.chat_id = $1
  AND m.message_date BETWEEN $2 AND $3
ORDER BY m.message_date
LIMIT $4
"""

SQL_CHECK_CHAT_EXISTS = """
-- Проверка существования чата по ID
-- Параметры: $1=chat_id
SELECT chat_id FROM chat_settings WHERE chat_id = $1 LIMIT 1
"""

SQL_GET_MESSAGE_BY_ID = """
-- Получение сообщения по ID с информацией о чате
-- Параметры: $1=message_id, $2=chat_id
SELECT m.id, m.message_text, m.message_date, m.message_link,
       m.sender_name, m.sender_id, c.title as chat_title
FROM messages m
JOIN chat_settings c ON m.chat_id = c.chat_id
WHERE m.id = $1 AND m.chat_id = $2
"""

__all__ = [
    "SQL_INSERT_MESSAGE",
    "SQL_INSERT_MESSAGE_WITH_EMBEDDING",
    "SQL_GET_UNPROCESSED_MESSAGES",
    "SQL_GET_MESSAGES_BY_CHAT_ID",
    "SQL_UPDATE_MESSAGE_EMBEDDING",
    "SQL_UPDATE_MESSAGE_EMBEDDING_WITH_MODEL",
    "SQL_DELETE_OLD_MESSAGES",
    "SQL_GET_MESSAGES_FOR_REINDEX",
    "SQL_GET_MESSAGES_COUNT_FOR_REINDEX",
    "SQL_GET_EMBEDDING_MODEL_STATS",
    # ✨ RAG Search
    "SQL_GET_MESSAGE_NEIGHBORS",
    "SQL_GET_CONSECUTIVE_MESSAGES",
    "SQL_GET_MESSAGES_IN_TIME_WINDOW",
    "SQL_CHECK_CHAT_EXISTS",
    "SQL_GET_MESSAGE_BY_ID",
]
