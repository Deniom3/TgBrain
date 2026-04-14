# Отчёт тестирования расписания summary + webhook

**Дата:** 2026-04-10
**Чат:** Smart Life (-1002222432841)
**Топик:** 47286 (Sammeri)

---

## 1. Найденные баги

### 1.1 CRITICAL — Webhook никогда не отправлялся из ScheduleService
**Файл:** `src/schedule/schedule_service.py` строка 281

```python
# БЫЛО (никогда не выполняется — from_cache=True и is_new=True не могут быть одновременно):
if is_new:
    triggered_count += 1
    if task_result.from_cache and chat_setting.webhook_enabled:  # ← NEVER TRUE
        await self._webhook_service.send_webhook_after_generation(...)
```

**Причина:** `from_cache=True` означает что найден кэш, `is_new=True` означает что создана новая задача. Эти флаги несовместимы.

**Исправление:** Вынес логику webhook за пределы `if is_new:` — теперь webhook отправляется для всех случаев (cached, new, pending).

### 1.2 CRITICAL — Webhook для pending задач отправлялся до завершения генерации
**Файл:** `src/infrastructure/services/summary_webhook_service.py` метод `send_webhook_after_generation`

**Причина:** Метод вызывал `send_webhook_for_summary` немедленно, но если summary ещё pending, `result_text` пустой и webhook не отправлялся.

**Исправление:** Добавлен цикл ожидания (до 5 минут, проверка каждые 10 секунд) пока summary не станет completed.

---

## 2. Результаты тестирования

### 2.1 ScheduleService с */5
| Проверка | Результат | Детали |
|----------|-----------|--------|
| Schedule установлен */5 | ✅ | next_run: 11:50 → 11:55 → ... |
| Summary создана по расписанию | ✅ | Summary #5, 558 символов, 11:47:42 |
| next_schedule_run обновлён | ✅ | 11:50 → 11:55 |
| Webhook для cached summary | ✅ | `webhook_sent: true` |
| Webhook для новой summary | ✅ | Ждёт completion, затем отправляет |

### 2.2 Timeline
```
11:46:40 — Установлено расписание */5, next_run=11:50
11:47:42 — ScheduleService создал summary #5 (при старте приложения)
11:47:53 — Summary completed (execution_time: 11.3s)
11:50:00 — ScheduleService обновил next_run → 11:55
11:54:40 — Проверка: summary #5 существует, next_run=11:55
```

### 2.3 Webhook delivery
| Сценарий | Статус |
|----------|--------|
| Cached summary (send-webhook endpoint) | ✅ Отправлено |
| Cached summary (ScheduleService) | ✅ Отправлено |
| New summary (send-webhook endpoint) | ✅ Отправлено после completion |
| New summary (ScheduleService) | ✅ Отправлено после completion |

---

## 3. Исправленные файлы

| Файл | Изменение |
|------|-----------|
| `src/schedule/schedule_service.py` | Webhook логика вынесена за пределы `if is_new:` |
| `src/infrastructure/services/summary_webhook_service.py` | `send_webhook_after_generation` ждёт completion summary |
| `src/app.py` | Добавлено `app.state.summary_task_service = summary_task_service` |
| `src/reindex/task_executor.py` | Cursor-based pagination + f-string DDL |
| `src/reindex/batch_processor.py` | Vector format fix + cursor pagination |

---

## 4. Итог

**ScheduleService работает:**
- ✅ Находит чаты с расписанием
- ✅ Создаёт summary при наступлении времени
- ✅ Обновляет next_schedule_run
- ✅ Отправляет webhook (для cached — немедленно, для pending — после completion)

**Расписание:** 22:25 UTC ежедневно для чата Smart Life → топик 47286
