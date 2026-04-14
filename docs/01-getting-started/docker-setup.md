# Docker Setup
Languages: [English](docker-setup.md) | [Русский](docker-setup_ru.md)

## Overview

TgBrain provides Docker Compose configuration for easy deployment. The compose setup includes:

- PostgreSQL 16 with pgvector extension
- TgBrain application

## Prerequisites

- Docker Desktop for Windows
- Docker Compose v2+

## Starting the Application

### Start All Services

```bash
scripts\start.bat
```

This command runs `docker compose up -d` and starts both PostgreSQL and the application.

### Viewing Logs

```bash
# Application logs
scripts\logs.bat app

# PostgreSQL logs
scripts\logs.bat db

# All logs
scripts\logs.bat
```

### Stopping the Application

```bash
scripts\stop.bat
```

This command runs `docker compose down` and stops all services.

## Docker Compose Configuration

The `docker-compose.yml` defines two services:

### PostgreSQL Service

- Image: `pgvector/pgvector:pg16`
- Port: 5432 (internal only, not exposed to host)
- Volume: `pgdata` for persistent storage
- Health check: Tests database connectivity

### Application Service

- Build: From `Dockerfile`
- Port: 8000 (exposed to host)
- Depends on: PostgreSQL service
- Environment: Loaded from `.env` file
- Volumes: Source code mounted for development

## Docker Networking

### Accessing External Services from Docker

If you run Ollama or other external services on your host machine, use `host.docker.internal` instead of `localhost`:

```env
# Wrong - localhost refers to the container, not your host
OLLAMA_EMBEDDING_URL=http://localhost:11434

# Correct - resolves to the host machine
OLLAMA_EMBEDDING_URL=http://host.docker.internal:11434
```

## Data Persistence

PostgreSQL data is stored in a named Docker volume `pgdata`. This data persists across container restarts and rebuilds.

To reset all data:

```bash
docker compose down -v
```

## Custom Dockerfile

The `Dockerfile` is based on Python 3.12-slim:

1. Installs system dependencies
2. Copies and installs Python requirements
3. Copies application source
4. Exposes port 8000

## Docker Compose for Testing

A separate `docker-compose.test.yml` is available for running tests in an isolated environment:

```bash
docker compose -f docker-compose.test.yml up
```

## Troubleshooting

### Container Won't Start

Check logs for errors:

```bash
scripts\logs.bat
```

### Database Connection Refused

Ensure PostgreSQL is healthy before the application starts:

```bash
docker compose ps
```

The PostgreSQL service should show `(healthy)` status.

### Ollama Not Reachable

Remember to use `host.docker.internal` in your `.env`:

```env
OLLAMA_EMBEDDING_URL=http://host.docker.internal:11434
OLLAMA_LLM_BASE_URL=http://host.docker.internal:11434
```

## Next Steps

1. [Authenticate with Telegram](qr-auth.md)
2. [Configure the application](configuration.md)
