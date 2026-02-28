# Настройка Nginx для доступа к Dashboard с iPhone

## Проблема
Dashboard работает только на `localhost:5000`, недоступен с iPhone через Safari.

## Решение
Настроить Nginx reverse proxy для доступа через порт 80.

---

## Шаги на VPS

### 1. Установить Nginx (если нет)

```bash
sudo apt update
sudo apt install nginx -y
```

### 2. Создать конфиг

```bash
sudo nano /etc/nginx/sites-available/avito-parser
```

Вставить:

```nginx
server {
    listen 80;
    server_name 151.247.209.203;

    location / {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api {
        proxy_pass http://localhost:5000/api;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3. Активировать конфиг

```bash
sudo ln -s /etc/nginx/sites-available/avito-parser /etc/nginx/sites-enabled/
```

### 4. Проверить конфиг

```bash
sudo nginx -t
```

Должно быть:
```
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

### 5. Перезагрузить Nginx

```bash
sudo systemctl reload nginx
```

### 6. Проверить статус

```bash
sudo systemctl status nginx
```

---

## Проверка

### С VPS (локально)
```bash
curl http://localhost
```

### С iPhone (Safari)
Открой:
```
http://151.247.209.203
```

---

## Если порт 80 занят (tk-kontinental)

### Вариант 1: Использовать другой порт (например 8080)

```nginx
server {
    listen 8080;
    server_name 151.247.209.203;
    # ... остальное
}
```

Доступ:
```
http://151.247.209.203:8080
```

### Вариант 2: Использовать поддомен

Если есть домен (например `parser.yourdomain.com`):

```nginx
server {
    listen 80;
    server_name parser.yourdomain.com;
    # ... остальное
}
```

Доступ:
```
http://parser.yourdomain.com
```

### Вариант 3: Использовать location path

Добавить в существующий конфиг tk-kontinental:

```nginx
# В /etc/nginx/sites-available/tk-kontinental

server {
    listen 80;
    server_name 151.247.209.203;

    # Главный сайт
    location / {
        root /var/www/tk-kontinental;
        index index.html;
    }

    # Авито парсер
    location /parser/ {
        proxy_pass http://localhost:5000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Доступ:
```
http://151.247.209.203/parser/
```

---

## SSL (опционально, для HTTPS)

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d parser.yourdomain.com
```

---

**Рекомендация:** Использовать Вариант 3 (location path), чтобы не конфликтовать с tk-kontinental на порту 80.
