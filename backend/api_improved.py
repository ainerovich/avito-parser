"""
Улучшенный Flask API для Dashboard с поддержкой нескольких городов
"""
from flask import Flask, jsonify, request
from flask_cors import CORS
import yaml
import os
from pathlib import Path
from database import db
from models import Announcement
from sqlalchemy import func

app = Flask(__name__, static_folder='../frontend/dist')
CORS(app)

CONFIG_PATH = "config.yaml"


def load_config():
    """Загрузка конфига"""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return get_default_config()


def save_config(config):
    """Сохранение конфига"""
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)


def get_default_config():
    """Дефолтный конфиг"""
    return {
        'vk': {'access_token': '', 'groups': {}},
        'telegram': {'bot_token': '', 'channels': {}},
        'proxies': [],
        'stop_words': ['автосалон', 'кредит', 'рассрочка', 'франшиза'],
        'cities': [],
        'parser': {'interval': 300, 'max_pages': 3, 'timeout': 30}
    }


@app.route('/api/config', methods=['GET'])
def get_config():
    """Получить полный конфиг"""
    config = load_config()
    
    # Маскируем токены
    if config.get('vk', {}).get('access_token'):
        config['vk']['access_token'] = config['vk']['access_token'][:10] + '...'
    if config.get('telegram', {}).get('bot_token'):
        config['telegram']['bot_token'] = config['telegram']['bot_token'][:10] + '...'
    
    return jsonify(config)


# ===== ГОРОДА =====

@app.route('/api/cities', methods=['GET'])
def get_cities():
    """Получить все города"""
    config = load_config()
    return jsonify(config.get('cities', []))


@app.route('/api/cities', methods=['POST'])
def add_city():
    """Добавить новый город"""
    data = request.json
    city_name = data.get('name', '').strip()
    city_slug = data.get('url_slug', '').strip().lower()
    
    if not city_name or not city_slug:
        return jsonify({'error': 'Укажи название и слаг'}), 400
    
    config = load_config()
    
    # Проверяем что не существует
    if any(c['url_slug'] == city_slug for c in config.get('cities', [])):
        return jsonify({'error': f'Город {city_slug} уже существует'}), 400
    
    # Создаём новый город с дефолтными ссылками
    new_city = {
        'name': city_name,
        'url_slug': city_slug,
        'enabled': True,
        'sources': [
            {'category': 'auto', 'url_path': 'avtomobili', 'enabled': True, 'signature': f'🚗 Авто {city_name}'},
            {'category': 'real_estate_sale', 'url_path': 'kvartiry', 'enabled': True, 'signature': f'🏠 Недвижимость {city_name}'},
            {'category': 'real_estate_rent', 'url_path': 'kvartiry/sdam', 'enabled': False, 'signature': f'🏠 Аренда {city_name}'},
            {'category': 'sport', 'url_path': 'tovary_dlya_sporta_i_otdyha', 'enabled': False, 'signature': f'⚽ Спорт {city_name}'},
            {'category': 'home', 'url_path': 'tovary_dlya_doma_i_dachi', 'enabled': False, 'signature': f'🏡 Товары {city_name}'},
        ]
    }
    
    config['cities'] = config.get('cities', []) + [new_city]
    save_config(config)
    
    return jsonify({'message': f'Город {city_name} добавлен с {len(new_city["sources"])} ссылками', 'city': new_city})


@app.route('/api/cities/<slug>/toggle', methods=['POST'])
def toggle_city(slug):
    """Включить/отключить город"""
    config = load_config()
    
    for city in config.get('cities', []):
        if city['url_slug'] == slug:
            city['enabled'] = not city['enabled']
            save_config(config)
            return jsonify({'message': f"Город {city['name']}: {'включен' if city['enabled'] else 'отключен'}"})
    
    return jsonify({'error': 'Город не найден'}), 404


@app.route('/api/cities/<slug>/sources', methods=['POST'])
def update_city_sources(slug):
    """Обновить ссылки города"""
    data = request.json
    sources = data.get('sources', [])
    
    config = load_config()
    
    for city in config.get('cities', []):
        if city['url_slug'] == slug:
            city['sources'] = sources
            save_config(config)
            return jsonify({'message': f'Ссылки {city["name"]} обновлены'})
    
    return jsonify({'error': 'Город не найден'}), 404


@app.route('/api/cities/<slug>', methods=['DELETE'])
def delete_city(slug):
    """Удалить город"""
    config = load_config()
    
    cities = config.get('cities', [])
    city_to_delete = None
    
    for i, city in enumerate(cities):
        if city['url_slug'] == slug:
            city_to_delete = cities.pop(i)
            break
    
    if city_to_delete:
        config['cities'] = cities
        save_config(config)
        return jsonify({'message': f'Город {city_to_delete["name"]} удалён'})
    
    return jsonify({'error': 'Город не найден'}), 404


# ===== ТОКЕНЫ И ПРОКСИ =====

