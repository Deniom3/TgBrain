"""
SQL запросы для переиндексации.

CRUD операции для таблиц reindex_settings, reindex_tasks.
"""

# ==================== Reindex Settings ====================

SQL_INSERT_REINDEX_SETTING = """
INSERT INTO reindex_settings (
    id, batch_size, delay_between_batches, auto_reindex_on_model_change,
    auto_reindex_new_messages, reindex_new_messages_delay, max_concurrent_tasks,
    max_retries, low_priority_delay, normal_priority_delay, high_priority_delay,
    last_reindex_model, speed_mode, current_batch_size
)
VALUES (1, $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
ON CONFLICT (id) DO UPDATE SET
    batch_size = EXCLUDED.batch_size,
    delay_between_batches = EXCLUDED.delay_between_batches,
    auto_reindex_on_model_change = EXCLUDED.auto_reindex_on_model_change,
    auto_reindex_new_messages = EXCLUDED.auto_reindex_new_messages,
    reindex_new_messages_delay = EXCLUDED.reindex_new_messages_delay,
    max_concurrent_tasks = EXCLUDED.max_concurrent_tasks,
    max_retries = EXCLUDED.max_retries,
    low_priority_delay = EXCLUDED.low_priority_delay,
    normal_priority_delay = EXCLUDED.normal_priority_delay,
    high_priority_delay = EXCLUDED.high_priority_delay,
    last_reindex_model = EXCLUDED.last_reindex_model,
    speed_mode = EXCLUDED.speed_mode,
    current_batch_size = EXCLUDED.current_batch_size,
    updated_at = NOW()
RETURNING *
"""

SQL_GET_REINDEX_SETTING = """
SELECT id, batch_size, delay_between_batches,
       low_priority_delay, normal_priority_delay, high_priority_delay,
       auto_reindex_on_model_change, last_reindex_model
FROM reindex_settings WHERE id = 1
"""

SQL_UPDATE_REINDEX_SETTING = """
UPDATE reindex_settings
SET batch_size = $1, delay_between_batches = $2, updated_at = NOW()
WHERE id = 1
RETURNING *
"""

SQL_SET_LAST_REINDEX_MODEL = """
UPDATE reindex_settings SET last_reindex_model = $1, updated_at = NOW()
WHERE id = 1
"""

# ==================== Reindex Tasks ====================

SQL_INSERT_REINDEX_TASK = """
INSERT INTO reindex_tasks (
    id, status, priority, target_model, total_messages,
    processed_count, failed_count, batch_size, delay_between_batches,
    created_at, started_at, completed_at, error, progress_percent
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
ON CONFLICT (id) DO UPDATE SET
    status = EXCLUDED.status,
    priority = EXCLUDED.priority,
    target_model = EXCLUDED.target_model,
    total_messages = EXCLUDED.total_messages,
    processed_count = EXCLUDED.processed_count,
    failed_count = EXCLUDED.failed_count,
    batch_size = EXCLUDED.batch_size,
    delay_between_batches = EXCLUDED.delay_between_batches,
    started_at = EXCLUDED.started_at,
    completed_at = EXCLUDED.completed_at,
    error = EXCLUDED.error,
    progress_percent = EXCLUDED.progress_percent,
    updated_at = NOW()
RETURNING *
"""

SQL_UPDATE_REINDEX_TASK = """
UPDATE reindex_tasks
SET status = $1, processed_count = $2, failed_count = $3, progress_percent = $4
WHERE id = $5
"""

SQL_GET_REINDEX_TASK = """
SELECT id, status, priority, target_model, batch_size,
       delay_between_batches, total_messages,
       processed_count,
       failed_count,
       progress_percent, started_at, completed_at, error
FROM reindex_tasks WHERE id = $1
"""

SQL_GET_REINDEX_TASK_HISTORY = """
SELECT id, status, priority, target_model, batch_size,
       delay_between_batches, total_messages,
       processed_count,
       failed_count,
       progress_percent, started_at, completed_at, error
FROM reindex_tasks ORDER BY started_at DESC LIMIT $1
"""

__all__ = [
    "SQL_INSERT_REINDEX_SETTING",
    "SQL_GET_REINDEX_SETTING",
    "SQL_UPDATE_REINDEX_SETTING",
    "SQL_SET_LAST_REINDEX_MODEL",
    "SQL_INSERT_REINDEX_TASK",
    "SQL_UPDATE_REINDEX_TASK",
    "SQL_GET_REINDEX_TASK",
    "SQL_GET_REINDEX_TASK_HISTORY",
]
