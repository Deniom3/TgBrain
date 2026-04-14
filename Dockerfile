# Базовый образ
FROM python:3.12-slim

# Рабочая директория
WORKDIR /app

# Переменные окружения
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Установка системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копирование зависимостей
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY src/ ./src/
COPY tests/ ./tests/
COPY scripts/ ./scripts/
COPY promt/ ./promt/
COPY static/ ./static/
# Документация (фильтрация ненужных директорий происходит в коде docs_viewer.py)
COPY docs/ ./docs/
COPY main.py ./
COPY pytest.ini ./

# Создание директорий для сессий и результатов
RUN mkdir -p /app/sessions /app/results

# Порт приложения
EXPOSE 8000

# Команда запуска (FastAPI через uvicorn)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
