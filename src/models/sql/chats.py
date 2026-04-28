"""
SQL запросы для работы с чатами.

CRUD операции для таблицы chat_settings (объединённая с chats).
"""

# ==================== Chat Settings SQL (объединённая таблица) ====================

SQL_BULK_UPSERT_CHAT_SETTINGS = """
INSERT INTO chat_settings (chat_id, title, type, last_message_id, is_monitored, summary_enabled, filter_bots, filter_actions, filter_min_length, filter_ads)
SELECT * FROM UNNEST(
    $1::BIGINT[],
    $2::TEXT[],
    $3::TEXT[],
    $4::BIGINT[],
    $5::BOOLEAN[],
    $6::BOOLEAN[],
    $7::BOOLEAN[],
    $8::BOOLEAN[],
    $9::INTEGER[],
    $10::BOOLEAN[]
) AS t(chat_id, title, type, last_message_id, is_monitored, summary_enabled, filter_bots, filter_actions, filter_min_length, filter_ads)
ON CONFLICT (chat_id) DO UPDATE SET
    title = EXCLUDED.title,
    type = EXCLUDED.type,
    last_message_id = EXCLUDED.last_message_id,
    is_monitored = EXCLUDED.is_monitored,
    summary_enabled = EXCLUDED.summary_enabled,
    filter_bots = EXCLUDED.filter_bots,
    filter_actions = EXCLUDED.filter_actions,
    filter_min_length = EXCLUDED.filter_min_length,
    filter_ads = EXCLUDED.filter_ads,
    updated_at = NOW()
RETURNING *
"""

SQL_GET_MONITORED_CHATS = """
SELECT
    id,
    chat_id,
    title,
    type,
    last_message_id,
    is_monitored,
    summary_enabled,
    summary_period_minutes,
    summary_schedule,
    custom_prompt,
    webhook_config,
    webhook_enabled,
    filter_bots,
    filter_actions,
    filter_min_length,
    filter_ads,
    next_schedule_run,
    created_at,
    updated_at
FROM chat_settings
WHERE is_monitored = TRUE
ORDER BY chat_id
"""

SQL_GET_CHAT_SETTINGS_BY_ID = """
SELECT
    id,
    chat_id,
    title,
    type,
    last_message_id,
    is_monitored,
    summary_enabled,
    summary_period_minutes,
    summary_schedule,
    custom_prompt,
    webhook_config,
    webhook_enabled,
    filter_bots,
    filter_actions,
    filter_min_length,
    filter_ads,
    next_schedule_run,
    created_at,
    updated_at
FROM chat_settings
WHERE chat_id = $1
"""

SQL_UPDATE_CHAT_MONITORING = """
UPDATE chat_settings
SET is_monitored = $2, updated_at = NOW()
WHERE chat_id = $1
RETURNING *
"""

SQL_TOGGLE_CHAT_MONITORING = """
UPDATE chat_settings
SET is_monitored = NOT is_monitored, updated_at = NOW()
WHERE chat_id = $1
RETURNING *
"""

