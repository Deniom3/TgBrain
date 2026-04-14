# Отчёт тестирования переиндексации при смене модели эмбеддингов

**Дата:** 2026-04-09
**Модели:** bge-m3:latest (1024 dim) → nomic-embed-text:latest (768 dim) → bge-m3:latest (1024 dim)
**Сообщений:** 4546

---

## 1. Тест-кейсы

### 1.1 Смена модели через API
- **Endpoint:** PUT /api/v1/settings/embedding/ollama/model
- **Статус:** PASSED
- **Результат:** Модель обновлена, embedding_dim автоопределён, last_reindex_model сброшен
- **Замечание:** `reindex_started: false` — Smart Trigger не запускает реиндекс автоматически (embeddings_client не инициализирован)

### 1.2 Проверка необходимости переиндексации
- **Endpoint:** GET /api/v1/settings/reindex/check
- **Статус:** PASSED
- **До смены:** needs_reindex: false, все сообщения используют bge-m3:latest
- **После смены:** needs_reindex: true, 4546 messages_to_reindex

### 1.3 Переиндексация (async mode)
- **Endpoint:** POST /api/v1/settings/reindex/start (async_mode=true)
- **Статус:** FAILED → PASSED (после исправлений)
- **Найдено 3 критических бага** (см. раздел 2)

### 1.4 Вектор переключается правильно
- **Статус:** PASSED
- **До:** bge-m3:latest, VECTOR(1024), 4546 сообщений
- **После:** bge-m3:latest, VECTOR(1024), 4546 сообщений (после обратной смены)
- **Тест с nomic-embed-text:** VECTOR(768), 2300 сообщений успели переиндексироваться до обнаружения бага с pagination

### 1.5 RAG Ask после переиндексации
- **Статус:** FAILED — RAG-008 Database error
- **Причина:** Представление `v_embedding_dimension` было удалено во время миграции и не восстановлено
- **Обход:** `CREATE VIEW v_embedding_dimension AS SELECT ...` — RAG заработал

---

## 2. Найденные и исправленные баги

### 2.1 CRITICAL — Parameterized DDL в asyncpg
**Файлы:** `src/reindex/task_executor.py` (строки 99-101, 108-111, 431-443)

```python
# БЫЛО (не работает):
await pool.execute(
    "ALTER TABLE messages ALTER COLUMN embedding TYPE VECTOR($1::INTEGER)",
    required_dim
)

# СТАЛО (работает):
await pool.execute(
    f"ALTER TABLE messages ALTER COLUMN embedding TYPE VECTOR({required_dim})"
)
```

**Причина:** asyncpg не поддерживает параметры в DDL-запросах. Вызывает `InterfaceError`.

### 2.2 CRITICAL — Offset-based pagination при реиндексации
**Файлы:** `src/reindex/batch_processor.py:231-263`, `src/reindex/task_executor.py:265-301`

```python
# БЫЛО (offset-based — ломается):
offset = 0
while True:
    success, failed = await process_batch(pool, target_model, offset, stats)
    if success == 0 and failed == 0:
        break
    offset += batch_size  # offset растёт, но выборка уменьшается!

# СТАЛО (cursor-based — работает):
last_id = 0
while True:
    success, failed, new_last_id = await process_batch_cursor(pool, target_model, last_id, stats)
    if success == 0 and failed == 0:
        break
    last_id = new_last_id  # cursor движется только вперёд
```

**Причина:** При реиндексации сообщения обновляются и выпадают из выборки (`WHERE embedding IS NULL`). Offset пропускает необработанные сообщения. Реиндексация застревала на ~50% (2300/4546).

### 2.3 CRITICAL — Формат вектора для asyncpg/pgvector
**Файл:** `src/reindex/batch_processor.py:121-126`

```python
# БЫЛО (list[float] — не работает):
await pool.execute(SQL_UPDATE, record["id"], embedding, target_model)

# СТАЛО (string — работает):
embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
await pool.execute(SQL_UPDATE, record["id"], embedding_str, target_model)
```

**Причина:** asyncpg с pgvector ожидает строковое представление вектора `'[0.1,0.2,...]'`, а не Python list. Вызывает `DataError: expected str, got list`.

### 2.4 MINOR — v_embedding_dimension view не восстанавливается
**Причина:** Миграция удаляет view (`DROP VIEW IF EXISTS v_embedding_dimension`), но при сбое view не восстанавливается.
**Влияние:** RAG search (RAG-008 Database error)
**Рекомендация:** Добавить восстановление view в finally-блок миграции

---

## 3. Результаты

| Тест | До исправлений | После исправлений |
|------|---------------|-------------------|
| Модель меняется | OK | OK |
| Dimension обновляется | OK | OK |
| last_reindex_model сбрасывается | OK | OK |
| Реиндексация запускается | reindex_started: false | reindex_started: false* |
| Все сообщения переиндексированы | 2300/4546 (застревает) | 4546/4546 ✅ |
| 0 failed | ❌ InterfaceError | ✅ 0 failed |
| Вектор правильный | ❌ DataError | ✅ VECTOR(1024/768) |
| RAG работает | ❌ RAG-008 | ❌ RAG-008 (view) |

*Smart Trigger не запускает авто-реиндекс потому что embeddings_client не инициализирован в момент вызова. Требуется ручной запуск или исправление инициализации.

---

## 4. Рекомендации

1. **Восстановление view в finally-блок миграции** — предотвратить RAG-008 при сбоях
2. **Smart Trigger** — исправить инициализацию embeddings_client для авто-запуска реиндекса
3. **Интеграционные тесты** — добавить тест полной реиндексации с проверкой 100% coverage
4. **Мониторинг** — добавить алерт если реиндексация застревает на одном прогрессе > 5 мин
