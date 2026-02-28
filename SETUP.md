# Настройка и запуск Avito Parser MVP

## 1. Подготовка конфигурации

Отредактируй `backend/config.yaml`:

```yaml
# VK токен - ОБЯЗАТЕЛЬНО!
vk:
  access_token: "YOUR_VK_TOKEN_HERE"  # Замени на свой токен
  groups:
    auto: -123456789        # ID твоей группы "Авторынок" (с минусом!)
    real_estate: -987654321 # ID группы "Недвижимость"
    general: -111222333     # ID общей группы
```

### Как получить VK токен:

1. Иди: https://vkhost.github.io/
2. Выбери "Standalone приложение"
3. Права: `wall, photos, groups, offline`
4. Скопируй токен

### Как узнать ID группы:

1. Открой свою группу в VK
2. URL будет: `vk.com/club123456789` или `vk.com/public123456789`
3. ID группы = `-123456789` (с минусом!)

---

## 2. Локальный запуск (для теста)

```bash
cd avito-parser/backend

# Установка зависимостей
pip3 install -r requirements-mvp.txt

# Запуск
python3 main.py
```

---

## 3. Запуск через Docker (рекомендуется)

```bash
cd avito-parser

# Сборка и запуск
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down
```

---

## 4. Деплой на VPS

### Вариант А: Через Docker на VPS

```bash
# На VPS
cd /var/www
git clone https://github.com/ainerovich/avito-parser.git
cd avito-parser

# Настрой config.yaml
nano backend/config.yaml

# Запусти
docker-compose up -d
```

### Вариант Б: Systemd service (без Docker)

Создай `/etc/systemd/system/avito-parser.service`:

```ini
[Unit]
Description=Avito Parser Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/var/www/avito-parser/backend
ExecStart=/usr/bin/python3 /var/www/avito-parser/backend/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Запуск:
```bash
systemctl enable avito-parser
systemctl start avito-parser
systemctl status avito-parser
```

---

## 5. Проверка работы

```bash
# Логи (Docker)
docker-compose logs -f avito-parser

# Логи (systemd)
journalctl -u avito-parser -f

# Логи (файл)
tail -f logs/parser.log

# База данных
sqlite3 data/avito_parser.db "SELECT COUNT(*) FROM announcements;"
```

---

## 6. Настройка

### Добавление города:

Пока MVP поддерживает только один город. Чтобы добавить другой город:

1. Измени `city` в `config.yaml`
2. Измени URLs в `sources`

### Добавление категории:

```yaml
sources:
  - url: "https://www.avito.ru/vorkuta/noutbuki"
    category: "laptops"
    enabled: true
    signature: "💻 Ноутбуки Воркута"
```

### Отключение ссылки:

```yaml
sources:
  - url: "..."
    enabled: false  # Отключить эту ссылку
```

### Стоп-слова:

```yaml
stop_words:
  - "автосалон"
  - "кредит"
  - "новое слово"
```

---

## 7. Что дальше (расширение до боевой версии)

После тестирования MVP добавим:

- ✅ **Telegram публикацию**
- ✅ **Несколько городов одновременно**
- ✅ **Веб-интерфейс (Dashboard)**
- ✅ **API** для управления
- ✅ **Прокси ротацию**
- ✅ **Playwright** вместо requests (обход защиты Авито)
- ✅ **PostgreSQL** вместо SQLite
- ✅ **Метрики и мониторинг**

---

## Troubleshooting

**Проблема:** VK API ошибка "Invalid access token"
- Проверь токен в config.yaml
- Убедись что права `wall, photos, groups, offline`

**Проблема:** Не парсятся объявления
- Авито часто меняет вёрстку
- Проверь логи: `tail -f logs/parser.log`
- Возможно нужен Playwright (JS-рендеринг)

**Проблема:** Не публикуется в VK
- Проверь ID группы (должен быть с минусом!)
- Проверь что ты админ группы
- Проверь права токена

**Проблема:** Парсер падает
- Смотри логи
- Система автоматически перезапустится через 60 сек
