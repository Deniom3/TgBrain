# Schedule
Languages: [English](schedule.md) | [Русский](schedule_ru.md)

## Overview

The schedule service provides cron-like scheduling for automatic summary generation. Each chat can have an independent schedule that triggers summary generation at specified times.

## Schedule Formats

### Simple Time Format

Specify a time in HH:MM format. The summary will be generated daily at that time.

```json
{"schedule": "09:00", "timezone": "Europe/Moscow"}
```

### Cron Format

Prefix with `cron:` to use full cron expressions.

```json
{"schedule": "cron:0 9 * * 1-5", "timezone": "Europe/Moscow"}
```

This example generates summaries at 9:00 AM on weekdays only.

## Timezone Support

Schedules are stored as UTC times. When you provide a time in `HH:MM` format, the server converts it to UTC using the application's configured timezone (set via the `TIMEZONE` environment variable or app settings).

## How It Works

1. The ScheduleService runs as a background asyncio task
2. Every minute, it checks which schedules match the current UTC time
3. Matching schedules trigger summary generation for their respective chats

## Managing Schedules

### Set Schedule

```bash
curl -X PUT http://localhost:8000/api/v1/settings/chats/{chat_id}/summary/schedule \
  -H "Content-Type: application/json" \
  -d '{"schedule": "09:00"}'
```

The time is interpreted in the application's configured timezone and converted to UTC for storage. You can also use cron expressions:

```bash
curl -X PUT http://localhost:8000/api/v1/settings/chats/{chat_id}/summary/schedule \
  -H "Content-Type: application/json" \
  -d '{"schedule": "0 9 * * *"}'
```

### Get Schedule

```bash
curl http://localhost:8000/api/v1/settings/chats/{chat_id}/summary/schedule
```

### Clear Schedule

```bash
curl -X DELETE http://localhost:8000/api/v1/settings/chats/{chat_id}/summary/schedule
```

## Architecture

```
ScheduleService
  |-- Scheduler           -- Main loop, checks every minute
  |-- TimezoneConverter   -- Local to UTC conversion
  |-- TriggerHandler      -- Triggers summary generation
  |-- ScheduleStore       -- Loads schedules from database
```
