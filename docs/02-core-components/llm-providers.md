# LLM Providers
Languages: [English](llm-providers.md) | [Русский](llm-providers_ru.md)

## Overview

TgBrain supports multiple LLM providers through a unified abstraction layer. The active provider is used for summary generation and RAG answer generation.

## Supported Providers

| Provider | Description |
|----------|-------------|
| Gemini | Google's Gemini models via official API |
| OpenRouter | Access to 300+ models through OpenRouter |
| Ollama | Local models via Ollama server |
| LM Studio | Local models via LM Studio server |

## Provider Selection

The active provider is configured via `LLM_ACTIVE_PROVIDER` in `.env` or through the Settings API. Fallback providers are specified via `LLM_FALLBACK_PROVIDERS`.

## Automatic Fallback

When `LLM_AUTO_FALLBACK` is enabled (default), the system automatically tries fallback providers if the active provider fails. The `LLM_FALLBACK_TIMEOUT` setting controls how long to wait before switching to a fallback.

## Managing Providers via API

### List All Providers

```bash
curl http://localhost:8000/api/v1/settings/llm
```

### Get Specific Provider

```bash
curl http://localhost:8000/api/v1/settings/llm/gemini
```

### Update Provider Settings

```bash
curl -X PUT http://localhost:8000/api/v1/settings/llm/gemini \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "your-key",
    "model": "gemini-2.5-flash"
  }'
```

### Activate Provider

```bash
curl -X POST http://localhost:8000/api/v1/settings/llm/gemini/activate
```

### Check Provider Health

```bash
curl -X POST http://localhost:8000/api/v1/settings/llm/gemini/check
```

## Provider Configuration

Each provider has its own set of configuration options stored in the `llm_providers` database table. Changes made via the API are persisted and survive restarts.
