# LLM Providers
Языки: [English](llm-providers.md) | [Русский](llm-providers_ru.md)

## Обзор

TgBrain поддерживает несколько LLM-провайдеров через единый уровень абстракции. Активный провайдер используется для генерации суммаризаций и ответов RAG.

## Поддерживаемые провайдеры

| Провайдер | Описание |
|----------|-------------|
| Gemini | Модели Google Gemini через официальный API |
| OpenRouter | Доступ к 300+ моделям через OpenRouter |
| Ollama | Локальные модели через сервер Ollama |
| LM Studio | Локальные модели через сервер LM Studio |

## Выбор провайдера

Активный провайдер настраивается через `LLM_ACTIVE_PROVIDER` в `.env` или через Settings API. Резервные провайдеры указываются через `LLM_FALLBACK_PROVIDERS`.

## Автоматическое резервирование

Когда `LLM_AUTO_FALLBACK` включено (по умолчанию), система автоматически пытается использовать резервные провайдеры, если активный провайдер не отвечает. Настройка `LLM_FALLBACK_TIMEOUT` определяет, сколько ждать перед переключением на резервный провайдер.

## Управление провайдерами через API

### Список всех провайдеров

```bash
curl http://localhost:8000/api/v1/settings/llm
```

### Получение конкретного провайдера

```bash
curl http://localhost:8000/api/v1/settings/llm/gemini
```

### Обновление настроек провайдера

```bash
curl -X PUT http://localhost:8000/api/v1/settings/llm/gemini \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "your-key",
    "model": "gemini-2.5-flash"
  }'
```

### Активация провайдера

```bash
curl -X POST http://localhost:8000/api/v1/settings/llm/gemini/activate
```

### Проверка работоспособности провайдера

```bash
curl -X POST http://localhost:8000/api/v1/settings/llm/gemini/check
```

## Конфигурация провайдера

Каждый провайдер имеет собственный набор параметров конфигурации, хранящихся в таблице базы данных `llm_providers`. Изменения, внесённые через API, сохраняются и сохраняются после перезапуска.
