# LLM Providers
Languages: [English](llm-providers.md) | [Русский](llm-providers_ru.md)

## Overview

TgBrain supports four LLM providers for summary generation and RAG answer generation.

## Gemini

Google's Gemini models via the official API.

**Configuration:**
- `GEMINI_API_KEY` -- Required API key
- `GEMINI_BASE_URL` -- API base URL (default: generativelanguage.googleapis.com)
- `GEMINI_MODEL` -- Model name (default: gemini-2.5-flash)

**Use case:** Default provider, good balance of quality and speed.

## OpenRouter

Access to 300+ models through the OpenRouter platform.

**Configuration:**
- `OPENROUTER_API_KEY` -- Required API key
- `OPENROUTER_BASE_URL` -- API base URL (default: openrouter.ai/api/v1)
- `OPENROUTER_MODEL` -- Model name (default: auto)

**Use case:** Access to a wide variety of models, fallback provider.

## Ollama

Local models served via Ollama server.

**Configuration:**
- `OLLAMA_LLM_ENABLED` -- Enable/disable (default: true)
- `OLLAMA_LLM_BASE_URL` -- Ollama server URL (default: http://localhost:11434)
- `OLLAMA_LLM_MODEL` -- Model name (default: deepseek-coder:6.7b)

**Use case:** Local inference, no API costs, full data privacy.

**Docker note:** Use `http://host.docker.internal:11434` instead of `localhost` when running in Docker.

## LM Studio

Local models served via LM Studio server.

**Configuration:**
- `LM_STUDIO_ENABLED` -- Enable/disable (default: false)
- `LM_STUDIO_BASE_URL` -- Server URL (default: http://localhost:1234/v1)
- `LM_STUDIO_MODEL` -- Model name
- `LM_STUDIO_API_KEY` -- API key (if required)

**Use case:** Local inference with OpenAI-compatible API.

## Provider Fallback

The system supports automatic fallback when the active provider fails:

- `LLM_FALLBACK_PROVIDERS` -- Comma-separated list of fallback providers
- `LLM_AUTO_FALLBACK` -- Enable automatic fallback (default: true)
- `LLM_FALLBACK_TIMEOUT` -- Timeout before trying fallback (default: 10 seconds)
