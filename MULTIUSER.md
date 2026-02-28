# Авито Парсер - Multi-User Architecture

## Новые требования

### У каждого пользователя:
- ✅ Свои VK токены
- ✅ Свои Telegram токены
- ✅ Свой пул прокси
- ✅ Свои города и настройки
- ✅ Автозамена прокси при ошибке
- ✅ Автозамена VK токена при бане

---

## Архитектура БД (Multi-tenant)

### Таблицы

```sql
-- Пользователи (тенанты)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- VK токены (у каждого юзера свои)
CREATE TABLE vk_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    token_encrypted TEXT NOT NULL,
    scope VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    is_banned BOOLEAN DEFAULT FALSE,
    last_error TEXT,
    last_check TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- VK группы (привязаны к юзеру)
CREATE TABLE vk_groups (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    token_id INTEGER REFERENCES vk_tokens(id) ON DELETE CASCADE,
    group_id VARCHAR(50) NOT NULL, -- -123456789
    category VARCHAR(50) NOT NULL, -- auto, real_estate_sale, etc
    is_active BOOLEAN DEFAULT TRUE
);

-- Telegram боты
CREATE TABLE telegram_bots (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    bot_token_encrypted TEXT NOT NULL,
    bot_username VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    is_banned BOOLEAN DEFAULT FALSE,
    last_error TEXT,
    last_check TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Telegram каналы
CREATE TABLE telegram_channels (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    bot_id INTEGER REFERENCES telegram_bots(id) ON DELETE CASCADE,
    channel_id VARCHAR(255) NOT NULL, -- @channel или -1001234567890
    category VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

-- Прокси (у каждого юзера свой пул)
CREATE TABLE proxies (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    url TEXT NOT NULL, -- http://ip:port
    protocol VARCHAR(20), -- http, https, socks5
    is_alive BOOLEAN DEFAULT TRUE,
    last_check TIMESTAMP,
    error_count INTEGER DEFAULT 0,
    last_error TEXT,
    response_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Города (у каждого юзера свои)
CREATE TABLE cities (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL, -- Воркута
    url_slug VARCHAR(255) NOT NULL, -- vorkuta
    is_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, url_slug)
);

-- Источники (ссылки) для городов
CREATE TABLE city_sources (
    id SERIAL PRIMARY KEY,
    city_id INTEGER REFERENCES cities(id) ON DELETE CASCADE,
    category VARCHAR(50) NOT NULL,
    url_path VARCHAR(255) NOT NULL, -- avtomobili
    signature TEXT, -- 🚗 Авто Воркута
    is_enabled BOOLEAN DEFAULT TRUE
);

-- Объявления (привязаны к юзеру)
CREATE TABLE ads (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    city_id INTEGER REFERENCES cities(id),
    avito_id VARCHAR(255) NOT NULL,
    title TEXT,
    price INTEGER,
    description TEXT,
    url TEXT,
    category VARCHAR(50),
    author_type VARCHAR(20), -- private, business
    published_at TIMESTAMP,
    is_published BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, avito_id)
);

-- Стоп-слова (у каждого юзера свои)
CREATE TABLE stop_words (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    word VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, word)
);

-- Логи (для каждого юзера)
CREATE TABLE logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    level VARCHAR(20), -- INFO, WARNING, ERROR
    service VARCHAR(50), -- parser, publisher_vk, publisher_tg
    message TEXT,
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Автозамена токенов и прокси

### Прокси автозамена

**Триггеры замены:**
- ❌ Connection timeout
- ❌ HTTP 407 (Proxy Authentication Required)
- ❌ HTTP 502 (Bad Gateway)
- ❌ Сеть недоступна
- ❌ 3+ ошибки подряд

**Алгоритм:**
1. Попытка запроса через прокси
2. Ошибка → `error_count++`, `is_alive = False`
3. Выбор следующего живого прокси из пула юзера
4. Повтор запроса
5. Фоновая проверка "мёртвых" прокси каждые 5 минут

**Проверка прокси:**
```python
async def check_proxy(proxy_url):
    try:
        async with httpx.AsyncClient(proxies=proxy_url, timeout=10) as client:
            response = await client.get('https://httpbin.org/ip')
            if response.status_code == 200:
                return True, response.elapsed.total_seconds() * 1000
    except:
        return False, None
```

---

### VK токен автозамена

**Триггеры замены:**
- ❌ HTTP 401 (User authorization failed)
- ❌ Error code 5 (User authorization failed)
- ❌ Error code 6 (Too many requests per second)
- ❌ Error code 9 (Flood control)
- ❌ Error code 18 (User was deleted or banned)

**Алгоритм:**
1. Попытка запроса к VK API
2. Ошибка авторизации → `is_banned = True` в БД
3. Выбор следующего активного токена юзера
4. Повтор запроса
5. Если все токены забанены → уведомление юзеру

**Задержки при флуд-контроле:**
- Error 6 → задержка 1 сек, повтор
- Error 9 → задержка 5 сек, повтор
- Если повторяется → смена токена

---

### Telegram токен автозамена

**Триггеры замены:**
- ❌ HTTP 401 (Unauthorized)
- ❌ HTTP 403 (Forbidden)
- ❌ "Bot was blocked by the user"
- ❌ "Chat not found"

**Алгоритм:**
Похож на VK, но обычно с TG проблем меньше.

---

## Парсер с мультиюзер поддержкой

### Новая структура конфига

**Не нужен config.yaml!** Всё в БД.

### API для юзера

```python
# Получить свои настройки
GET /api/user/config
→ {
    cities: [...],
    vk_tokens: [{id, scope, is_active, is_banned}],
    telegram_bots: [...],
    proxies: [{url, is_alive, response_time_ms}],
    stop_words: [...]
}

