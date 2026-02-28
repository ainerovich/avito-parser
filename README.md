# Авито-парсер SaaS

Современная система парсинга Авито с автопубликацией в VK и Telegram.

## Возможности

✅ **Парсинг Авито** - по городам и категориям
✅ **Фильтрация** - только частные объявления, стоп-слова
✅ **Мультиканальная публикация** - VK группы + Telegram каналы
✅ **Дедупликация** - без повторов, публикация только при изменении цены
✅ **Управление прокси** - автопроверка и ротация
✅ **Dashboard** - веб-интерфейс управления
✅ **Автовосстановление** - система сама поднимается при падении
✅ **Логирование** - полная история работы
✅ **SaaS готово** - мультипользователь, биллинг

## Технологии

- **Backend:** FastAPI (Python 3.11+)
- **Parser:** Playwright + BeautifulSoup4
- **Database:** PostgreSQL 15 + Redis 7
- **Frontend:** React 18 + Vite
- **Queue:** Celery
- **Deploy:** Docker + Docker Compose
- **CI/CD:** GitHub Actions

## Структура проекта

```
avito-parser/
├── backend/
│   ├── api/              # REST API endpoints
│   ├── parser/           # Авито парсер
│   ├── publisher/        # VK + Telegram публикатор
│   ├── models/           # Database models
│   ├── utils/            # Утилиты
│   └── main.py           # Entry point
├── frontend/
│   ├── src/
│   │   ├── components/   # React компоненты
│   │   ├── pages/        # Страницы
│   │   └── utils/        # Утилиты
│   └── package.json
├── database/
│   ├── init.sql          # Инициализация БД
│   └── migrations/       # Миграции
├── docker/
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   └── docker-compose.yml
├── config/
│   └── config.yaml       # Конфигурация
└── README.md
```

## Быстрый старт

```bash
# 1. Клонировать репо
git clone https://github.com/ainerovich/avito-parser.git
cd avito-parser

# 2. Запустить через Docker
docker-compose up -d

# 3. Открыть dashboard
http://localhost:3000
```

## Разработка

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## API Документация

После запуска: http://localhost:8000/docs

## Настройка

1. Добавь города в дашборде
2. Добавь ссылки для парсинга
3. Добавь токены VK и Telegram
4. Настрой прокси (опционально)
5. Запусти парсер!

## Лицензия

Proprietary - © 2024 Айнер
