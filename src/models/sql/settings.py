"""
SQL запросы для настроек.

CRUD операции для таблиц chat_settings, app_settings.
"""

# ==================== Chat Settings ====================

SQL_INSERT_CHAT_SETTING = """
INSERT INTO chat_settings (chat_id, title, is_monitored, summary_enabled, custom_prompt, filter_bots, filter_actions, filter_min_length, filter_ads)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
ON CONFLICT (chat_id) DO UPDATE SET
    title = EXCLUDED.title,
    is_monitored = EXCLUDED.is_monitored,
    summary_enabled = EXCLUDED.summary_enabled,
    custom_prompt = EXCLUDED.custom_prompt,
    filter_bots = EXCLUDED.filter_bots,
    filter_actions = EXCLUDED.filter_actions,
    filter_min_length = EXCLUDED.filter_min_length,
    filter_ads = EXCLUDED.filter_ads,
    updated_at = NOW()
RETURNING *
"""

SQL_GET_CHAT_SETTING = """
SELECT * FROM chat_settings WHERE chat_id = $1
"""

SQL_GET_ALL_CHAT_SETTINGS = """
SELECT * FROM chat_settings ORDER BY chat_id
"""

SQL_UPDATE_CHAT_SETTING = """
UPDATE chat_settings
SET is_monitored = $2, summary_enabled = $3, custom_prompt = $4,
    filter_bots = $5, filter_actions = $6, filter_min_length = $7, filter_ads = $8,
    updated_at = NOW()
WHERE chat_id = $1
RETURNING *
"""

SQL_DELETE_CHAT_SETTING = """
DELETE FROM chat_settings WHERE chat_id = $1
"""

# ==================== App Settings ====================

SQL_INSERT_APP_SETTING = """
INSERT INTO app_settings (key, value, value_type, description, is_sensitive)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (key) DO UPDATE SET
    value = EXCLUDED.value,
    value_type = EXCLUDED.value_type,
    description = EXCLUDED.description,
    is_sensitive = EXCLUDED.is_sensitive,
    updated_at = NOW()
RETURNING *
"""

SQL_INSERT_APP_SETTING_IF_NOT_EXISTS = """
INSERT INTO app_settings (key, value, value_type, description, is_sensitive)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (key) DO NOTHING
RETURNING *
"""

SQL_GET_APP_SETTING = """
SELECT * FROM app_settings WHERE key = $1
"""

SQL_GET_ALL_APP_SETTINGS = """
SELECT * FROM app_settings ORDER BY key
"""

SQL_UPDATE_APP_SETTING = """
UPDATE app_settings
SET value = $2, updated_at = NOW()
WHERE key = $1
RETURNING *
"""

SQL_DELETE_APP_SETTING = """
DELETE FROM app_settings WHERE key = $1
"""

__all__ = [
    "SQL_INSERT_CHAT_SETTING",
    "SQL_GET_CHAT_SETTING",
    "SQL_GET_ALL_CHAT_SETTINGS",
    "SQL_UPDATE_CHAT_SETTING",
    "SQL_DELETE_CHAT_SETTING",
    "SQL_INSERT_APP_SETTING",
    "SQL_INSERT_APP_SETTING_IF_NOT_EXISTS",
    "SQL_GET_APP_SETTING",
    "SQL_GET_ALL_APP_SETTINGS",
    "SQL_UPDATE_APP_SETTING",
    "SQL_DELETE_APP_SETTING",
]
