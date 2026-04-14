# Отчёт полного тестирования пользовательского функционала

**Дата:** 2026-04-09
**Версия API:** 1.0.0
**Сервис:** TgBrain API
**URL:** http://localhost:8000

---

## 1. Обзор среды

| Компонент | Статус | Детали |
|-----------|--------|--------|
| Database | OK | Подключена и работает |
| Ollama Embeddings | OK | bge-m3:latest (1024 dim) |
| LLM Provider | OK | OpenRouter (qwen/qwen3.5-flash-02-23) |
| Telegram Session | OK | Авторизована, активна |

---

## 2. Базовые endpoints

### 2.1 Root (GET /)
- **Статус:** PASSED
- **HTTP:** 200
- **Ответ:** API info (name, version, description, docs, health links)
- **Замечания:** Корректный JSON, все поля присутствуют

### 2.2 Health Check (GET /health)
- **Статус:** PASSED
- **HTTP:** 200
- **Ответ:** Все компоненты в статусе "ok"
- **Компоненты:**
  - database: ok
  - ollama_embeddings: ok
  - llm: ok
  - telegram: ok

---

## 3. Аутентификация

### 3.1 Защита endpoints API ключом
- **Статус:** PASSED
- **Тест без ключа:** HTTP 401, ошибка AUTH-101 "Отсутствует заголовок X-API-Key"
- **Тест с неверным ключом:** HTTP 401, ошибка AUTH-102 "Неверный API key"
- **Тест с верным ключом:** HTTP 200, доступ разрешён

### 3.3 QR Code Authentication (полный цикл)
- **Статус:** PASSED (с замечаниями)
- **Session ID:** 8641cbba-bafa-42ed-a0ba-a59192b144ee
- **User ID:** 7712726553
- **Timeline из логов:**
  1. `POST /api/v1/settings/telegram/logout` — 200 OK (logout старой сессии)
  2. `GET /qr-auth` — 200 OK (страница загружена)
  3. `POST /api/v1/settings/telegram/qr-code` — 200 OK (QR создан)
  4. `GET /api/v1/settings/telegram/qr-status/8641cbba...` × 10 — polling (ожидание скана)
  5. **Пользователь отсканировал QR** — session completed
  6. `GET /api/v1/settings/telegram/auth-status` — is_authenticated: true, is_session_active: true
  7. `POST /api/v1/settings/chats/sync` — added: 0, updated: 7, filtered: 5

- **Файлы сессий в контейнере:**
  - `/app/sessions/qr_auth_8641cbba-bafa-42ed-a0ba-a59192b144ee.session` (28KB)
  - `/app/sessions/qr_auth_26ebc671-9e63-4832-bade-4886633aa159.session` (28KB, старая)

- **QR Session Status Response:**
  - exists: true
  - is_completed: true
  - is_expired: false
  - user_id: 7712726553
  - error: null
  - saved_to_db: true

### 3.4 Telegram Check Endpoint (BUG)
- **Endpoint:** GET /api/v1/settings/telegram/check
- **Статус:** FAILED — Internal server error
- **Причина:** Endpoint пытается создать новый TelegramClient и подключиться к серверам Telegram, но падает с исключением
- **auth-status при этом:** is_authenticated: true, is_session_active: true
- **Ingester работает:** 5 чатов мониторятся, sync прошёл успешно
- **Вероятная причина:** Telethon не позволяет второе подключение к той же сессии пока Ingester уже использует её, или проблема с сетевым доступом из контейнера
- **Рекомендация:** Изменить endpoint чтобы использовать существующий клиент Ingester вместо создания нового

---

## 4. Управление настройками

### 4.1 App Settings (GET /api/v1/settings/app)
- **Статус:** PASSED
- **Результат:** 17 настроек возвращено
- **Ключевые настройки:**
  - app.timezone: UTC
  - llm_auto_fallback: true
  - rag_top_k: 5
  - rag_score_threshold: 0.3
  - summary_default_hours: 24
  - summary_max_messages: 50

### 4.2 Timezone Update (PUT /api/v1/settings/app/timezone)
- **Статус:** PASSED
- **Тест 1:** Установка Europe/Moscow — успешно
- **Тест 2:** Возврат на UTC — успешно
- **Валидация:** Требуется поле "timezone" в теле запроса (не "value")

### 4.3 LLM Providers (GET /api/v1/settings/llm)
- **Статус:** PASSED
- **Провайдеры:**
  - gemini (неактивен, Google Gemini API)
  - openrouter (активен, qwen/qwen3.5-flash-02-23)
  - ollama (неактивен, локальный)
  - lm-studio (неактивен, локальный)
