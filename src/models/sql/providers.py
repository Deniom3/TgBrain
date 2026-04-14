"""
SQL запросы для провайдеров.

CRUD операции для таблиц llm_providers, embedding_providers.
"""

# ==================== LLM Providers ====================

SQL_INSERT_LLM_PROVIDER = """
INSERT INTO llm_providers (name, is_active, api_key, base_url, model, is_enabled, priority, description)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
ON CONFLICT (name) DO UPDATE SET
    is_active = EXCLUDED.is_active,
    api_key = EXCLUDED.api_key,
    base_url = EXCLUDED.base_url,
    model = EXCLUDED.model,
    is_enabled = EXCLUDED.is_enabled,
    priority = EXCLUDED.priority,
    description = EXCLUDED.description,
    updated_at = NOW()
RETURNING *
"""

SQL_GET_LLM_PROVIDER = """
SELECT * FROM llm_providers WHERE name = $1
"""

SQL_GET_ALL_LLM_PROVIDERS = """
SELECT * FROM llm_providers ORDER BY priority, name
"""

SQL_GET_ACTIVE_LLM_PROVIDER = """
SELECT * FROM llm_providers WHERE is_active = TRUE AND is_enabled = TRUE LIMIT 1
"""

SQL_UPDATE_LLM_PROVIDER = """
UPDATE llm_providers
SET is_active = $2, api_key = $3, base_url = $4, model = $5, is_enabled = $6, priority = $7, description = $8, updated_at = NOW()
WHERE name = $1
RETURNING *
"""

SQL_SET_ACTIVE_PROVIDER = """
UPDATE llm_providers SET is_active = FALSE WHERE id != $1
"""

SQL_DELETE_LLM_PROVIDER = """
DELETE FROM llm_providers WHERE name = $1
"""

# ==================== Embedding Providers ====================

SQL_INSERT_EMBEDDING_PROVIDER = """
INSERT INTO embedding_providers (name, is_active, api_key, base_url, model, is_enabled, priority, description, embedding_dim, max_retries, timeout, normalize)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
ON CONFLICT (name) DO UPDATE SET
    is_active = EXCLUDED.is_active,
    api_key = EXCLUDED.api_key,
    base_url = EXCLUDED.base_url,
    model = EXCLUDED.model,
    is_enabled = EXCLUDED.is_enabled,
    priority = EXCLUDED.priority,
    description = EXCLUDED.description,
    embedding_dim = EXCLUDED.embedding_dim,
    max_retries = EXCLUDED.max_retries,
    timeout = EXCLUDED.timeout,
    normalize = EXCLUDED.normalize,
    updated_at = NOW()
RETURNING *
"""

SQL_GET_EMBEDDING_PROVIDER = """
SELECT * FROM embedding_providers WHERE name = $1
"""

SQL_GET_ALL_EMBEDDING_PROVIDERS = """
SELECT * FROM embedding_providers ORDER BY priority, name
"""

SQL_GET_ACTIVE_EMBEDDING_PROVIDER = """
SELECT * FROM embedding_providers WHERE is_active = TRUE AND is_enabled = TRUE LIMIT 1
"""

SQL_UPDATE_EMBEDDING_PROVIDER = """
UPDATE embedding_providers
SET is_active = $2, api_key = $3, base_url = $4, model = $5, is_enabled = $6, priority = $7, description = $8, embedding_dim = $9, max_retries = $10, timeout = $11, normalize = $12, updated_at = NOW()
WHERE name = $1
RETURNING *
"""

SQL_SET_ACTIVE_EMBEDDING_PROVIDER = """
UPDATE embedding_providers SET is_active = FALSE WHERE id != $1
"""

SQL_DELETE_EMBEDDING_PROVIDER = """
DELETE FROM embedding_providers WHERE name = $1
"""

__all__ = [
    "SQL_INSERT_LLM_PROVIDER",
    "SQL_GET_LLM_PROVIDER",
    "SQL_GET_ALL_LLM_PROVIDERS",
    "SQL_GET_ACTIVE_LLM_PROVIDER",
    "SQL_UPDATE_LLM_PROVIDER",
    "SQL_SET_ACTIVE_PROVIDER",
    "SQL_DELETE_LLM_PROVIDER",
    "SQL_INSERT_EMBEDDING_PROVIDER",
    "SQL_GET_EMBEDDING_PROVIDER",
    "SQL_GET_ALL_EMBEDDING_PROVIDERS",
    "SQL_GET_ACTIVE_EMBEDDING_PROVIDER",
    "SQL_UPDATE_EMBEDDING_PROVIDER",
    "SQL_SET_ACTIVE_EMBEDDING_PROVIDER",
    "SQL_DELETE_EMBEDDING_PROVIDER",
]
