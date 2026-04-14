# Error Codes

Languages: [English](error-codes.md) | [Русский](error-codes_ru.md)

This document lists all error codes used across the API, grouped by prefix.

## APP-* -- Application Errors

| Code | HTTP Status | Description |
|------|-------------|-------------|
| APP-001 | 400 | Invalid timezone |
| APP-002 | 404 | Setting not found |
| APP-003 | 500 | Failed to save timezone setting |

## WHK-* -- Webhook Errors

| Code | HTTP Status | Description |
|------|-------------|-------------|
| WHK-001 | 404 | Chat not found |
| WHK-002 | 400 | Invalid webhook configuration |
| WHK-006 | 400/500 | Webhook not configured or delivery failed |

## RAG-* -- RAG/Search Errors

| Code | HTTP Status | Description |
|------|-------------|-------------|
| RAG-001 | 400 | Invalid question |
| RAG-002 | 400 | Chat not found |
| RAG-003 | 400 | Invalid search_in value |
| RAG-004 | 400 | Invalid top_k |
| RAG-005 | 404 | No relevant messages found |
| RAG-006 | 500 | Embedding generation failed |
| RAG-007 | 500 | LLM generation failed |
| RAG-008 | 500 | Database error |

## EXT-* -- External Ingestion Errors

| Code | HTTP Status | Description |
|------|-------------|-------------|
| EXT-001 | 400 | Invalid request data |
| EXT-002 | 400 | Chat not monitored |
| EXT-003 | 200 | Embedding error (message stored as pending) |
| EXT-004 | 200/500 | Database error |
| EXT-005 | 200 | Filtered message |
| EXT-006 | 200 | Duplicate message |
| EXT-007 | 200 | Embedding service unavailable (message stored as pending) |
| EXT-008 | 413 | File too large |
| EXT-009 | 400 | Invalid chat type |
| EXT-010 | 415 | Invalid content type |
| EXT-013 | 404 | Task not found |
| EXT-014 | 403 | User has no access to chat |
| EXT-015 | 400 | Too many messages |

## INTERNAL_ERROR

| Code | HTTP Status | Description |
|------|-------------|-------------|
| INTERNAL_ERROR | 500 | Unhandled server error |
