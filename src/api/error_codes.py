"""Коды ошибок API."""
from dataclasses import dataclass


@dataclass
class ErrorCode:
    """Код ошибки API."""

    code: str
    message: str
    http_status: int


RAG_ERROR_CODES: dict[str, ErrorCode] = {
    "RAG-001": ErrorCode("RAG-001", "Invalid question", 400),
    "RAG-002": ErrorCode("RAG-002", "Chat not found", 400),
    "RAG-003": ErrorCode("RAG-003", "Invalid search_in value", 400),
    "RAG-004": ErrorCode("RAG-004", "Invalid top_k", 400),
    "RAG-005": ErrorCode("RAG-005", "No relevant messages found", 404),
    "RAG-006": ErrorCode("RAG-006", "Embedding generation failed", 500),
    "RAG-007": ErrorCode("RAG-007", "LLM generation failed", 500),
    "RAG-008": ErrorCode("RAG-008", "Database error", 500),
}

EXTERNAL_INGEST_ERROR_CODES: dict[str, ErrorCode] = {
    "EXT-001": ErrorCode("EXT-001", "Invalid request data", 400),
    "EXT-002": ErrorCode("EXT-002", "Chat not monitored", 400),
    "EXT-003": ErrorCode("EXT-003", "Embedding error", 200),
    "EXT-004": ErrorCode("EXT-004", "Database error", 200),
    "EXT-005": ErrorCode("EXT-005", "Filtered message", 200),
    "EXT-006": ErrorCode("EXT-006", "Duplicate message", 200),
    "EXT-007": ErrorCode("EXT-007", "Embedding service unavailable", 200),
    "EXT-008": ErrorCode("EXT-008", "File too large", 413),
    "EXT-009": ErrorCode("EXT-009", "Invalid chat type", 400),
    "EXT-010": ErrorCode("EXT-010", "Invalid content type", 415),
    # EXT-011, EXT-012 intentionally skipped (see 03-decisions.md)
    "EXT-013": ErrorCode("EXT-013", "Task not found", 404),
    "EXT-014": ErrorCode("EXT-014", "User has no access to chat", 403),
    "EXT-015": ErrorCode("EXT-015", "Too many messages", 400),
}

SUMMARY_ERROR_CODES: dict[str, ErrorCode] = {
    "SUM-001": ErrorCode("SUM-001", "Chat not found", 404),
    "SUM-002": ErrorCode("SUM-002", "Database error creating task", 500),
    "SUM-003": ErrorCode("SUM-003", "Summary generation timeout", 500),
    "SUM-004": ErrorCode("SUM-004", "LLM generation failed", 500),
}

# ===== APP Error Codes =====
# APP-001..003 — existing (settings_api), значения НЕ менять
# APP-101..199 — global exception handlers

APP_ERROR_CODES: dict[str, ErrorCode] = {
    "APP-001": ErrorCode("APP-001", "Invalid timezone", 400),
    "APP-002": ErrorCode("APP-002", "Setting not found", 404),
    "APP-003": ErrorCode("APP-003", "Failed to save setting", 500),
    "APP-008": ErrorCode("APP-008", "Invalid filter configuration", 422),
    "APP-101": ErrorCode("APP-101", "Internal server error", 500),
    "APP-102": ErrorCode("APP-102", "Validation error", 400),
    "APP-103": ErrorCode("APP-103", "Not found", 404),
    "APP-104": ErrorCode("APP-104", "Business rule error", 400),
    "APP-105": ErrorCode("APP-105", "Duplicate", 409),
    "APP-106": ErrorCode("APP-106", "Service unavailable", 503),
    "APP-107": ErrorCode("APP-107", "Use case error", 422),
    "APP-108": ErrorCode("APP-108", "Session decryption error", 500),
}

# ===== WHK Error Codes =====
# WHK-001..002 — existing (webhook), значения НЕ менять
# WHK-003..010 — новые webhook API errors

