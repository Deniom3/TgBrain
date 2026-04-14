# Configuration
Languages: [English](configuration.md) | [Русский](configuration_ru.md)

## Environment Variables

All configuration is managed through environment variables. Copy `.env.example` to `.env` and adjust the values.

### Telegram Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TG_API_ID` | Yes | - | Telegram API ID from my.telegram.org |
| `TG_API_HASH` | Yes | - | Telegram API Hash from my.telegram.org |
| `TG_PHONE_NUMBER` | No | - | Phone number for classic auth (not QR) |
| `TG_CHAT_ENABLE` | No | - | Comma-separated chat IDs to enable on startup |
| `TG_CHAT_DISABLE` | No | - | Comma-separated chat IDs to disable on startup |

### Database Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DB_HOST` | No | localhost | PostgreSQL host |
| `DB_PORT` | No | 5432 | PostgreSQL port |
| `DB_NAME` | No | tg_db | Database name |
| `DB_USER` | No | postgres | Database user |
| `DB_PASSWORD` | Yes | - | Database password |
| `DB_URL` | No | auto-generated | Full connection string (overrides other DB vars) |

### LLM Provider Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_ACTIVE_PROVIDER` | No | gemini | Active LLM provider: gemini, openrouter, ollama, lm-studio |
| `LLM_FALLBACK_PROVIDERS` | No | openrouter,gemini | Comma-separated fallback providers |
| `LLM_AUTO_FALLBACK` | No | true | Enable automatic fallback on failure |
| `LLM_FALLBACK_TIMEOUT` | No | 10 | Timeout in seconds before trying fallback |

#### Gemini LLM

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | Yes* | - | Gemini API key (required if Gemini is active) |
| `GEMINI_BASE_URL` | No | https://generativelanguage.googleapis.com | Base URL |
| `GEMINI_MODEL` | No | gemini-2.5-flash | Model name |

#### OpenRouter LLM

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENROUTER_API_KEY` | Yes* | - | OpenRouter API key (required if OpenRouter is active) |
| `OPENROUTER_BASE_URL` | No | https://openrouter.ai/api/v1 | Base URL |
| `OPENROUTER_MODEL` | No | auto | Model name (auto = let OpenRouter choose) |

#### Ollama LLM

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OLLAMA_LLM_ENABLED` | No | true | Enable Ollama as LLM provider |
| `OLLAMA_LLM_BASE_URL` | No | http://localhost:11434 | Ollama server URL |
| `OLLAMA_LLM_MODEL` | No | deepseek-coder:6.7b | Model name |

#### LM Studio LLM

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LM_STUDIO_ENABLED` | No | false | Enable LM Studio as LLM provider |
| `LM_STUDIO_BASE_URL` | No | http://localhost:1234 | Base URL |
| `LM_STUDIO_MODEL` | No | - | Model name |
| `LM_STUDIO_API_KEY` | No | - | API key (if required) |

### Embedding Provider Settings

#### Ollama Embeddings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OLLAMA_EMBEDDING_PROVIDER` | No | ollama | Active embedding provider |
| `OLLAMA_EMBEDDING_URL` | No | http://localhost:11434 | Ollama server URL |
| `OLLAMA_EMBEDDING_MODEL` | No | nomic-embed-text | Model name |
| `OLLAMA_EMBEDDING_DIM` | No | auto-detected | Vector dimension (auto-detected on first use) |
| `OLLAMA_EMBEDDING_MAX_RETRIES` | No | 3 | Max retry attempts |
| `OLLAMA_EMBEDDING_TIMEOUT` | No | 30 | Request timeout in seconds |
| `OLLAMA_EMBEDDING_NORMALIZE` | No | false | Normalize output vectors |

#### Gemini Embeddings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_EMBEDDING_URL` | No | https://generativelanguage.googleapis.com | Base URL |
| `GEMINI_EMBEDDING_MODEL` | No | text-embedding-004 | Model name |
| `GEMINI_EMBEDDING_DIM` | No | 768 | Vector dimension |

#### OpenRouter Embeddings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENROUTER_EMBEDDING_URL` | No | https://openrouter.ai/api/v1 | Base URL |
| `OPENROUTER_EMBEDDING_MODEL` | No | openai/text-embedding-3-small | Model name |
| `OPENROUTER_EMBEDDING_DIM` | No | 1536 | Vector dimension |
| `OPENROUTER_EMBEDDING_BATCH_SIZE` | No | 20 | Batch size for embedding requests |

#### LM Studio Embeddings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LM_STUDIO_EMBEDDING_URL` | No | http://localhost:1234 | Base URL |
| `LM_STUDIO_EMBEDDING_MODEL` | No | - | Model name |
| `LM_STUDIO_EMBEDDING_DIM` | No | - | Vector dimension |
| `LM_STUDIO_EMBEDDING_API_KEY` | No | - | API key |

### Application Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LOG_LEVEL` | No | INFO | Logging level: DEBUG, INFO, WARNING, ERROR |
| `TIMEZONE` | No | Etc/UTC | Application timezone (IANA format) |
| `SUMMARY_DEFAULT_HOURS` | No | 24 | Default summary period in hours |
| `SUMMARY_MAX_MESSAGES` | No | 50 | Maximum messages per summary |
| `RAG_TOP_K` | No | 5 | Number of results for RAG search |
| `RAG_SCORE_THRESHOLD` | No | 0.3 | Minimum similarity score (0.0-1.0) |

## Settings Storage

Settings are stored in two layers:

1. **Environment variables** - Initial defaults from `.env`
2. **Database** - Runtime overrides stored in `app_settings`, `llm_providers`, `embedding_providers`, and `chat_settings` tables

On startup, the application loads settings from the database if they exist, overriding `.env` values. All changes made through the API are persisted to the database.

## Obtaining Telegram API Credentials

1. Visit https://my.telegram.org
2. Log in with your phone number
3. Go to "API development tools"
4. Create a new application
5. Copy the `API ID` and `API Hash` to your `.env` file

## Next Steps

1. [Set up Docker](docker-setup.md)
2. [Authenticate with Telegram](qr-auth.md)
