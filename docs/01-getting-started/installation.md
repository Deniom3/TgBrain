# Installation
Languages: [English](installation.md) | [Русский](installation_ru.md)

## System Requirements

- Python 3.12 or higher
- PostgreSQL 14+ with pgvector extension
- Docker and Docker Compose (optional, recommended)
- Telegram API credentials (API ID and API Hash)

## Installation Methods

### Method 1: Docker Compose (Recommended)

The simplest way to run TgBrain is with Docker Compose. This method includes PostgreSQL with pgvector.

```bash
# Start all services
scripts\start.bat

# View logs
scripts\logs.bat app

# Stop all services
scripts\stop.bat
```

### Method 2: Manual Installation

#### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd TelegramMessageSummarizer
```

#### Step 2: Create Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate
```

#### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

#### Step 4: Configure Environment

```bash
copy .env.example .env
```

Edit `.env` with your settings. At minimum, you need:

```env
# Telegram API credentials (required)
TG_API_ID=your_api_id
TG_API_HASH=your_api_hash

# Database (required)
DB_PASSWORD=your_password
```

#### Step 5: Start PostgreSQL

Ensure PostgreSQL is running with the pgvector extension installed.

#### Step 6: Run the Application

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Verification

After starting the application:

- **Swagger UI:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health

The health endpoint returns the status of all subsystems:

```json
{
  "status": "ok",
  "components": {
    "database": "ok",
    "ollama_embeddings": "ok",
    "llm": "ok",
    "telegram": "not_configured"
  },
  "timestamp": "2026-04-10T12:00:00Z"
}
```

Component status values: `ok`, `error`, `degraded`, `not_configured`.

## Next Steps

1. [Configure the application](configuration.md)
2. [Set up Docker](docker-setup.md)
3. [Authenticate with Telegram](qr-auth.md)
