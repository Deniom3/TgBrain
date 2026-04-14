# Settings Architecture
Languages: [English](settings-architecture.md) | [Русский](settings-architecture_ru.md)

## Overview

Settings in TgBrain are managed through a two-layer system: environment variables for initial defaults and a database for runtime overrides.

## Settings Layers

```
.env file --> Settings class --> Database --> Runtime
```

1. **Environment variables** -- Initial defaults loaded from `.env` via pydantic-settings
2. **Database** -- Persistent overrides stored in dedicated settings tables
3. **Runtime** -- Active settings used by services

On startup, database values override environment variable defaults.

## Settings Tables

| Table | Purpose |
|-------|---------|
| `llm_providers` | LLM provider configurations |
| `embedding_providers` | Embedding provider configurations |
| `chat_settings` | Per-chat configuration |
| `app_settings` | Application-level settings |
| `reindex_settings` | Reindex service configuration |

## Settings Repositories

Each settings table has a corresponding repository class:

| Repository | Table |
|------------|-------|
| `LLMProvidersRepository` | `llm_providers` |
| `EmbeddingProvidersRepository` | `embedding_providers` |
| `ChatSettingsRepository` | `chat_settings` |
| `AppSettingsRepository` | `app_settings` |
| `PendingCleanupSettingsRepository` | `app_settings` (pending.* keys) |
| `SummaryCleanupSettingsRepository` | `app_settings` (summary_cleanup.* keys) |
| `EncryptionSettingsRepository` | `app_settings` (encryption.* keys) |

## Settings Initialization

On application startup:

1. Load `.env` values into the Settings class
2. Initialize the database connection
3. Run the settings initializer, which:
    - Creates provider entries in the database if they don't exist
    - Applies TG_CHAT_ENABLE/TG_CHAT_DISABLE to chat_settings
    - Syncs .env defaults to the database (without overwriting user changes)

## Runtime Updates

All settings changes made through the API are persisted to the database immediately. Services that depend on settings are notified of changes:

- **Chat monitoring** -- The Ingester cache is invalidated when chat settings change
- **LLM provider** -- The active provider is reloaded on change
- **Embedding provider** -- The active provider is reloaded on change

## Settings API

All settings can be managed through the Settings API endpoints. See [Settings API](../03-api-reference/settings-api.md) for full documentation.