@app.route('/api/tokens/vk', methods=['POST'])
def update_vk_token():
    """Обновить VK токен и группы"""
    data = request.json
    config = load_config()
    
    config['vk'] = {
        'access_token': data.get('access_token', ''),
        'groups': data.get('groups', {})
    }
    save_config(config)
    
    return jsonify({'message': 'VK токен обновлён'})


@app.route('/api/tokens/telegram', methods=['POST'])
def update_tg_token():
    """Обновить Telegram токен и каналы"""
    data = request.json
    config = load_config()
    
    config['telegram'] = {
        'bot_token': data.get('bot_token', ''),
        'channels': data.get('channels', {})
    }
    save_config(config)
    
    return jsonify({'message': 'Telegram токен обновлён'})


@app.route('/api/proxies', methods=['POST'])
def update_proxies():
    """Обновить прокси"""
    data = request.json
    proxies = data.get('proxies', [])
    proxies = [p.strip() for p in proxies if p.strip()]
    
    config = load_config()
    config['proxies'] = proxies
    save_config(config)
    
    return jsonify({'message': f'Прокси обновлены ({len(proxies)} шт.)'})


@app.route('/api/stop-words', methods=['POST'])
def update_stop_words():
    """Обновить стоп-слова"""
    data = request.json
    stop_words = data.get('stop_words', [])
    stop_words = [w.strip() for w in stop_words if w.strip()]
    
    config = load_config()
    config['stop_words'] = stop_words
    save_config(config)
    
    return jsonify({'message': f'Стоп-слова обновлены ({len(stop_words)} шт.)'})


# ===== СТАТИСТИКА =====

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Статистика"""
    session = db.get_session()
    
    try:
        total = session.query(func.count(Announcement.id)).scalar()
        new = session.query(func.count(Announcement.id)).filter(Announcement.status == 'new').scalar()
        published = session.query(func.count(Announcement.id)).filter(Announcement.published_to_vk == True).scalar()
        
        # По категориям
        by_category = {}
        categories = session.query(Announcement.category, func.count(Announcement.id)).group_by(Announcement.category).all()
        for cat, count in categories:
            by_category[cat] = count
        
        return jsonify({
            'total': total,
            'new': new,
            'published': published,
            'by_category': by_category
        })
    finally:
        session.close()


@app.route('/api/announcements', methods=['GET'])
def get_announcements():
    """Список объявлений"""
    session = db.get_session()
    
    try:
        limit = request.args.get('limit', 50, type=int)
        status = request.args.get('status', None)
        category = request.args.get('category', None)
        
        query = session.query(Announcement).order_by(Announcement.created_at.desc())
        
        if status:
            query = query.filter(Announcement.status == status)
        if category:
            query = query.filter(Announcement.category == category)
        
        announcements = query.limit(limit).all()
        
        return jsonify([ann.to_dict() for ann in announcements])
    finally:
        session.close()


# ===== ПАРСИНГ =====

@app.route('/api/fill-groups', methods=['POST'])
def fill_groups():
    """Наполнить группы"""
    import threading
    from parser_improved import ImprovedAvitoParser
    from publisher import VKPublisher
    from telegram_publisher import TelegramPublisher
    
    data = request.json
    days = data.get('days', 1)
    
    config = load_config()
    
    def fill_job():
        try:
            parser = ImprovedAvitoParser(config)
            
            total_found = 0
            
            # Парсим все активные города
            for city in config.get('cities', []):
                if not city.get('enabled', True):
                    continue
                
                logger.info(f"🌍 Обработка: {city['name']}")
                
                # Парсим город
                max_pages = days * 3
                announcements = parser.parse_city(city, max_pages)
                
                if not announcements:
                    continue
                
                # Фильтруем
                stop_words = config.get('stop_words', [])
                filtered = parser.filter_announcements(announcements, stop_words)
                
                # Сохраняем
                stats = parser.save_to_db(filtered)
                total_found += stats['new']
            
            # Публикуем
            signatures = {}
            for city in config.get('cities', []):
                for source in city.get('sources', []):
                    signatures[source['category']] = source.get('signature', '')
            
            if config.get('vk', {}).get('access_token'):
                vk_pub = VKPublisher(
                    access_token=config['vk']['access_token'],
                    group_mappings=config['vk']['groups']
                )
                vk_pub.publish_announcements(signatures)
            
            if config.get('telegram', {}).get('bot_token'):
                tg_pub = TelegramPublisher(
                    bot_token=config['telegram']['bot_token'],
                    channel_mappings=config['telegram']['channels']
                )
                tg_pub.publish_announcements(signatures)
            
            logger.success(f"✅ Наполнение завершено! {total_found} новых")
            
        except Exception as e:
            logger.error(f"Ошибка: {e}", exc_info=True)
    
    thread = threading.Thread(target=fill_job, daemon=True)
    thread.start()
    
    return jsonify({'message': f'Запущено наполнение за {days} дней', 'status': 'running'})


if __name__ == '__main__':
    db.init_db()
    
    if not os.path.exists(CONFIG_PATH):
        save_config(get_default_config())
        print("✅ Создан config.yaml")
    
    print("🚀 API запущен: http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
