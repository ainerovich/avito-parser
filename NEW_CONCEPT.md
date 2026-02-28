# Авито Парсер - Новая концепция "Единиц"

## Проблема старой логики
- Один город = один набор настроек
- Нельзя парсить один город для разных тематик

## Новая логика

### Единица (Unit)
**Единица** = независимая настройка парсинга

**Структура единицы:**
```
Название: "Воркута Авто" (любое, юзер сам придумывает)
Город (slug): "vorkuta"
Включенные ссылки: [avtomobili, zapchasti]
VK группа: -123456789
Telegram канал: @vorkuta_avto
Статус: включена/выключена
```

### Примеры

**Единица 1:**
- Название: "Воркута Авто"
- Город: vorkuta
- Ссылки: ✅ avtomobili, ✅ zapchasti
- VK: -111111111
- TG: @vorkuta_auto

**Единица 2:**
- Название: "Воркута Недвижка"
- Город: vorkuta
- Ссылки: ✅ kvartiry, ✅ doma
- VK: -222222222
- TG: @vorkuta_realty

**Единица 3:**
- Название: "Воркута Техника"
- Город: vorkuta
- Ссылки: ✅ noutbuki, ✅ telefony
- VK: -333333333
- TG: @vorkuta_tech

**Единица 4:**
- Название: "Москва Авто"
- Город: moskva
- Ссылки: ✅ avtomobili
- VK: -444444444
- TG: @moscow_auto

---

## База данных

```sql
-- Единицы (каждая независима)
CREATE TABLE units (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL, -- "Воркута Авто"
    city_slug VARCHAR(255) NOT NULL, -- vorkuta
    is_enabled BOOLEAN DEFAULT TRUE,
    vk_group_id VARCHAR(50), -- -123456789
    telegram_channel_id VARCHAR(255), -- @channel
    created_at TIMESTAMP DEFAULT NOW()
);

-- Ссылки внутри единицы
CREATE TABLE unit_sources (
    id SERIAL PRIMARY KEY,
    unit_id INTEGER REFERENCES units(id) ON DELETE CASCADE,
    category VARCHAR(50) NOT NULL, -- auto, real_estate_sale
    url_path VARCHAR(255) NOT NULL, -- avtomobili
    is_enabled BOOLEAN DEFAULT TRUE,
    signature TEXT -- 🚗 Воркута Авто
);

-- VK/TG токены остаются общими для юзера
vk_tokens (...)
telegram_bots (...)
proxies (...)
```

---

## Dashboard - Новый дизайн

### Главная страница

```
┌─────────────────────────────────────────────┐
│  ➕ Создать единицу                         │
│  ┌─────────────────┬─────────────────────┐ │
│  │ Название        │ Воркута Авто        │ │
│  │ Город (слаг)    │ vorkuta             │ │
│  │ VK группа       │ -123456789          │ │
│  │ Telegram канал  │ @vorkuta_auto       │ │
│  └─────────────────┴─────────────────────┘ │
│  [Создать]                                  │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ 🟢 Воркута Авто                   [вкл/выкл]│
│ 📍 vorkuta                                   │
│ 📱 VK: -123456789  💬 TG: @vorkuta_auto     │
│                                              │
│ Ссылки:                                      │
│ ✅ avtomobili    ✅ zapchasti               │
│ ❌ kvartiry      ❌ doma                     │
│                                              │
│ [📅 День] [📆 3 дня] [📊 5 дней]           │
│ [⚙️ Настроить] [🗑️ Удалить]               │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ 🟢 Воркута Недвижка               [вкл/выкл]│
│ 📍 vorkuta                                   │
│ 📱 VK: -222222222  💬 TG: @vorkuta_realty   │
│                                              │
│ Ссылки:                                      │
│ ❌ avtomobili    ❌ zapchasti               │
│ ✅ kvartiry      ✅ doma                     │
│                                              │
│ [📅 День] [📆 3 дня] [📊 5 дней]           │
│ [⚙️ Настроить] [🗑️ Удалить]               │
└─────────────────────────────────────────────┘
```

### Страница Настройки

**НЕТ полей для групп!** Группы настраиваются в каждой единице отдельно.

Только:
- ✅ VK токены (общие)
- ✅ Telegram токены (общие)
- ✅ Прокси (общие)
- ✅ Стоп-слова (общие)

---

## API

```python
# Создать единицу
POST /api/units
{
    name: "Воркута Авто",
    city_slug: "vorkuta",
    vk_group_id: "-123456789",
    telegram_channel_id: "@vorkuta_auto"
}

# Получить все единицы
GET /api/units
→ [{id, name, city_slug, is_enabled, vk_group_id, telegram_channel_id, sources: [...]}]

# Обновить ссылки единицы
POST /api/units/{id}/sources
{sources: [{category, url_path, is_enabled, signature}]}

# Включить/выключить единицу
POST /api/units/{id}/toggle

# Удалить единицу
DELETE /api/units/{id}

# Наполнить единицу
POST /api/units/{id}/fill
{days: 3}
```

---

## Парсер - логика

```python
async def run_parser():
    # Получить все включенные единицы
    units = await db.get_units(is_enabled=True)
    
    for unit in units:
        # Получить включенные ссылки этой единицы
        sources = await db.get_unit_sources(unit.id, is_enabled=True)
        
        for source in sources:
            # Парсинг
            ads = await parse_avito(
                city=unit.city_slug,
                category=source.url_path,
                proxies=proxies,
                stop_words=stop_words
            )
            
            # Публикация в СВОЮ группу единицы
            for ad in ads:
                await publish_to_vk(ad, unit.vk_group_id)
                await publish_to_telegram(ad, unit.telegram_channel_id)
```

---

## Преимущества

✅ Один город несколько раз с разными настройками
✅ Каждая единица = своя группа VK/TG
✅ Гибкость в названиях ("Воркута Авто Premium", "Воркута Недвижка VIP")
✅ Легко включать/отключать тематики
✅ Понятная структура для юзера

---

**Следующий шаг:** Переделать Dashboard и API под новую концепцию! 🚀
