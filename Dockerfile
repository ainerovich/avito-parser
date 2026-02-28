FROM python:3.11-slim

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копируем зависимости
COPY backend/requirements-mvp.txt .

# Устанавливаем Python пакеты
RUN pip install --no-cache-dir -r requirements-mvp.txt

# Копируем код
COPY backend/ .

# Создаём директории
RUN mkdir -p data logs

# Запуск
CMD ["python", "main.py"]
