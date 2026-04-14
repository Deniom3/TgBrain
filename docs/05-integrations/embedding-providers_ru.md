# Провайдеры эмбеддингов
Языки: [English](embedding-providers.md) | [Русский](embedding-providers_ru.md)

## Обзор

TgBrain поддерживает четыре провайдера эмбеддингов для преобразования текста в векторные представления.

## Ollama

Локальные модели эмбеддингов через сервер Ollama.

**Конфигурация:**
- `OLLAMA_EMBEDDING_URL` -- URL сервера Ollama (по умолчанию: http://localhost:11434)
- `OLLAMA_EMBEDDING_MODEL` -- Имя модели (по умолчанию: nomic-embed-text)
- `OLLAMA_EMBEDDING_DIM` -- Размерность вектора (автоопределяется при первом использовании)
- `OLLAMA_EMBEDDING_MAX_RETRIES` -- Максимальное количество повторных попыток (по умолчанию: 3)
- `OLLAMA_EMBEDDING_TIMEOUT` -- Таймаут запроса в секундах (по умолчанию: 30)
- `OLLAMA_EMBEDDING_NORMALIZE` -- Нормализовать выходные векторы (по умолчанию: true)

**Случай использования:** Провайдер по умолчанию, локальный инференс, отсутствие затрат на API.

**Примечание для Docker:** Используйте `http://host.docker.internal:11434` вместо `localhost` при запуске в Docker.

## Gemini

Модели эмбеддингов Google через API.

**Конфигурация:**
- `GEMINI_EMBEDDING_URL` -- Базовый URL API
- `GEMINI_EMBEDDING_MODEL` -- Имя модели (по умолчанию: text-embedding-004)
- `GEMINI_EMBEDDING_DIM` -- Размерность вектора (по умолчанию: 768)

**Случай использования:** Высококачественные эмбеддинги, облачное решение.

## OpenRouter

Модели эмбеддингов через OpenRouter.

**Конфигурация:**
- `OPENROUTER_EMBEDDING_URL` -- Базовый URL API
- `OPENROUTER_EMBEDDING_MODEL` -- Имя модели (по умолчанию: openai/text-embedding-3-small)
- `OPENROUTER_EMBEDDING_DIM` -- Размерность вектора (по умолчанию: 1536)
- `OPENROUTER_EMBEDDING_BATCH_SIZE` -- Размер пакета (по умолчанию: 20)

**Случай использования:** Доступ к моделям эмбеддингов OpenAI через OpenRouter.

## LM Studio

Локальные модели через сервер LM Studio.

**Конфигурация:**
- `LM_STUDIO_EMBEDDING_URL` -- URL сервера
- `LM_STUDIO_EMBEDDING_MODEL` -- Имя модели
- `LM_STUDIO_EMBEDDING_DIM` -- Размерность вектора
- `LM_STUDIO_EMBEDDING_API_KEY` -- Ключ API (если требуется)

**Случай использования:** Локальный инференс с OpenAI-совместимым API.

## Размерность вектора

Размерность вектора критически важна для индексации pgvector. Она:

1. Автоопределяется при первой генерации эмбеддинга
2. Сохраняется в таблице `embedding_providers`
3. Используется для валидации всех последующих эмбеддингов

Если размерность изменяется (смена модели), требуется полная переиндексация. См. [Переиндексация](../02-core-components/reindex_ru.md).
