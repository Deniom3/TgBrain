# API Testing Plan

**Версия:** 1.0.0
**Дата:** 03 апреля 2026 г.
**Статус:** Черновик

---

## Содержание

1. [Общие сведения](#1-общие-сведения)
2. [Подготовка к тестированию](#2-подготовка-к-тестированию)
3. [Стратегия тестирования](#3-стратегия-тестирования)
4. [План тестирования по модулям](#4-план-тестирования-по-модулям)
   - [4.1 Health & System](#41-health--system)
   - [4.2 Настройки Telegram](#42-настройки-telegram)
   - [4.3 QR-аутентификация](#43-qr-аутентификация)
   - [4.4 Настройки LLM-провайдеров](#44-настройки-llm-провайдеров)
   - [4.5 Настройки Embedding-провайдеров](#45-настройки-embedding-провайдеров)
   - [4.6 Настройки приложения](#46-настройки-приложения)
   - [4.7 Обзор настроек](#47-обзор-настроек)
   - [4.8 Управление чатами — CRUD](#48-управление-чатами--crud)
   - [4.9 Управление чатами — Операции](#49-управление-чатами--операции)
   - [4.10 Управление чатами — Пользователи и синхронизация](#410-управление-чатами--пользователи-и-синхронизация)
   - [4.11 Настройки Summary](#411-настройки-summary)
   - [4.12 Генерация Summary](#412-генерация-summary)
   - [4.13 Получение Summary](#413-получение-summary)
   - [4.14 Webhook Summary](#414-webhook-summary)
   - [4.15 Конфигурация Webhook](#415-конфигурация-webhook)
   - [4.16 Переиндексация (Reindex)](#416-переиндексация-reindex)
   - [4.17 Скорость переиндексации](#417-скорость-переиндексации)
   - [4.18 RAG & Search](#418-rag--search)
   - [4.19 Внешние сообщения](#419-внешние-сообщения)
   - [4.20 Пакетный импорт](#420-пакетный-импорт)
5. [Тестирование ошибок и граничных случаев](#5-тестирование-ошибок-и-граничных-случаев)
6. [Тестирование безопасности](#6-тестирование-безопасности)
7. [Тестирование производительности](#7-тестирование-производительности)
8. [Интеграционное тестирование](#8-интеграционное-тестирование)
9. [Чек-лист выполнения](#9-чек-лист-выполнения)

---

## 1. Общие сведения

### 1.1 Цель

Проверить корректность работы всех 86 API-эндпоинтов приложения Stellar Knight, включая:
- CRUD-операции
- Бизнес-логику
- Интеграции с внешними сервисами
- Обработку ошибок
- Безопасность
- Производительность

### 1.2 Область применения

- Все эндпоинты REST API v1
- Фоновые задачи (reindex, summary generation, cleanup)
- Интеграции (Telegram, LLM, Embedding, Webhooks)

### 1.3 Используемые инструменты

- **pytest** — основное средство тестирования
- **httpx.AsyncClient** — асинхронные HTTP-запросы
- **Postman/Insomnia** — ручное тестирование
- **Swagger UI** (`/docs`) — интерактивная документация

---

## 2. Подготовка к тестированию

### 2.1 Требования

| Компонент | Требование |
|-----------|------------|
| Python | 3.12+ |
| PostgreSQL | 15+ (локально или Docker) |
| Ollama | запущен на `http://localhost:11434` |
| Telegram API | валидные `TG_API_ID` и `TG_API_HASH` |

### 2.2 Настройка тестового окружения

```bash
# Активация venv
venv\Scripts\activate

# Установка зависимостей
pip install -r requirements.txt

# Запуск тестовой БД (Docker)
docker-compose up -d postgres

# Запуск приложения
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 2.3 Тестовые данные

| Данные | Значение |
|--------|----------|
| Тестовый чат ID | `-1001234567890` |
| Тестовый пользователь | `test_user_123` |
| Тестовый LLM-провайдер | `openai` |
| Тестовый embedding-провайдер | `ollama` |
| Тестовая сессия QR | `test-session-id` |

### 2.4 Порядок выполнения

1. Health & System (базовая проверка работоспособности)
2. Настройки Telegram + QR Auth (аутентификация)
3. Настройки LLM/Embedding (зависимости для RAG)
4. Управление чатами (основная сущность)
5. Настройки Summary
6. Генерация и получение Summary
7. Переиндексация
8. RAG & Search
9. Внешние сообщения и импорт
10. Webhook
11. Тестирование ошибок и безопасности
12. Производительность и нагрузочное тестирование

---

## 3. Стратегия тестирования

### 3.1 Уровни тестирования

| Уровень | Описание | Инструмент |
|---------|----------|------------|
| Unit | Отдельные функции и методы | pytest |
| Integration | Взаимодействие компонентов | pytest + httpx |
| E2E | Полные сценарии через API | httpx/Postman |

### 3.2 Типы тестов

| Тип | Цель |
|-----|------|
| Positive | Проверка корректной работы при валидных данных |
| Negative | Проверка обработки невалидных данных |
| Boundary | Проверка граничных значений параметров |
| Security | Проверка авторизации и валидации |
| Performance | Проверка времени отклика и нагрузки |

### 3.3 Статусы тестов

- ✅ **PASS** — тест пройден успешно
- ❌ **FAIL** — тест провален
- ⚠️ **WARN** — тест пройден с предупреждениями
- ⏭️ **SKIP** — тест пропущен (нет зависимостей)

---

## 4. План тестирования по модулям

### 4.1 Health & System

**Цель:** Проверить доступность и корректность ответов всех системных эндпоинтов.

| # | Тест | Метод | Эндпоинт | Ожидаемый результат |
|---|------|-------|----------|---------------------|
| H1 | Проверка health (все компоненты доступны) | GET | `/health` | `status: "healthy"`, все компоненты `ok` |
| H2 | Проверка health (БД недоступна) | GET | `/health` | `status: "unhealthy"`, `database: "error"` |
| H3 | Проверка health (Telegram недоступен) | GET | `/health` | `status: "degraded"`, `telegram: "error"` |
| H4 | Статистика системы | GET | `/api/v1/system/stats` | Возвращает `rate_limiter`, `requests`, `incidents` |
| H5 | Пропускная способность | GET | `/api/v1/system/throughput` | Возвращает `rpm`, `rph` |
| H6 | История FloodWait | GET | `/api/v1/system/flood-history` | Возвращает список инцидентов |
| H7 | История FloodWait с лимитом | GET | `/api/v1/system/flood-history?limit=5` | Возвращает не более 5 записей |
| H8 | История FloodWait без статистики | GET | `/api/v1/system/flood-history?include_stats=false` | Без поля `stats` в ответе |
| H9 | История запросов к Telegram | GET | `/api/v1/system/request-history?limit=10` | Возвращает до 10 записей |

---

### 4.2 Настройки Telegram

**Цель:** Проверить CRUD-операции и управление сессией Telegram.

| # | Тест | Метод | Эндпоинт | Ожидаемый результат |
|---|------|-------|----------|---------------------|
| T1 | Получить настройки Telegram | GET | `/api/v1/settings/telegram` | Возвращает `api_id`, `api_hash`, `phone_number`, `session_name` |
| T2 | Обновить настройки Telegram | PUT | `/api/v1/settings/telegram` | `success: true`, настройки сохранены |
| T3 | Обновить настройки (пустой api_id) | PUT | `/api/v1/settings/telegram` | Ошибка валидации (400) |
| T4 | Проверка здоровья сессии | GET | `/api/v1/settings/telegram/check` | `connected: true/false` |
| T5 | Статус авторизации | GET | `/api/v1/settings/telegram/auth-status` | `authorized: true/false`, `phone` |
| T6 | Выход из сессии | POST | `/api/v1/settings/telegram/logout` | `success: true`, сессия завершена |
| T7 | Выход без активной сессии | POST | `/api/v1/settings/telegram/logout` | `success: false` или соответствующее сообщение |

---

### 4.3 QR-аутентификация

**Цель:** Проверить полный цикл QR-аутентификации.

| # | Тест | Метод | Эндпоинт | Ожидаемый результат |
|---|------|-------|----------|---------------------|
| Q1 | Создание QR-сессии | POST | `/api/v1/settings/telegram/qr-code` | Возвращает `session_id`, `qr_code` (изображение/data URL) |
| Q2 | Проверка статуса (ожидание) | GET | `/api/v1/settings/telegram/qr-status/{session_id}` | `status: "waiting"` |
| Q3 | Проверка статуса (неверный session_id) | GET | `/api/v1/settings/telegram/qr-status/invalid` | Ошибка (404) |
| Q4 | Отмена QR-сессии | POST | `/api/v1/settings/telegram/qr-cancel/{session_id}` | `success: true`, сессия отменена |
| Q5 | Отмена несуществующей сессии | POST | `/api/v1/settings/telegram/qr-cancel/invalid` | Ошибка (404) |
| Q6 | Полный цикл аутентификации | COMBO | POST qr-code → статус → авторизация | Сессия переходит в `authorized` |

---

### 4.4 Настройки LLM-провайдеров

**Цель:** Проверить управление LLM-провайдерами.

| # | Тест | Метод | Эндпоинт | Ожидаемый результат |
|---|------|-------|----------|---------------------|
| L1 | Получить все LLM-провайдеры | GET | `/api/v1/settings/llm` | Список всех провайдеров |
| L2 | Получить конкретный провайдер | GET | `/api/v1/settings/llm/openai` | Настройки `openai` |
| L3 | Получить несуществующий провайдер | GET | `/api/v1/settings/llm/invalid` | Ошибка (404) |
| L4 | Обновить настройки провайдера | PUT | `/api/v1/settings/llm/openai` | `success: true`, настройки обновлены |
| L5 | Обновить (невалидный URL) | PUT | `/api/v1/settings/llm/openai` | Ошибка валидации (400) |
| L6 | Активировать провайдер | POST | `/api/v1/settings/llm/openai/activate` | `success: true`, `is_active: true` |
| L7 | Проверка здоровья провайдера | POST | `/api/v1/settings/llm/openai/check` | `healthy: true/false`, задержка |
| L8 | Проверка здоровья (недоступный) | POST | `/api/v1/settings/llm/invalid/check` | `healthy: false`, ошибка подключения |

---

### 4.5 Настройки Embedding-провайдеров

**Цель:** Проверить управление embedding-провайдерами и переиндексацию при смене модели.

| # | Тест | Метод | Эндпоинт | Ожидаемый результат |
|---|------|-------|----------|---------------------|
| E1 | Получить все embedding-провайдеры | GET | `/api/v1/settings/embedding` | Список всех провайдеров |
| E2 | Получить конкретный провайдер | GET | `/api/v1/settings/embedding/ollama` | Настройки `ollama` |
| E3 | Обновить настройки провайдера | PUT | `/api/v1/settings/embedding/ollama` | `success: true` |
| E4 | Обновить модель (trigger reindex) | PUT | `/api/v1/settings/embedding/ollama/model` | `success: true`, `reindex_triggered: true` |
| E5 | Обновить модель (та же модель) | PUT | `/api/v1/settings/embedding/ollama/model` | `success: true`, `reindex_triggered: false` |
| E6 | Активировать провайдер | POST | `/api/v1/settings/embedding/ollama/activate` | `success: true` |
| E7 | Проверка здоровья провайдера | POST | `/api/v1/settings/embedding/ollama/check` | `healthy: true/false` |
| E8 | Обновить размерность (Ollama) | POST | `/api/v1/settings/embedding/ollama/refresh-dimension` | `embedding_dim` обновлён |
| E9 | Обновить размерность (не Ollama) | POST | `/api/v1/settings/embedding/openai/refresh-dimension` | Ошибка или игнорирование |

---

### 4.6 Настройки приложения

**Цель:** Проверить управление общими настройками приложения.

| # | Тест | Метод | Эндпоинт | Ожидаемый результат |
|---|------|-------|----------|---------------------|
| A1 | Получить все настройки | GET | `/api/v1/settings/app` | Список всех настроек |
| A2 | Получить конкретную настройку | GET | `/api/v1/settings/app/{key}` | Значение настройки |
| A3 | Получить несуществующую настройку | GET | `/api/v1/settings/app/invalid` | Ошибка (404) |
| A4 | Обновить настройку | PUT | `/api/v1/settings/app/{key}` | `success: true` |
| A5 | Обновить настройку (невалидное значение) | PUT | `/api/v1/settings/app/{key}` | Ошибка валидации (400) |
| A6 | Установить часовой пояс | PUT | `/api/v1/settings/app/timezone` | `success: true`, `timezone: "Europe/Moscow"` |
| A7 | Установить невалидный часовой пояс | PUT | `/api/v1/settings/app/timezone` | Ошибка (400) |

---

### 4.7 Обзор настроек

**Цель:** Проверить сводную информацию о всех настройках.

| # | Тест | Метод | Эндпоинт | Ожидаемый результат |
|---|------|-------|----------|---------------------|
| O1 | Получить обзор настроек | GET | `/api/v1/settings/overview` | Сводка по Telegram, LLM, Embedding, чатам |

---

### 4.8 Управление чатами — CRUD

**Цель:** Проверить создание, чтение, обновление и удаление настроек чатов.

| # | Тест | Метод | Эндпоинт | Ожидаемый результат |
|---|------|-------|----------|---------------------|
| C1 | Получить все чаты | GET | `/api/v1/settings/chats` | Список всех чатов |
| C2 | Получить список чатов с метаданными | GET | `/api/v1/settings/chats/list` | Список + мета-информация |
| C3 | Получить только monitored чаты | GET | `/api/v1/settings/chats/monitored` | Только чаты с `is_monitored: true` |
| C4 | Получить конкретный чат | GET | `/api/v1/settings/chats/{chat_id}` | Настройки чата |
| C5 | Получить несуществующий чат | GET | `/api/v1/settings/chats/invalid` | Ошибка (404) |
| C6 | Обновить настройки чата | PUT | `/api/v1/settings/chats/{chat_id}` | `success: true`, настройки обновлены |
| C7 | Удалить чат | DELETE | `/api/v1/settings/chats/{chat_id}` | `success: true`, чат удалён |
| C8 | Удалить несуществующий чат | DELETE | `/api/v1/settings/chats/invalid` | Ошибка (404) |

---

### 4.9 Управление чатами — Операции

**Цель:** Проверить операции управления мониторингом чатов.

| # | Тест | Метод | Эндпоинт | Ожидаемый результат |
|---|------|-------|----------|---------------------|
| O1 | Включить мониторинг | POST | `/api/v1/settings/chats/{chat_id}/enable` | `is_monitored: true` |
| O2 | Отключить мониторинг | POST | `/api/v1/settings/chats/{chat_id}/disable` | `is_monitored: false` |
| O3 | Переключить мониторинг (вкл→выкл) | POST | `/api/v1/settings/chats/{chat_id}/toggle` | `is_monitored: false` |
| O4 | Переключить мониторинг (выкл→вкл) | POST | `/api/v1/settings/chats/{chat_id}/toggle` | `is_monitored: true` |
| O5 | Массовое обновление (включить) | POST | `/api/v1/settings/chats/bulk-update` | Все указанные чаты `is_monitored: true` |
| O6 | Массовое обновление (отключить) | POST | `/api/v1/settings/chats/bulk-update` | Все указанные чаты `is_monitored: false` |
| O7 | Массовое обновление (пустой список) | POST | `/api/v1/settings/chats/bulk-update` | Ошибка валидации (400) |
| O8 | Массовое обновление (несуществующие чаты) | POST | `/api/v1/settings/chats/bulk-update` | Частичный успех или ошибка |

---

### 4.10 Управление чатами — Пользователи и синхронизация

**Цель:** Проверить синхронизацию с Telegram и управление пользователями.

| # | Тест | Метод | Эндпоинт | Ожидаемый результат |
|---|------|-------|----------|---------------------|
| S1 | Синхронизация чатов с Telegram | POST | `/api/v1/settings/chats/sync` | `success: true`, добавлены новые чаты |
| S2 | Синхронизация без подключения к Telegram | POST | `/api/v1/settings/chats/sync` | Ошибка подключения |
| S3 | Добавить пользователя по ID | POST | `/api/v1/settings/chats/user/add` | Пользователь добавлен, `is_monitored: true` |
| S4 | Добавить пользователя по username | POST | `/api/v1/settings/chats/user/add` | Пользователь добавлен |
| S5 | Добавить пользователя (невалидный ID) | POST | `/api/v1/settings/chats/user/add` | Ошибка (400) |
| S6 | Удалить пользователя | POST | `/api/v1/settings/chats/user/remove` | Пользователь удалён |
| S7 | Удалить несуществующего пользователя | POST | `/api/v1/settings/chats/user/remove` | Ошибка (404) |

---

### 4.11 Настройки Summary

**Цель:** Проверить настройки генерации summary для чатов.

| # | Тест | Метод | Эндпоинт | Ожидаемый результат |
|---|------|-------|----------|---------------------|
| SS1 | Включить summary | POST | `/api/v1/settings/chats/{chat_id}/summary/enable` | `summary_enabled: true` |
| SS2 | Отключить summary | POST | `/api/v1/settings/chats/{chat_id}/summary/disable` | `summary_enabled: false` |
| SS3 | Переключить summary | POST | `/api/v1/settings/chats/{chat_id}/summary/toggle` | Статус изменён на противоположный |
| SS4 | Установить период (60 мин) | PUT | `/api/v1/settings/chats/{chat_id}/summary/period` | `period_minutes: 60` |
| SS5 | Установить период (0 мин) | PUT | `/api/v1/settings/chats/{chat_id}/summary/period` | Ошибка валидации (400) |
| SS6 | Установить период (10080 мин) | PUT | `/api/v1/settings/chats/{chat_id}/summary/period` | `period_minutes: 10080` (максимум) |
| SS7 | Установить период (10081 мин) | PUT | `/api/v1/settings/chats/{chat_id}/summary/period` | Ошибка валидации (400) |
| SS8 | Установить расписание | PUT | `/api/v1/settings/chats/{chat_id}/summary/schedule` | `schedule` сохранён |
| SS9 | Установить невалидное расписание | PUT | `/api/v1/settings/chats/{chat_id}/summary/schedule` | Ошибка валидации (400) |
| SS10 | Получить расписание | GET | `/api/v1/settings/chats/{chat_id}/summary/schedule` | Текущее расписание |
| SS11 | Очистить расписание | DELETE | `/api/v1/settings/chats/{chat_id}/summary/schedule` | `schedule: null` |
| SS12 | Установить кастомный промпт | PUT | `/api/v1/settings/chats/{chat_id}/summary/prompt` | `custom_prompt` сохранён |
| SS13 | Получить кастомный промпт | GET | `/api/v1/settings/chats/{chat_id}/summary/prompt` | Текущий промпт |
| SS14 | Очистить кастомный промпт | DELETE | `/api/v1/settings/chats/{chat_id}/summary/prompt` | `custom_prompt: null` |

---

### 4.12 Генерация Summary

**Цель:** Проверить асинхронную генерацию summary.

| # | Тест | Метод | Эндпоинт | Ожидаемый результат |
|---|------|-------|----------|---------------------|
| SG1 | Генерация для одного чата | POST | `/api/v1/chats/{chat_id}/summary/generate` | Возвращает `task_id`, `status: "pending"` |
| SG2 | Генерация с периодом | POST | `/api/v1/chats/{chat_id}/summary/generate` | `task_id`, период учтён |
| SG3 | Генерация с кастомным промптом | POST | `/api/v1/chats/{chat_id}/summary/generate` | `task_id`, промпт учтён |
| SG4 | Генерация без кэша | POST | `/api/v1/chats/{chat_id}/summary/generate` | `from_cache: false` |
| SG5 | Генерация с кэшем | POST | `/api/v1/chats/{chat_id}/summary/generate` | `from_cache: true` (если есть кэш) |
| SG6 | Генерация для всех чатов | POST | `/api/v1/chats/summary/generate` | Массив `task_id` для каждого чата |
| SG7 | Генерация для выбранных чатов | POST | `/api/v1/chats/summary/generate` | `task_id` только для указанных чатов |
| SG8 | Генерация для несуществующего чата | POST | `/api/v1/chats/{invalid}/summary/generate` | Ошибка (404) |
| SG9 | Генерация с max_messages | POST | `/api/v1/chats/{chat_id}/summary/generate` | Ограничение сообщений учтено |
| SG10 | Проверка статуса задачи | GET | `/api/v1/chats/{chat_id}/summary/{task_id}` | `status: "completed"/"pending"/"failed"` |

---

### 4.13 Получение Summary

**Цель:** Проверить retrieval и управление сохранёнными summary.

| # | Тест | Метод | Эндпоинт | Ожидаемый результат |
|---|------|-------|----------|---------------------|
| SR1 | Список summary (пагинация) | GET | `/api/v1/chats/{chat_id}/summary` | Список summary, `total`, `limit`, `offset` |
| SR2 | Список summary (default pagination) | GET | `/api/v1/chats/{chat_id}/summary` | Первые 10 summary |
| SR3 | Список summary (limit=5, offset=10) | GET | `/api/v1/chats/{chat_id}/summary?limit=5&offset=10` | 5 summary начиная с 11-го |
| SR4 | Последнее summary | GET | `/api/v1/chats/{chat_id}/summary/latest` | Самое свежее summary |
| SR5 | Последнее summary (нет summary) | GET | `/api/v1/chats/{chat_id}/summary/latest` | Ошибка (404) или пустой ответ |
| SR6 | Получить конкретное summary | GET | `/api/v1/chats/{chat_id}/summary/{id}` | Полное summary |
| SR7 | Получить несуществующее summary | GET | `/api/v1/chats/{chat_id}/summary/{invalid}` | Ошибка (404) |
| SR8 | Удалить summary | DELETE | `/api/v1/chats/{chat_id}/summary/{id}` | `success: true` |
| SR9 | Удалить несуществующее summary | DELETE | `/api/v1/chats/{chat_id}/summary/{invalid}` | Ошибка (404) |
| SR10 | Очистка старых summary | POST | `/api/v1/chats/{chat_id}/summary/cleanup` | Удалены summary старше `older_than_days` |
| SR11 | Очистка (0 дней) | POST | `/api/v1/chats/{chat_id}/summary/cleanup` | Ошибка валидации (400) |
| SR12 | Статистика summary | GET | `/api/v1/chats/summary/stats` | Статистика по всем чатам |

---

### 4.14 Webhook Summary

**Цель:** Проверить отправку summary через webhook.

| # | Тест | Метод | Эндпоинт | Ожидаемый результат |
|---|------|-------|----------|---------------------|
| SW1 | Отправка summary на webhook | POST | `/api/v1/chats/{chat_id}/summary/send-webhook` | `success: true`, webhook вызван |
| SW2 | Отправка без настроенного webhook | POST | `/api/v1/chats/{chat_id}/summary/send-webhook` | Ошибка (400) — webhook не настроен |
| SW3 | Отправка с кастомным промптом | POST | `/api/v1/chats/{chat_id}/summary/send-webhook` | Summary сгенерировано с промптом |

---

### 4.15 Конфигурация Webhook

**Цель:** Проверить управление webhook-конфигурацией.

| # | Тест | Метод | Эндпоинт | Ожидаемый результат |
|---|------|-------|----------|---------------------|
| WC1 | Установить webhook | PUT | `/api/v1/settings/chats/{chat_id}/webhook/config` | `success: true`, конфигурация сохранена |
| WC2 | Установить webhook (невалидный URL) | PUT | `/api/v1/settings/chats/{chat_id}/webhook/config` | Ошибка валидации (400) |
| WC3 | Получить webhook | GET | `/api/v1/settings/chats/{chat_id}/webhook/config` | Текущая конфигурация |
| WC4 | Получить webhook (не настроен) | GET | `/api/v1/settings/chats/{chat_id}/webhook/config` | Пустой ответ или `null` |
| WC5 | Удалить webhook | DELETE | `/api/v1/settings/chats/{chat_id}/webhook/config` | `success: true`, webhook удалён |
| WC6 | Тестовый webhook | POST | `/api/v1/settings/chats/{chat_id}/webhook/test` | `success: true`, тестовый запрос отправлен |
| WC7 | Тестовый webhook (не настроен) | POST | `/api/v1/settings/chats/{chat_id}/webhook/test` | Ошибка (400) |

---

### 4.16 Переиндексация (Reindex)

**Цель:** Проверить управление переиндексацией векторных данных.

| # | Тест | Метод | Эндпоинт | Ожидаемый результат |
|---|------|-------|----------|---------------------|
| R1 | Проверка необходимости переиндексации | GET | `/api/v1/settings/reindex/check` | `needs_reindex: true/false`, причина |
| R2 | Проверка (смена модели) | GET | `/api/v1/settings/reindex/check` | `needs_reindex: true`, `reason: "model_changed"` |
| R3 | Статус сервиса | GET | `/api/v1/settings/reindex/status` | `status: "idle"/"running"/"paused"`, прогресс |
| R4 | Статистика моделей | GET | `/api/v1/settings/reindex/stats` | Статистика по моделям и векторам |
| R5 | Запуск переиндексации | POST | `/api/v1/settings/reindex/start` | `success: true`, `task_id` |
| R6 | Запуск с параметрами | POST | `/api/v1/settings/reindex/start` | Параметры применены |
| R7 | Запуск (уже запущена) | POST | `/api/v1/settings/reindex/start` | Ошибка (409) — уже выполняется |
| R8 | Пауза переиндексации | POST | `/api/v1/settings/reindex/control` | `status: "paused"` |
| R9 | Возобновление переиндексации | POST | `/api/v1/settings/reindex/control` | `status: "running"` |
| R10 | Отмена переиндексации | POST | `/api/v1/settings/reindex/control` | `status: "cancelled"` |
| R11 | Управление (нет активной задачи) | POST | `/api/v1/settings/reindex/control` | Ошибка (400) — нет активной задачи |
| R12 | История задач | GET | `/api/v1/settings/reindex/history` | Список последних задач |
| R13 | История с лимитом | GET | `/api/v1/settings/reindex/history?limit=3` | Не более 3 записей |

---

### 4.17 Скорость переиндексации

**Цель:** Проверить управление скоростью переиндексации.

| # | Тест | Метод | Эндпоинт | Ожидаемый результат |
|---|------|-------|----------|---------------------|
| RS1 | Получить текущий режим | GET | `/api/v1/settings/reindex/speed` | `speed_mode: "low"/"medium"/"aggressive"` |
| RS2 | Установить режим low | PATCH | `/api/v1/settings/reindex/speed` | `success: true`, `speed_mode: "low"` |
| RS3 | Установить режим medium | PATCH | `/api/v1/settings/reindex/speed` | `success: true`, `speed_mode: "medium"` |
| RS4 | Установить режим aggressive | PATCH | `/api/v1/settings/reindex/speed` | `success: true`, `speed_mode: "aggressive"` |
| RS5 | Установить невалидный режим | PATCH | `/api/v1/settings/reindex/speed` | Ошибка валидации (400) |

---

### 4.18 RAG & Search

**Цель:** Проверить семантический поиск и генерацию ответов.

| # | Тест | Метод | Эндпоинт | Ожидаемый результат |
|---|------|-------|----------|---------------------|
| ASK1 | Поиск в сообщениях | POST | `/api/v1/ask` | Ответ на основе сообщений |
| ASK2 | Поиск в summary | POST | `/api/v1/ask` | Ответ на основе summary |
| ASK3 | Поиск везде | POST | `/api/v1/ask` | Комбинированный ответ |
| ASK4 | Поиск с указанием чата | POST | `/api/v1/ask` | Ответ только из указанного чата |
| ASK5 | Поиск без индекса | POST | `/api/v1/ask` | Ошибка или сообщение о пустом индексе |
| ASK6 | Пустой вопрос | POST | `/api/v1/ask` | Ошибка валидации (400) |
| ASK7 | Поиск с top_k=5 | POST | `/api/v1/ask` | Не более 5 результатов в контексте |
| ASK8 | Поиск с expand_context | POST | `/api/v1/ask` | Расширенный контекст в ответе |

---

### 4.19 Внешние сообщения

**Цель:** Проверить приём сообщений из внешних источников.

| # | Тест | Метод | Эндпоинт | Ожидаемый результат |
|---|------|-------|----------|---------------------|
| EX1 | Успешная ingest | POST | `/api/v1/messages/ingest` | `success: true`, `message_id` |
| EX2 | Ingest (чат не мониторится) | POST | `/api/v1/messages/ingest` | Ошибка (400), код `EXT-002` |
| EX3 | Ingest (пустой текст) | POST | `/api/v1/messages/ingest` | Ошибка валидации (400), код `EXT-001` |
| EX4 | Ingest (несуществующий чат) | POST | `/api/v1/messages/ingest` | Ошибка (400), код `EXT-002` |
| EX5 | Ingest (дубликат) | POST | `/api/v1/messages/ingest` | `duplicate: true` |
| EX6 | Ingest (фильтрация) | POST | `/api/v1/messages/ingest` | `filtered: true` |
| EX7 | Ingest (ошибка embedding) | POST | `/api/v1/messages/ingest` | `status: "pending"`, код `EXT-003` |
| EX8 | Ingest (невалидная дата) | POST | `/api/v1/messages/ingest` | Ошибка валидации (400) |

---

### 4.20 Пакетный импорт

**Цель:** Проверить импорт сообщений пакетами.

| # | Тест | Метод | Эндпоинт | Ожидаемый результат |
|---|------|-------|----------|---------------------|
| IM1 | Импорт JSON-данных | POST | `/api/v1/messages/import` | `task_id`, `status: "pending"` |
| IM2 | Импорт файла | POST | `/api/v1/messages/import` | `task_id`, файл принят |
| IM3 | Импорт (пустые данные) | POST | `/api/v1/messages/import` | Ошибка валидации (400) |
| IM4 | Импорт (несуществующий чат) | POST | `/api/v1/messages/import` | Ошибка (400) |
| IM5 | Проверка прогресса | GET | `/api/v1/messages/import/{task_id}/progress` | `progress: 0-100`, `status` |
| IM6 | Прогресс (несуществующая задача) | GET | `/api/v1/messages/import/{invalid}/progress` | Ошибка (404) |
| IM7 | Отмена импорта | DELETE | `/api/v1/messages/import/{task_id}/cancel` | `success: true`, задача отменена |
| IM8 | Отмена завершённого импорта | DELETE | `/api/v1/messages/import/{task_id}/cancel` | Ошибка (400) — уже завершён |
| IM9 | Полный цикл импорта | COMBO | POST import → GET progress → завершение | Все сообщения импортированы |

---

## 5. Тестирование ошибок и граничных случаев

### 5.1 Валидация входных данных

| # | Тест | Описание |
|---|------|----------|
| V1 | Отправка пустого тела запроса | Должен вернуть 422 Unprocessable Entity |
| V2 | Отправка невалидного JSON | Должен вернуть 400 Bad Request |
| V3 | Отправка невалидного типа данных | Должен вернуть 422 |
| V4 | Превышение максимальной длины строки | Должен вернуть 422 |
| V5 | Отрицательные значения для положительных полей | Должен вернуть 422 |
| V6 | Невалидный формат даты | Должен вернуть 422 |
| V7 | Невалидный формат email/URL | Должен вернуть 422 |

### 5.2 Обработка ошибок сервера

| # | Тест | Описание |
|---|------|----------|
| E1 | Отключение БД во время запроса | Должен вернуть 500 с понятным сообщением |
| E2 | Отключение embedding-сервиса | Должен вернуть 503 или pending статус |
| E3 | Отключение LLM-сервиса | Должен вернуть 503 |
| E4 | Отключение Telegram | Должен вернуть ошибку с кодом |
| E5 | Таймаут внешнего сервиса | Должен вернуть 504 или обработать gracefully |
| E6 | Переполнение диска | Должен вернуть 507 |

### 5.3 Граничные значения

| # | Тест | Описание |
|---|------|----------|
| B1 | Минимальное значение pagination (limit=1) | Должен работать корректно |
| B2 | Максимальное значение pagination (limit=1000) | Должен работать или вернуть ограничение |
| B3 | Пустой массив в bulk-операциях | Должен вернуть ошибку валидации |
| B4 | Очень длинный текст сообщения (10000+ символов) | Должен обработать или отклонить |
| B5 | Одновременные запросы к одному ресурсу | Должен обработать корректно (race condition) |

---

## 6. Тестирование безопасности

### 6.1 Авторизация и доступ

| # | Тест | Описание |
|---|------|----------|
| SEC1 | Доступ к защищённым эндпоинтам без auth | Должен вернуть 401 |
| SEC2 | Доступ с невалидным токеном | Должен вернуть 401 |
| SEC3 | Доступ с истёкшим токеном | Должен вернуть 401 |
| SEC4 | Доступ к эндпоинтам с необходимыми правами | Должен вернуть 403 при недостатке прав |
| SEC5 | CSRF-защита (если применимо) | Должен отклонить запросы без CSRF-токена |

### 6.2 Валидация и инъекции

| # | Тест | Описание |
|---|------|----------|
| SEC6 | SQL-инъекция в параметрах | Должен отклонить запрос |
| SEC7 | XSS в текстовых полях | Должен экранировать или отклонить |
| SEC8 | Path traversal в путях | Должен отклонить запрос |
| SEC9 | Большой размер тела запроса (DoS) | Должен отклонить (>10MB) |

---

## 7. Тестирование производительности

### 7.1 Время отклика

| # | Тест | Эндпоинт | Целевое время |
|---|------|----------|---------------|
| P1 | Health check | `/health` | < 100ms |
| P2 | Получение настроек | `GET /api/v1/settings/telegram` | < 200ms |
| P3 | Получение списка чатов | `GET /api/v1/settings/chats` | < 500ms |
| P4 | Семантический поиск | `POST /api/v1/ask` | < 3000ms |
| P5 | Генерация summary (async) | `POST /api/v1/chats/{chat_id}/summary/generate` | < 500ms (возврат task_id) |
| P6 | Ingest сообщения | `POST /api/v1/messages/ingest` | < 1000ms |

### 7.2 Нагрузочное тестирование

| # | Тест | Описание |
|---|------|----------|
| P7 | 100 одновременных запросов к /health | Все должны завершиться успешно |
| P8 | 50 одновременных ingest-запросов | Все должны обработаться корректно |
| P9 | 10 одновременных генераций summary | Все задачи должны создаться |
| P10 | Длительная нагрузка (10 мин) | Не должно быть утечек памяти |

---

## 8. Интеграционное тестирование

### 8.1 Сценарии

| # | Сценарий | Шаги |
|---|----------|------|
| I1 | **Полный цикл настройки чата** | 1. Настроить Telegram → 2. Синхронизировать чаты → 3. Включить мониторинг → 4. Включить summary |
| I2 | **Генерация и отправка summary** | 1. Настроить webhook → 2. Сгенерировать summary → 3. Проверить отправку на webhook |
| I3 | **Смена модели embedding** | 1. Обновить модель → 2. Проверить trigger reindex → 3. Запустить reindex → 4. Проверить статус |
| I4 | **Внешнее сообщение → поиск** | 1. Ingest сообщение → 2. Дождаться индексации → 3. Найти через /ask |
| I5 | **Пакетный импорт → summary** | 1. Импортировать сообщения → 2. Дождаться завершения → 3. Сгенерировать summary |
| I6 | **QR-аутентификация → мониторинг** | 1. Создать QR-сессию → 2. Авторизоваться → 3. Синхронизировать чаты → 4. Включить мониторинг |

### 8.2 Фоновые задачи

| # | Задача | Проверка |
|---|--------|----------|
| BG1 | ReindexService | Запуск, пауза, возобновление, отмена, завершение |
| BG2 | TelegramIngester | Подключение, получение сообщений, обработка ошибок |
| BG3 | SummaryTaskService | Планирование, генерация, кэширование |
| BG4 | SummaryCleanup | Автоматическая очистка старых summary |
| BG5 | PendingCleanup | Очистка просроченных pending-сообщений |

---

## 9. Чек-лист выполнения

### 9.1 Модули

| Модуль | Тестов | PASS | FAIL | SKIP | Статус |
|--------|--------|------|------|------|--------|
| Health & System | 9 | | | | ⬜ |
| Настройки Telegram | 7 | | | | ⬜ |
| QR-аутентификация | 6 | | | | ⬜ |
| Настройки LLM | 8 | | | | ⬜ |
| Настройки Embedding | 9 | | | | ⬜ |
| Настройки приложения | 7 | | | | ⬜ |
| Обзор настроек | 1 | | | | ⬜ |
| Управление чатами CRUD | 8 | | | | ⬜ |
| Управление чатами Операции | 8 | | | | ⬜ |
| Управление чатами Пользователи | 7 | | | | ⬜ |
| Настройки Summary | 14 | | | | ⬜ |
| Генерация Summary | 10 | | | | ⬜ |
| Получение Summary | 12 | | | | ⬜ |
| Webhook Summary | 3 | | | | ⬜ |
| Конфигурация Webhook | 7 | | | | ⬜ |
| Переиндексация | 13 | | | | ⬜ |
| Скорость переиндексации | 5 | | | | ⬜ |
| RAG & Search | 8 | | | | ⬜ |
| Внешние сообщения | 8 | | | | ⬜ |
| Пакетный импорт | 9 | | | | ⬜ |
| **ИТОГО** | **159** | | | | ⬜ |

### 9.2 Дополнительные тесты

| Категория | Тестов | PASS | FAIL | SKIP | Статус |
|-----------|--------|------|------|------|--------|
| Валидация | 7 | | | | ⬜ |
| Обработка ошибок | 6 | | | | ⬜ |
| Граничные значения | 5 | | | | ⬜ |
| Безопасность | 9 | | | | ⬜ |
| Производительность | 10 | | | | ⬜ |
| Интеграция | 6 | | | | ⬜ |
| Фоновые задачи | 5 | | | | ⬜ |
| **ИТОГО** | **48** | | | | ⬜ |

### 9.3 Общий итог

| Показатель | Значение |
|------------|----------|
| Всего тестов | **207** |
| Пройдено | |
| Провалено | |
| Пропущено | |
| Процент успеха | |
| Дата начала | |
| Дата завершения | |
| Тестировщик | |

---

## Приложение A: Глоссарий

| Термин | Определение |
|--------|-------------|
| Reindex | Переиндексация всех сообщений в векторном хранилище |
| Summary | Краткое содержание сообщений чата за период |
| Pending | Сообщения, ожидающие обработки (embedding) |
| Ingest | Приём сообщения из внешнего источника |
| RAG | Retrieval-Augmented Generation |
| QR Auth | Аутентификация через QR-код в Telegram |
| Webhook | HTTP-уведомление о событии |

## Приложение B: Коды ошибок

| Код | Описание | HTTP статус |
|-----|----------|-------------|
| EXT-001 | Invalid request data | 400 |
| EXT-002 | Chat not monitored | 400 |
| EXT-003 | Embedding error | 200 (pending) |
| EXT-004 | Database error | 200/500 |
| EXT-005 | Filtered message | 200 |
| EXT-006 | Duplicate message | 200 |
| EXT-007 | Embedding service unavailable | 200 (pending) |

## Приложение C: Примеры запросов

### Health Check
```bash
curl http://localhost:8000/health
```

### Ingest Message
```bash
curl -X POST http://localhost:8000/api/v1/messages/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "chat_id": "-1001234567890",
    "text": "Test message",
    "date": "2026-04-03T12:00:00Z",
    "sender_id": "123456",
    "sender_name": "Test User"
  }'
```

### Generate Summary
```bash
curl -X POST http://localhost:8000/api/v1/chats/-1001234567890/summary/generate \
  -H "Content-Type: application/json" \
  -d '{"period_minutes": 60, "use_cache": false}'
```

### Ask Question
```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What was discussed today?",
    "chat_id": "-1001234567890",
    "search_in": "both"
  }'
```