SQL_INSERT_CHAT_SETTING_SINGLE = """
INSERT INTO chat_settings (chat_id, title, type, last_message_id, is_monitored, summary_enabled, custom_prompt, filter_bots, filter_actions, filter_min_length, filter_ads)
VALUES ($1, $2, $3, 0, $4, $5, $6, $7, $8, $9, $10)
ON CONFLICT (chat_id) DO UPDATE SET
    title = EXCLUDED.title,
    type = EXCLUDED.type,
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

SQL_ENABLE_CHAT_BY_ID = """
UPDATE chat_settings
SET is_monitored = TRUE, updated_at = NOW()
WHERE chat_id = $1
RETURNING *
"""

SQL_DISABLE_CHAT_BY_ID = """
UPDATE chat_settings
SET is_monitored = FALSE, updated_at = NOW()
WHERE chat_id = $1
RETURNING *
"""

# ==================== Summary Settings SQL ====================

SQL_ENABLE_SUMMARY = """
UPDATE chat_settings
SET summary_enabled = TRUE, updated_at = NOW()
WHERE chat_id = $1
RETURNING *
"""

SQL_DISABLE_SUMMARY = """
UPDATE chat_settings
SET summary_enabled = FALSE, updated_at = NOW()
WHERE chat_id = $1
RETURNING *
"""

SQL_TOGGLE_SUMMARY = """
UPDATE chat_settings
SET summary_enabled = NOT summary_enabled, updated_at = NOW()
WHERE chat_id = $1
RETURNING *
"""

SQL_SET_SUMMARY_PERIOD = """
UPDATE chat_settings
SET summary_period_minutes = $2, updated_at = NOW()
WHERE chat_id = $1
RETURNING *
"""

SQL_SET_SUMMARY_SCHEDULE = """
UPDATE chat_settings
SET summary_schedule = $2, next_schedule_run = ($3 AT TIME ZONE 'UTC'), updated_at = NOW()
WHERE chat_id = $1
RETURNING *
"""

SQL_CLEAR_SUMMARY_SCHEDULE = """
UPDATE chat_settings
SET summary_schedule = NULL, next_schedule_run = NULL, updated_at = NOW()
WHERE chat_id = $1
RETURNING *
"""

SQL_GET_SUMMARY_SETTINGS = """
SELECT
    chat_id,
    summary_enabled,
    summary_period_minutes,
    summary_schedule,
    custom_prompt,
    next_schedule_run
FROM chat_settings
WHERE chat_id = $1
"""

SQL_GET_CUSTOM_PROMPT = """
SELECT custom_prompt
FROM chat_settings
WHERE chat_id = $1
"""

SQL_SET_CUSTOM_PROMPT = """
UPDATE chat_settings
SET custom_prompt = $2, updated_at = NOW()
WHERE chat_id = $1
RETURNING *
"""

SQL_CLEAR_CUSTOM_PROMPT = """
UPDATE chat_settings
SET custom_prompt = NULL, updated_at = NOW()
WHERE chat_id = $1
RETURNING *
"""

# ==================== Webhook Configuration SQL ====================

SQL_SET_WEBHOOK_CONFIG = """
UPDATE chat_settings
SET
    webhook_config = $2::JSONB,
    webhook_enabled = TRUE,
    updated_at = NOW()
WHERE chat_id = $1
RETURNING *
"""

SQL_GET_WEBHOOK_CONFIG = """
SELECT
    chat_id,
    webhook_config,
    webhook_enabled
FROM chat_settings
WHERE chat_id = $1
  AND webhook_enabled = TRUE
"""

SQL_DISABLE_WEBHOOK = """
UPDATE chat_settings
SET
    webhook_enabled = FALSE,
    updated_at = NOW()
WHERE chat_id = $1
RETURNING *
"""

SQL_UPDATE_NEXT_SCHEDULE_RUN = """
UPDATE chat_settings
SET next_schedule_run = $2, updated_at = NOW()
WHERE chat_id = $1
  AND (next_schedule_run IS NULL OR next_schedule_run <= NOW())
RETURNING *
"""

SQL_GET_ENABLED_SUMMARY_CHAT_IDS = "SELECT chat_id FROM chat_settings WHERE summary_enabled = TRUE"

SQL_GET_CHATS_WITH_SCHEDULE = """
SELECT
    id,
    chat_id,
    title,
    type,
    last_message_id,
    is_monitored,
    summary_enabled,
    summary_period_minutes,
    summary_schedule,
    custom_prompt,
    webhook_config,
    webhook_enabled,
    filter_bots,
    filter_actions,
    filter_min_length,
    filter_ads,
    next_schedule_run,
    created_at,
    updated_at
FROM chat_settings
WHERE summary_schedule IS NOT NULL
  AND summary_enabled = TRUE
  AND is_monitored = TRUE
  AND (next_schedule_run IS NULL OR next_schedule_run <= NOW())
