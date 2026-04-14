"""
SQL запросы для Telegram авторизации.

CRUD операции для таблицы telegram_auth.
"""

SQL_UPSERT_TELEGRAM_AUTH = """
INSERT INTO telegram_auth (api_id, api_hash, phone_number, session_name, session_data)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (id) DO UPDATE SET
    api_id = COALESCE(EXCLUDED.api_id, telegram_auth.api_id),
    api_hash = COALESCE(EXCLUDED.api_hash, telegram_auth.api_hash),
    phone_number = COALESCE(EXCLUDED.phone_number, telegram_auth.phone_number),
    session_name = COALESCE(EXCLUDED.session_name, telegram_auth.session_name),
    session_data = CASE 
        WHEN EXCLUDED.session_data IS NULL THEN telegram_auth.session_data
        ELSE EXCLUDED.session_data
    END,
    updated_at = NOW()
RETURNING *
"""

SQL_CLEAR_SESSION = """
UPDATE telegram_auth
SET session_name = NULL,
    session_data = NULL,
    updated_at = NOW()
WHERE id = 1
RETURNING *
"""

SQL_GET_TELEGRAM_AUTH = """
SELECT id, api_id, api_hash, phone_number, session_name, session_data, updated_at
FROM telegram_auth
WHERE id = 1
"""

SQL_CREATE_SESSION_NAME_INDEX = """
CREATE INDEX IF NOT EXISTS idx_telegram_auth_session_name ON telegram_auth(session_name)
"""

SQL_SAVE_SESSION_DATA = """
UPDATE telegram_auth
SET session_data = $1, updated_at = NOW()
WHERE session_name = $2
"""

SQL_GET_SESSION_DATA = """
SELECT session_data
FROM telegram_auth
WHERE session_name = $1
LIMIT 1
"""

__all__ = [
    "SQL_UPSERT_TELEGRAM_AUTH",
    "SQL_GET_TELEGRAM_AUTH",
    "SQL_CREATE_SESSION_NAME_INDEX",
    "SQL_SAVE_SESSION_DATA",
    "SQL_GET_SESSION_DATA",
    "SQL_CLEAR_SESSION",
]