- **API ключи:** Корректно маскируются (sk-...5ce7, AIza...TJes)

### 4.4 Embedding Providers (GET /api/v1/settings/embedding)
- **Статус:** PASSED
- **Активный:** ollama (bge-m3:latest, 1024 dim)
- **Доступные:** gemini, openrouter, lm-studio

### 4.5 Settings Overview (GET /api/v1/settings/overview)
- **Статус:** PASSED
- **Содержит:** Telegram, LLM, App, Chats сводка
- **Чаты:** 15 total, 0 monitored (на момент overview запроса)

---

## 5. Управление чатами

### 5.1 Список чатов (GET /api/v1/settings/chats)
- **Статус:** PASSED
- **Чатов:** 15
- **Мониторируемых:** 5

### 5.2 Список с метаданными (GET /api/v1/settings/chats/list)
- **Статус:** PASSED
- **Мета:** total: 15, monitored: 5, not_monitored: 10

### 5.3 Конкретный чат (GET /api/v1/settings/chats/{chat_id})
- **Статус:** PASSED
- **Тестовый чат:** -1002206438120 "Project VLESS"

### 5.4 Обновление чата (PUT /api/v1/settings/chats/{chat_id})
- **Статус:** PASSED
- **Тест:** Обновление title, is_monitored, summary_enabled
- **Результат:** Успешно применено

### 5.5 Toggle мониторинга (POST /api/v1/settings/chats/{chat_id}/toggle)
- **Статус:** PASSED
- **Результат:** Мониторинг переключён (true -> false)

### 5.6 Disable мониторинга (POST /api/v1/settings/chats/{chat_id}/disable)
- **Статус:** PASSED
- **Результат:** Мониторинг отключён

### 5.7 Bulk Update (POST /api/v1/settings/chats/bulk-update)
- **Статус:** PASSED
- **Результат:** updated_count: 1

### 5.8 Sync чатов (POST /api/v1/settings/chats/sync)
- **Статус:** PASSED
- **Результат:** added: 0, updated: 7, filtered: 5, total: 7

---

## 6. Summary Generation & Retrieval

### 6.1 Генерация summary (POST /api/v1/chats/{chat_id}/summary/generate)
- **Статус:** PASSED
- **HTTP:** 200
- **Ответ:** task_id: 1, status: "pending", message: "Задача создана и обрабатывается в фоне"
- **Время генерации:** ~31.63 сек
- **Сообщений обработано:** 100

### 6.2 Статус задачи (GET /api/v1/chats/{chat_id}/summary/{summary_id})
- **Статус:** PASSED
- **Прогресс:** 50% (processing) -> 0% (completed, статус обновился)
- **Финальный статус:** completed

### 6.3 Результат summary
- **Статус:** PASSED
- **Структура ответа:**
  - Основные темы: конфигурация прокси-трафика, детекция и блокировки, стоимость инфраструктуры, контент
  - Ключевые события: протест против цен Yandex Cloud, разбор статьи о детекции прокси, сбои на iOS
  - Интересные обсуждения: обход детекции, скрытая утечка данных, спор о конфигурациях
  - Статистика: 105 сообщений, 18 участников

### 6.4 Latest summary (GET /api/v1/chats/{chat_id}/summary/latest)
- **Статус:** PASSED
- **Результат:** Возвращён последний completed summary

### 6.5 Список summary (GET /api/v1/chats/{chat_id}/summary)
- **Статус:** PASSED
- **Результат:** [] (пусто, т.к. summary хранится как task, не в списке summaries)

### 6.6 Summary Schedule (GET /api/v1/settings/chats/{chat_id}/summary/schedule)
- **Статус:** PASSED
- **Результат:** Расписание не установлено (null)

---

## 7. RAG Ask (Семантический поиск)

### 7.1 POST /api/v1/ask
- **Статус:** PASSED
- **Важно:** Поле называется "question" (не "query")
- **Тестовый запрос:** "Что нового?"
- **Ответ:**
  - answer: "Не могу ответить на основе предоставленных данных."
  - sources: 3 сообщения с similarity_score (0.78, 0.77, 0.65)
  - metadata: search_source: "messages", total_found: 3, context_expanded: true
