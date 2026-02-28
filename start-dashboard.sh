#!/bin/bash
# Запуск Dashboard + Parser

echo "🚀 Запуск Avito Parser Dashboard"

cd backend

# Проверка зависимостей
if ! python3 -c "import flask" 2>/dev/null; then
    echo "📦 Установка зависимостей..."
    pip3 install -r requirements.txt
fi

# Запуск Dashboard API
echo "🌐 Dashboard: http://localhost:5000"
python3 api.py
