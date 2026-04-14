"""SQL запросы для внешних сообщений."""

SQL_CHECK_CHAT_MONITORED = """
SELECT is_monitored FROM chat_settings WHERE chat_id = $1
"""

SQL_CHECK_DUPLICATE = """
SELECT id, message_text
FROM messages
WHERE chat_id = $1
  AND message_text = $2
  AND ABS(EXTRACT(EPOCH FROM (message_date - $3))) < $4
"""

SQL_UPSERT_EXTERNAL_MESSAGE = """
INSERT INTO messages (
    id, chat_id, sender_id, sender_name, message_text,
    message_date, message_link, embedding, embedding_model,
    is_processed
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::VECTOR, $9, $10)
ON CONFLICT (id) DO UPDATE SET
    message_text = EXCLUDED.message_text,
    embedding = EXCLUDED.embedding,
    embedding_model = EXCLUDED.embedding_model,
    is_processed = EXCLUDED.is_processed,
    sender_name = EXCLUDED.sender_name
RETURNING id
"""

SQL_UPSERT_CHAT_SETTINGS = """
INSERT INTO chat_settings (chat_id, title, type, last_message_id, is_monitored, summary_enabled)
VALUES ($1, $2, $3, 0, TRUE, TRUE)
ON CONFLICT (chat_id) DO UPDATE SET
    title = EXCLUDED.title,
    type = EXCLUDED.type,
    updated_at = NOW()
"""