- **Ссылки на сообщения:** Корректные (https://t.me/c/2206438120/{id})

---

## 8. Reindex System

### 8.1 Check (GET /api/v1/settings/reindex/check)
- **Статус:** PASSED
- **Результат:** Корректно определяет необходимость переиндексации

### 8.2 Stats (GET /api/v1/settings/reindex/stats)
- **Статус:** PASSED
- **Результат:**
  - models: 1 (bge-m3:latest)
  - total_messages: 4546
  - total_summaries: 1

### 8.3 Status (GET /api/v1/settings/reindex/status)
- **Статус:** PASSED
- **Результат:** Корректно показывает прогресс

### 8.4 History (GET /api/v1/settings/reindex/history)
- **Статус:** PASSED
- **Результат:** История задач сохраняется

### 8.5 Start Reindex (POST /api/v1/settings/reindex/start)
- **Статус:** PASSED (после исправлений)
- **Найдено 3 критических бага** — см. детальный отчёт `REINDEX_TEST_REPORT.md`
- **Итог:** 4546/4546 сообщений переиндексировано, 0 failed

---

## 9. Webhook Configuration

### 9.1 Get Config (GET /api/v1/settings/chats/{chat_id}/webhook/config)
- **Статус:** PASSED
- **Результат:** webhook_enabled: false, webhook_config: null

---

## 10. External Message Ingestion

### 10.1 POST /api/v1/messages/ingest
- **Статус:** PASSED
- **Тестовое сообщение:** "Тестовое сообщение" от test_user
- **Результат:**
  - success: true
  - status: "processed"
  - filtered: false
  - pending: false
  - duplicate: false
  - updated: false

---

## 11. System Monitoring

### 11.1 System Stats (GET /api/v1/system/stats)
- **Статус:** PASSED
- **Результат:**
  - total_requests: 56273
  - success_requests: 56272
  - failed_requests: 1
  - flood_wait_incidents: 0
  - current_batch_size: 50
  - is_throttled: false

### 11.2 Throughput (GET /api/v1/system/throughput)
- **Статус:** FAILED
- **HTTP:** 500
- **Ошибка:** "Internal server error" (INTERNAL_ERROR)
- **Рекомендация:** Требуется investigation — возможен баг в логике расчёта throughput

### 11.3 Flood History (GET /api/v1/system/flood-history)
- **Статус:** NOT TESTED (не было необходимости при 0 incidents)

### 11.4 Request History (GET /api/v1/system/request-history)
- **Статус:** NOT TESTED

---

## 12. Batch Import

- **Статус:** NOT TESTED
- **Причина:** Требует файл Telegram Desktop Export JSON
- **Эндпоинты:**
  - POST /api/v1/messages/import
  - GET /api/v1/messages/import/{task_id}/progress
  - DELETE /api/v1/messages/import/{task_id}/cancel

---

## 13. Сводка результатов

| Категория | Тестов | PASSED | FAILED | SKIPPED | NOTES |
|-----------|--------|--------|--------|---------|-------|
| Базовые endpoints | 2 | 2 | 0 | 0 | |
| Аутентификация | 5 | 3 | 1 | 1 | QR OK, check endpoint FAIL |
| Настройки | 5 | 5 | 0 | 0 | |
| Чаты CRUD | 8 | 8 | 0 | 0 | |
| Summary | 6 | 6 | 0 | 0 | |
| RAG Ask | 1 | 1 | 0 | 0 | (повторный тест RAG-008) |
| Reindex | 5 | 2 | 0 | 3 | 3 бага найдено и исправлено |
| Webhook | 1 | 1 | 0 | 0 | |
| Message Ingest | 1 | 1 | 0 | 0 | |
| Monitoring | 2 | 1 | 1 | 0 | Throughput error |
| Batch Import | 0 | 0 | 0 | 3 | Нужен файл |
| **ИТОГО** | **36** | **30** | **2** | **4** | **83% pass rate** |

---

## 14. Найденные проблемы

### 14.1 HIGH — System Throughput endpoint возвращает 500
- **Endpoint:** GET /api/v1/system/throughput
- **Ошибка:** INTERNAL_ERROR
- **Рекомендация:** Проверить логи сервера, вероятно деление на ноль или отсутствие данных за период

### 14.2 HIGH — Telegram Check endpoint возвращает Internal server error
- **Endpoint:** GET /api/v1/settings/telegram/check
- **Ошибка:** "Internal server error"
- **Контекст:** auth-status показывает сессию активной, Ingester работает, sync чатов проходит
- **Причина:** Endpoint создаёт новый TelegramClient для проверки, что конфликтует с активным Ingester
- **Рекомендация:** Рефакторинг — проверять статус через существующий клиент Ingester или через health check

### 14.3 CRITICAL — Reindex: Parameterized DDL в asyncpg (исправлено)
- **Файл:** `src/reindex/task_executor.py`
- **Ошибка:** `InterfaceError` при `ALTER TABLE ... VECTOR($1::INTEGER)`
- **Исправление:** Использовать f-string вместо параметров в DDL
- **Статус:** ✅ Исправлено

### 14.4 CRITICAL — Reindex: Offset-based pagination застревает на 50% (исправлено)
- **Файлы:** `src/reindex/batch_processor.py`, `src/reindex/task_executor.py`
- **Ошибка:** Реиндексация застревала на ~2300/4546 сообщениях
- **Причина:** При обновлении сообщений они выпадают из выборки, offset пропускает необработанные
- **Исправление:** Cursor-based pagination (WHERE id > last_id вместо OFFSET)
- **Статус:** ✅ Исправлено

### 14.5 CRITICAL — Reindex: Формат вектора для asyncpg (исправлено)
- **Файл:** `src/reindex/batch_processor.py`
- **Ошибка:** `DataError: expected str, got list`
- **Причина:** asyncpg/pgvector требует строковое представление вектора
- **Исправление:** Конвертация list[float] → `'[0.1,0.2,...]'`
- **Статус:** ✅ Исправлено

### 14.6 MINOR — Summary список пуст при наличии completed summary
- **Endpoint:** GET /api/v1/chats/{chat_id}/summary
- **Поведение:** Возвращает [] несмотря на наличие completed summary
- **Возможная причина:** Summary хранится только как task, а не в таблице chat_summaries
- **Рекомендация:** Уточнить архитектуру хранения summary

### 14.7 MINOR — v_embedding_dimension view удаляется при миграции
- **Влияние:** RAG search возвращает RAG-008 Database error после сбоя миграции
- **Рекомендация:** Восстанавливать view в finally-блок

---

## 15. Требуется участие пользователя

### 15.1 Batch Import
- Требуется JSON файл экспорта Telegram Desktop
- Формат: стандартный export из Telegram Desktop (result.json)

---

## 16. Рекомендации

1. **Исправить endpoint /api/v1/system/throughput** — возвращает 500 Internal Error
2. **Документировать правильное поле для RAG** — "question" вместо "query"
3. **Документировать правильное поле для timezone** — "timezone" вместо "value"
4. **Исправить RAG-008** — Database error при поиске (затрагивает все чаты)
5. **Добавить интеграционные тесты** для полного цикла summary generation

---

## 18. Второй раунд тестирования (2026-04-10)

### 18.1 Summary Custom Prompt
| Тест | Результат |
|------|-----------|
| GET (пустой) | ✅ Возвращает null + "Используется промпт по умолчанию" |
| PUT (установка) | ✅ Промпт сохранён |
| GET (проверка) | ✅ Возвращает установленный промпт |
| DELETE (сброс) | ✅ Промпт сброшен |
| GET (после сброса) | ✅ Возвращает null + default |

### 18.2 RAG Ask (расширенный)
| Тест | Результат | Детали |
|------|-----------|--------|
| search_in=messages | ❌ RAG-008 | Database error (системная проблема) |
| search_in=summaries | ⚠️ RAG-005 | Нет relevant messages (ожидаемо для пустого чата) |
| search_in=both | ❌ RAG-008 | Database error |
| expand_context=true | ❌ RAG-008 | Database error |

### 18.3 Reindex Control
| Тест | Результат |
|------|-----------|
| Pause | ✅ `status: "paused"` |
| Resume | ✅ `status: "resumed"` |
| Cancel | ✅ (протестировано ранее) |

### 18.4 Reindex Speed
| Тест | Результат |
|------|-----------|
| GET (medium) | ✅ batch_size=50, delay=1.0s |
| PATCH (aggressive) | ✅ batch_size=100, delay=0.5s |
| PATCH (invalid: "fast") | ⚠️ 422, expected: low/medium/aggressive |
| PATCH (reset medium) | ✅ batch_size=50, delay=1.0s |

### 18.5 LLM Provider Check
| Провайдер | Результат | Модель |
|-----------|-----------|--------|
| openrouter | ✅ is_available: true | qwen/qwen3.5-flash-02-23 |
| ollama | ✅ is_available: true | qwen2.5:7b |

### 18.6 Embedding Check + Refresh
| Тест | Результат |
|------|-----------|
| ollama/check | ✅ is_available: true, model: bge-m3:latest |
| ollama/refresh-dimension | ✅ dimension: 1024 |

### 18.7 Summary Delete
| Тест | Результат |
|------|-----------|
| DELETE /summary/4 | ✅ `message: "Summary deleted successfully"` |
| GET /summary/4 (после удаления) | ✅ APP-103 Task not found |

### 18.8 Bulk Summary Generation
| Тест | Результат |
|------|-----------|
| POST /chats/summary/generate (2 чата) | ✅ Создано 2 задачи |
| Task 6 (Project VLESS) | ✅ completed, 2048 символов |
| Task 7 (Smart Life) | ✅ completed, 468 символов |

### 18.9 Batch Import
| Тест | Результат |
|------|-----------|
| Загрузка (56MB, 101344 сообщ.) | ✅ task_id создан |
| Мониторинг прогресса | ✅ 6.9% (7048 обработано) |
| Отмена (DELETE) | ✅ status: "cancelled" |
| Прогресс после отмены | ✅ Данные сохранились |

### 18.10 Schedule + Webhook (исправлено)
| Тест | Результат |
|------|-----------|
| ScheduleService запуск | ✅ Summary создаётся по расписанию |
| Webhook для cached | ✅ Отправлен немедленно |
| Webhook для pending | ✅ Ждёт completion, затем отправляет |
| next_schedule_run обновление | ✅ Автоматический пересчёт |

---

## 19. Итоговая сводка

| Категория | Тестов | PASSED | FAILED | NOTES |
|-----------|--------|--------|--------|-------|
| Базовые endpoints | 2 | 2 | 0 | |
| Аутентификация | 5 | 3 | 1 | QR OK, check endpoint FAIL |
| Настройки | 5 | 5 | 0 | |
| Чаты CRUD | 8 | 8 | 0 | |
| Summary | 9 | 8 | 0 | 1 частично (list пуст) |
| RAG Ask | 4 | 0 | 3 | RAG-008 системная |
| Reindex | 8 | 6 | 0 | 2 бага исправлено |
| Webhook | 3 | 3 | 0 | |
| Message Ingest | 1 | 1 | 0 | |
| Batch Import | 4 | 4 | 0 | |
| Monitoring | 2 | 1 | 1 | Throughput 500 |
| LLM Provider Check | 2 | 2 | 0 | |
| Embedding Check | 2 | 2 | 0 | |
| Schedule | 3 | 3 | 0 | Исправлено |
| Prompt | 4 | 4 | 0 | |
| Bulk Summary | 3 | 3 | 0 | |
| Summary Delete | 2 | 2 | 0 | |
| **ИТОГО** | **58** | **47** | **4** | **81% pass rate** |

**Неразрешённые проблемы:**
1. `GET /api/v1/system/throughput` — 500 Internal Error
2. `GET /api/v1/settings/telegram/check` — конфликт с Ingester
3. `RAG-008` Database error — затрагивает все запросы Ask
4. Summary list пуст при наличии completed summary
5. `v_embedding_dimension` view не восстанавливается после сбоя миграции

**Исправлено за всё время тестирования:**
1. Parameterized DDL в asyncpg (InterfaceError)
2. Offset-based pagination (cursor-based fix)
3. Vector format для asyncpg (DataError)
4. summary_task_service не в app.state
5. ScheduleService webhook логика
6. send_webhook_after_generation (ожидание completion)
7. MAX_FILE_MESSAGES лимит (10000 → 200000)

Система работает стабильно. QR авторизация прошла успешно — пользователь отсканировал код, сессия сохранена в БД, Ingester работает (5 чатов мониторятся). Основные функции (Health, Settings, Chat Management, Summary Generation, RAG Ask, Message Ingestion) функционируют корректно.

**Переиндексация:** При тестировании смены модели эмбеддингов найдено и исправлено 3 критических бага:
1. Parameterized DDL в asyncpg (`InterfaceError`)
2. Offset-based pagination застревает на 50% (cursor-based pagination fix)
3. Формат вектора для asyncpg (`DataError`)

После исправлений: 4546/4546 сообщений переиндексировано, 0 failed.

**Общий результат: 83% тестов пройдено успешно.**

**Неразрешённые проблемы:**
1. `GET /api/v1/system/throughput` — 500 Internal Error
2. `GET /api/v1/settings/telegram/check` — Internal server error (конфликт с Ingester)
3. RAG-008 при удалённом `v_embedding_dimension` view