WHK_ERROR_CODES: dict[str, ErrorCode] = {
    "WHK-001": ErrorCode("WHK-001", "Chat not found", 404),
    "WHK-002": ErrorCode("WHK-002", "Invalid webhook configuration", 400),
    "WHK-003": ErrorCode("WHK-003", "Webhook delivery failed", 500),
    "WHK-004": ErrorCode("WHK-004", "Webhook timeout", 504),
    "WHK-005": ErrorCode("WHK-005", "Invalid webhook response", 502),
    "WHK-006": ErrorCode("WHK-006", "Webhook not configured", 400),
    "WHK-007": ErrorCode("WHK-007", "Summary generation error", 500),
    "WHK-008": ErrorCode("WHK-008", "Webhook dispatch error", 500),
    "WHK-009": ErrorCode("WHK-009", "Invalid body template", 400),
    "WHK-010": ErrorCode("WHK-010", "Missing required field", 400),
}

# ===== AUTH Error Codes =====

AUTH_ERROR_CODES: dict[str, ErrorCode] = {
    "AUTH-001": ErrorCode("AUTH-001", "Unauthorized", 401),
    "AUTH-002": ErrorCode("AUTH-002", "Token verification failed", 500),
    "AUTH-003": ErrorCode("AUTH-003", "Session store error", 500),
    "AUTH-004": ErrorCode("AUTH-004", "Middleware configuration error", 500),
    "AUTH-101": ErrorCode("AUTH-101", "Missing X-API-Key header", 401),
    "AUTH-102": ErrorCode("AUTH-102", "Invalid API key", 401),
}

# ===== RATE Error Codes =====

RATE_ERROR_CODES: dict[str, ErrorCode] = {
    "RATE-001": ErrorCode("RATE-001", "Service unavailable", 503),
    "RATE-002": ErrorCode("RATE-002", "Rate limit exceeded", 429),
}

# ===== SCH Error Codes =====

SCH_ERROR_CODES: dict[str, ErrorCode] = {
    "SCH-001": ErrorCode("SCH-001", "Chat not found", 404),
    "SCH-002": ErrorCode("SCH-002", "LLM generation error", 500),
    "SCH-003": ErrorCode("SCH-003", "Schedule update error", 500),
    "SCH-004": ErrorCode("SCH-004", "Invalid schedule format", 400),
    "SCH-005": ErrorCode("SCH-005", "Cron parse error", 400),
    "SCH-006": ErrorCode("SCH-006", "Get scheduled chats error", 500),
}

# ===== CONF Error Codes =====

CONF_ERROR_CODES: dict[str, ErrorCode] = {
    "CONF-001": ErrorCode("CONF-001", "Configuration error", 500),
    "CONF-002": ErrorCode("CONF-002", "Invalid configuration value", 400),
    "CONF-003": ErrorCode("CONF-003", "Configuration reload failed", 500),
}

# ===== ALL Error Codes =====

ALL_ERROR_CODES: dict[str, ErrorCode] = {
    **RAG_ERROR_CODES,
    **EXTERNAL_INGEST_ERROR_CODES,
    **SUMMARY_ERROR_CODES,
    **APP_ERROR_CODES,
    **WHK_ERROR_CODES,
    **AUTH_ERROR_CODES,
    **RATE_ERROR_CODES,
    **SCH_ERROR_CODES,
    **CONF_ERROR_CODES,
}


def validate_error_codes_unique() -> list[str]:
    """Проверить уникальность всех кодов в ALL_ERROR_CODES."""
    seen: dict[str, str] = {}
    duplicates: list[str] = []

    sources = {
        "RAG": RAG_ERROR_CODES,
        "EXT": EXTERNAL_INGEST_ERROR_CODES,
        "SUM": SUMMARY_ERROR_CODES,
        "APP": APP_ERROR_CODES,
        "WHK": WHK_ERROR_CODES,
        "AUTH": AUTH_ERROR_CODES,
        "RATE": RATE_ERROR_CODES,
        "SCH": SCH_ERROR_CODES,
        "CONF": CONF_ERROR_CODES,
    }

    for prefix, codes in sources.items():
        for code in codes:
            if code in seen:
                duplicates.append(f"{code} in {prefix} and {seen[code]}")
            else:
                seen[code] = prefix

    return duplicates


__all__ = [
    "ErrorCode",
    "RAG_ERROR_CODES",
    "EXTERNAL_INGEST_ERROR_CODES",
    "SUMMARY_ERROR_CODES",
    "APP_ERROR_CODES",
    "WHK_ERROR_CODES",
    "AUTH_ERROR_CODES",
    "RATE_ERROR_CODES",
    "SCH_ERROR_CODES",
    "CONF_ERROR_CODES",
    "ALL_ERROR_CODES",
    "validate_error_codes_unique",
]
