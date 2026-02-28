#!/bin/bash
# Запуск парсера

echo "🔍 Запуск Avito Parser"

cd backend

# Проверка зависимостей
if ! python3 -c "import yaml" 2>/dev/null; then
    echo "📦 Установка зависимостей..."
    pip3 install -r requirements.txt
fi

# Запуск парсера
python3 main.py