# Добавить город
POST /api/cities
{name: "Воркута", url_slug: "vorkuta"}

# Добавить VK токен
POST /api/vk-tokens
{token: "vk1.a...", scope: "wall,photos,groups"}

# Добавить прокси
POST /api/proxies
{url: "http://ip:port"}

# Проверить прокси
POST /api/proxies/check
{proxy_id: 123}
→ {is_alive: true, response_time_ms: 234}

# Проверить VK токен
POST /api/vk-tokens/check
{token_id: 456}
→ {is_valid: true, scope: [...], user_info: {...}}
```

---

## Парсер - алгоритм работы

### 1. Запуск парсера для юзера

```python
async def run_parser_for_user(user_id: int):
    # Получить настройки юзера
    cities = await db.get_user_cities(user_id, enabled=True)
    proxies = await db.get_user_proxies(user_id, is_alive=True)
    tokens_vk = await db.get_user_vk_tokens(user_id, is_active=True, is_banned=False)
    tokens_tg = await db.get_user_telegram_bots(user_id, is_active=True, is_banned=False)
    stop_words = await db.get_user_stop_words(user_id)
    
    # Парсинг каждого города
    for city in cities:
        sources = await db.get_city_sources(city.id, enabled=True)
        
        for source in sources:
            # Парсинг категории
            ads = await parse_avito(
                city=city.url_slug,
                category=source.url_path,
                proxies=proxies,
                stop_words=stop_words
            )
            
            # Публикация
            for ad in ads:
                await publish_ad(
                    ad=ad,
                    category=source.category,
                    vk_tokens=tokens_vk,
                    tg_bots=tokens_tg,
                    user_id=user_id
                )
```

### 2. Парсинг с ротацией прокси

```python
async def parse_avito(city, category, proxies, stop_words):
    proxy_pool = ProxyPool(proxies)
    
    for page in range(1, 10):
        for attempt in range(3):
            proxy = proxy_pool.get_next()
            
            try:
                html = await fetch_page(url, proxy=proxy)
                ads = extract_ads(html)
                
                # Фильтрация
                ads = filter_ads(ads, stop_words)
                
                return ads
                
            except ProxyError as e:
                # Прокси мёртв → помечаем в БД
                await db.mark_proxy_dead(proxy.id, error=str(e))
                proxy_pool.remove(proxy)
                continue
                
            except Exception as e:
                await log_error(user_id, "parser", str(e))
                break
```

### 3. Публикация с ротацией токенов

```python
async def publish_to_vk(ad, category, vk_tokens, user_id):
    token_pool = TokenPool(vk_tokens)
    
    for attempt in range(len(vk_tokens)):
        token = token_pool.get_next()
        
        try:
            group_id = await db.get_vk_group(user_id, token.id, category)
            await vk_api.wall_post(token.value, group_id, ad.text)
            return True
            
        except VKAuthError as e:
            # Токен забанен
            await db.mark_token_banned(token.id, error=str(e))
            token_pool.remove(token)
            continue
            
        except VKFloodError as e:
            # Флуд-контроль → ждём
            await asyncio.sleep(5)
            continue
            
        except Exception as e:
            await log_error(user_id, "publisher_vk", str(e))
            break
    
    # Все токены забанены
    await notify_user(user_id, "Все VK токены забанены!")
    return False
```

---

## Фоновые задачи

### 1. Проверка прокси (каждые 5 минут)

```python
@scheduler.task('interval', minutes=5)
async def check_all_proxies():
    for user in await db.get_all_users(is_active=True):
        proxies = await db.get_user_proxies(user.id, is_alive=False)
        
        for proxy in proxies:
            is_alive, response_time = await check_proxy(proxy.url)
            await db.update_proxy(proxy.id, {
                'is_alive': is_alive,
                'response_time_ms': response_time,
                'last_check': datetime.now()
            })
```

### 2. Проверка VK токенов (каждые 15 минут)

```python
@scheduler.task('interval', minutes=15)
async def check_all_vk_tokens():
    for user in await db.get_all_users(is_active=True):
        tokens = await db.get_user_vk_tokens(user.id, is_banned=True)
        
        for token in tokens:
            is_valid = await check_vk_token(token.value)
            if is_valid:
                # Токен разбанили!
                await db.update_token(token.id, {
                    'is_banned': False,
                    'is_active': True,
                    'last_check': datetime.now()
                })
```

### 3. Парсинг (по расписанию для каждого юзера)

```python
@scheduler.task('interval', minutes=30)
async def run_all_parsers():
    for user in await db.get_all_users(is_active=True):
        await run_parser_for_user(user.id)
```

---

## Dashboard - изменения для мультиюзер

### Авторизация
- Логин/регистрация
- JWT токены
- Сессии

### Главная страница
- Показывает только данные текущего юзера
- Статистика только по его объявлениям

### Настройки
- **VK Токены:** список своих токенов (с индикатором бан/активен)
- **Telegram Боты:** список своих ботов
- **Прокси:** список своих прокси (с индикатором живой/мёртвый)
- Кнопки "Проверить" для каждого

---

## Миграция

### Из single-user в multi-user

1. Создать первого юзера (admin)
2. Перенести все данные из `config.yaml` в БД для этого юзера
3. Удалить `config.yaml`
4. Перезапустить парсер

---

**Следующий шаг:** Реализовать multi-user? Или сначала решить доступ к Dashboard с iPhone? 🚀
