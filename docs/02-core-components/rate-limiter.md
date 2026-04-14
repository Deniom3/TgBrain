# Rate Limiter
Languages: [English](rate-limiter.md) | [Русский](rate-limiter_ru.md)

## Overview

The adaptive rate limiter protects against Telegram API FloodWait errors by dynamically adjusting request rates based on server responses.

## How It Works

1. **Track requests** -- Every API request is logged with timing information
2. **Monitor responses** -- FloodWait errors are captured and recorded
3. **Adjust rate** -- The rate limiter reduces the request rate when FloodWait errors occur
4. **Recover gradually** -- The rate is slowly increased after a cooldown period
5. **Persist history** -- Incident history is stored in the database for analysis

## FloodWait Handling

When Telegram returns a FloodWait error, the rate limiter:

1. Records the incident in the `flood_wait_incidents` table
2. Pauses requests for the duration specified by Telegram
3. Reduces the batch size for subsequent requests
4. Logs the incident for monitoring

## Monitoring

### View Current Throughput

```bash
curl http://localhost:8000/api/v1/system/throughput
```

### View FloodWait History

```bash
curl http://localhost:8000/api/v1/system/flood-history
```

### View System Stats

```bash
curl http://localhost:8000/api/v1/system/stats
```

## Configuration

The rate limiter is self-tuning and does not require manual configuration. It adapts based on:

- Recent request frequency
- FloodWait incident frequency
- Time since last incident

## Architecture

```
TelegramRateLimiter
  |-- Request tracking    -- Log each request with timestamp
  |-- Incident recording  -- Store FloodWait events in DB
  |-- Rate adjustment     -- Dynamically modify batch sizes
  |-- History management  -- Query and analyze past incidents
```