ORDER BY chat_id
"""

# ==================== Устаревшие SQL (для обратной совместимости) ====================
# Используют chat_settings вместо chats

SQL_INSERT_CHAT = """
INSERT INTO chat_settings (chat_id, title, type, last_message_id, is_monitored, summary_enabled)
VALUES ($1, $2, $3, $4, TRUE, TRUE)
ON CONFLICT (chat_id) DO UPDATE SET
    title = EXCLUDED.title,
    type = EXCLUDED.type,
    last_message_id = EXCLUDED.last_message_id,
    is_monitored = EXCLUDED.is_monitored,
    summary_enabled = EXCLUDED.summary_enabled,
    updated_at = NOW()
RETURNING *
"""

SQL_GET_CHAT = """
SELECT
    id,
    chat_id,
    title,
    type,
    last_message_id,
    is_monitored,
    summary_enabled,
    summary_period_minutes,
    summary_schedule,
    custom_prompt,
    webhook_config,
    webhook_enabled,
    filter_bots,
    filter_actions,
    filter_min_length,
    filter_ads,
    next_schedule_run,
    created_at,
    updated_at
FROM chat_settings WHERE chat_id = $1
"""

SQL_GET_ACTIVE_CHATS = """
SELECT
    id,
    chat_id,
    title,
    type,
    last_message_id,
    is_monitored,
    summary_enabled,
    summary_period_minutes,
    summary_schedule,
    custom_prompt,
    webhook_config,
    webhook_enabled,
    filter_bots,
    filter_actions,
    filter_min_length,
    filter_ads,
    next_schedule_run,
    created_at,
    updated_at
FROM chat_settings WHERE is_monitored = TRUE
"""

SQL_UPDATE_CHAT_LAST_MESSAGE = """
UPDATE chat_settings SET last_message_id = $2, updated_at = NOW()
WHERE chat_id = $1
RETURNING *
"""

SQL_GET_CHAT_FILTER_CONFIGS = """
SELECT chat_id, filter_bots, filter_actions, filter_min_length, filter_ads
FROM chat_settings
WHERE is_monitored = TRUE
"""

__all__ = [
    "SQL_INSERT_CHAT",
    "SQL_GET_CHAT",
    "SQL_GET_ACTIVE_CHATS",
    "SQL_UPDATE_CHAT_LAST_MESSAGE",
    # Chat Settings
    "SQL_BULK_UPSERT_CHAT_SETTINGS",
    "SQL_GET_MONITORED_CHATS",
    "SQL_GET_CHAT_SETTINGS_BY_ID",
    "SQL_UPDATE_CHAT_MONITORING",
    "SQL_TOGGLE_CHAT_MONITORING",
    "SQL_INSERT_CHAT_SETTING_SINGLE",
    "SQL_ENABLE_CHAT_BY_ID",
    "SQL_DISABLE_CHAT_BY_ID",
    # Summary Settings
    "SQL_ENABLE_SUMMARY",
    "SQL_DISABLE_SUMMARY",
    "SQL_TOGGLE_SUMMARY",
    "SQL_SET_SUMMARY_PERIOD",
    "SQL_SET_SUMMARY_SCHEDULE",
    "SQL_CLEAR_SUMMARY_SCHEDULE",
    "SQL_GET_SUMMARY_SETTINGS",
    "SQL_GET_CUSTOM_PROMPT",
    "SQL_SET_CUSTOM_PROMPT",
    "SQL_CLEAR_CUSTOM_PROMPT",
    # Webhook Settings
    "SQL_SET_WEBHOOK_CONFIG",
    "SQL_GET_WEBHOOK_CONFIG",
    "SQL_DISABLE_WEBHOOK",
    # Schedule Settings
    "SQL_UPDATE_NEXT_SCHEDULE_RUN",
    "SQL_GET_CHATS_WITH_SCHEDULE",
    "SQL_GET_ENABLED_SUMMARY_CHAT_IDS",
    "SQL_GET_CHAT_FILTER_CONFIGS",
]
