"""
SQL запросы для RAG поиска.
"""

SQL_SEARCH_SIMILAR_WITH_CHAT_FILTER = """
SELECT
    m.id,
    m.message_text,
    m.message_date,
    m.message_link,
    m.sender_name,
    m.sender_id,
    c.title as chat_title,
    1 - (m.embedding <=> $1::VECTOR) as similarity_score
FROM messages m
JOIN chat_settings c ON m.chat_id = c.chat_id
WHERE m.embedding IS NOT NULL
  AND ($3::BIGINT IS NULL OR m.chat_id = $3)
ORDER BY m.embedding <=> $1::VECTOR
LIMIT $2
"""

SQL_GET_MESSAGES_BY_PERIOD = """
SELECT
    m.id,
    m.message_text,
    m.message_date,
    m.message_link,
    m.sender_name,
    m.sender_id,
    c.title as chat_title
FROM messages m
JOIN chat_settings c ON m.chat_id = c.chat_id
WHERE m.message_date >= NOW() - ($1::integer * INTERVAL '1 hour')
  AND ($3::BIGINT IS NULL OR m.chat_id = $3)
ORDER BY m.message_date DESC
LIMIT $2
"""

SQL_GET_MESSAGES_BY_PERIOD_RANGE = """
SELECT
    m.id,
    m.message_text,
    m.message_date,
    m.message_link,
    m.sender_name,
    m.sender_id,
    c.title as chat_title
FROM messages m
JOIN chat_settings c ON m.chat_id = c.chat_id
WHERE m.message_date >= $1
  AND m.message_date <= $2
  AND ($4::BIGINT IS NULL OR m.chat_id = $4)
ORDER BY m.message_date DESC
LIMIT $3
"""
