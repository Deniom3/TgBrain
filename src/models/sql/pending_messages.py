"""
SQL запросы для работы с отложенными сообщениями.

CRUD операции для таблицы pending_messages.
"""

SQL_INSERT_PENDING = """
INSERT INTO pending_messages (message_data, retry_count, last_error)
VALUES ($1::JSONB, $2, $3)
RETURNING id, message_data, retry_count, last_error, created_at
"""

SQL_GET_PENDING = """
SELECT id, message_data, retry_count, last_error, created_at
FROM pending_messages
ORDER BY created_at ASC
LIMIT $1
"""

SQL_UPDATE_PENDING_RETRY = """
UPDATE pending_messages
SET retry_count = retry_count + 1, last_error = $2
WHERE id = $1
"""

SQL_DELETE_PENDING = """
DELETE FROM pending_messages WHERE id = $1
"""

__all__ = [
    "SQL_INSERT_PENDING",
    "SQL_GET_PENDING",
    "SQL_UPDATE_PENDING_RETRY",
    "SQL_DELETE_PENDING",
]
