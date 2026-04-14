"""
SQL запросы для работы с результатами суммаризации (chat_summaries).

CRUD операции для таблицы chat_summaries.
"""

# ==================== Создание задачи ====================

SQL_CREATE_SUMMARY_TASK = """
INSERT INTO chat_summaries (
    chat_id, period_start, period_end, status, params_hash,
    result_text, messages_count, metadata
) VALUES ($1, $2, $3, 'pending', $4, '', 0, $5::JSONB)
RETURNING id, created_at, status
"""

# ==================== Обновление статуса ====================

SQL_UPDATE_SUMMARY_STATUS = """
UPDATE chat_summaries
SET status = $1, updated_at = NOW(),
    result_text = $2,
    messages_count = COALESCE($3, messages_count),
    metadata = $4::JSONB
WHERE id = $5
"""

SQL_START_PROCESSING = """
UPDATE chat_summaries
SET status = 'processing', updated_at = NOW()
WHERE id = $1
"""

SQL_COMPLETE_SUMMARY = """
UPDATE chat_summaries
SET status = 'completed', updated_at = NOW(),
    result_text = $2,
    messages_count = $3, metadata = $4::JSONB
WHERE id = $1
"""

SQL_FAIL_SUMMARY = """
UPDATE chat_summaries
SET status = 'failed', updated_at = NOW(),
    result_text = $2,
    metadata = $3::JSONB
WHERE id = $1
"""

# ==================== Поиск кэша ====================

SQL_GET_CACHED_SUMMARY = """
SELECT id, status, result_text, created_at, updated_at
FROM chat_summaries
WHERE params_hash = $1
  AND status = 'completed'
ORDER BY created_at DESC
LIMIT 1
"""

SQL_GET_PENDING_TASK = """
SELECT id, status, created_at
FROM chat_summaries
WHERE params_hash = $1
  AND status IN ('pending', 'processing')
ORDER BY created_at DESC
LIMIT 1
"""

# ==================== Чтение задачи/summary ====================

SQL_GET_SUMMARY_TASK = """
SELECT id, chat_id, created_at, updated_at, period_start, period_end,
       status, params_hash, result_text,
       messages_count, embedding, embedding_model, generated_by, metadata
FROM chat_summaries
WHERE id = $1
"""

# ==================== Очистка ====================

SQL_CLEANUP_OLD_TASKS = """
DELETE FROM chat_summaries
WHERE status IN ('failed', 'pending')
  AND created_at < NOW() - MAKE_INTERVAL(hours => $1)
"""

# ==================== Очистка ====================

SQL_CLEANUP_OLD_TASKS = """
DELETE FROM chat_summaries
WHERE status IN ('failed', 'pending')
  AND created_at < NOW() - MAKE_INTERVAL(hours => $1)
"""

__all__ = [
    # ==================== Управление задачами ====================
    "SQL_CREATE_SUMMARY_TASK",
    "SQL_UPDATE_SUMMARY_STATUS",
    "SQL_START_PROCESSING",
    "SQL_COMPLETE_SUMMARY",
    "SQL_FAIL_SUMMARY",
    "SQL_GET_CACHED_SUMMARY",
    "SQL_GET_PENDING_TASK",
    "SQL_GET_SUMMARY_TASK",
    "SQL_CLEANUP_OLD_TASKS",
]
