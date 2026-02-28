"""
Flask API для Dashboard
"""
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import yaml
import os
from pathlib import Path
from database import db
from models import Announcement, Log
from sqlalchemy import func
from parser import AvitoParser
from publisher import VKPublisher
from telegram_publisher import TelegramPublisher
import threading

app = Flask(__name__, static_folder='../frontend/dist')
CORS(app)

CONFIG_PATH = "config.yaml"


# Авито категории по городам (автоматическая генерация ссылок)
AVITO_CATEGORIES = {
    'auto': 'avtomobili',
    'real_estate_sale': 'kvartiry',
    'real_estate_rent': 'kvartiry/sdam',
    'sport': 'tovary_dlya_sporta_i_otdyha',
    'home': 'tovary_dlya_doma_i_dachi',
    'electronics': 'elektronika',
    'tech': 'oborudovanie_dlya_biznesa',
}

CATEGORY_NAMES = {
    'auto': '🚗 Автомобили',
    'real_estate_sale': '🏠 Недвижимость (продажа)',
    'real_estate_rent': '🏠 Недвижимость (аренда)',
    'sport': '⚽ Спорт и отдых',
    'home': '🏡 Товары для дома',
    'electronics': '💻 Электроника',
    'tech': '🔧 Оборудование',
}


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
        'city': '',
        'sources': [],
        'vk': {
            'access_token': '',
            'groups': {}
        },
        'telegram': {
            'bot_token': '',
            'channels': {}
        },
        'stop_words': [
            'автосалон', 'кредит', 'рассрочка', 'trade-in',
            'трейд-ин', 'франшиза', 'официальный дилер', 'автоцентр'
        ],
        'parser': {
            'interval': 300,
            'max_pages': 3,
            'timeout': 30,
            'headless': True
        },
        'proxies': [],
        'database': {'path': 'data/avito_parser.db'},
        'logging': {
            'level': 'INFO',
            'file': 'logs/parser.log',
            'max_size': '10 MB',
            'backup_count': 5
        }
    }


@app.route('/')
def index():
    """Главная страница"""
    return send_from_directory('../frontend', 'index.html')


@app.route('/api/config', methods=['GET'])
def get_config():
    """Получить конфигурацию"""
    config = load_config()
    
    # Маскируем токены
    masked = config.copy()
    if masked.get('vk', {}).get('access_token'):
        masked['vk']['access_token'] = masked['vk']['access_token'][:10] + '...'
    if masked.get('telegram', {}).get('bot_token'):
        masked['telegram']['bot_token'] = masked['telegram']['bot_token'][:10] + '...'
    
    return jsonify(masked)


@app.route('/api/config/city', methods=['POST'])
def update_city():
    """Обновить город и сгенерировать ссылки"""
    data = request.json
    city = data.get('city', '').strip().lower()
    
    if not city:
        return jsonify({'error': 'Город не указан'}), 400
    
    config = load_config()
    config['city'] = city
    
    # Генерируем ссылки для всех категорий
    sources = []
    for cat_id, cat_path in AVITO_CATEGORIES.items():
        url = f"https://www.avito.ru/{city}/{cat_path}"
        sources.append({
            'url': url,
            'category': cat_id,
            'enabled': True,  # По умолчанию все включены
            'signature': f"{CATEGORY_NAMES.get(cat_id, cat_id)} | {city.capitalize()}"
        })
    
    config['sources'] = sources
    save_config(config)
    
    return jsonify({
        'message': 'Город обновлён, ссылки сгенерированы',
        'city': city,
        'sources': sources
    })


@app.route('/api/config/sources', methods=['POST'])
def update_sources():
    """Обновить ссылки (включить/отключить)"""
    data = request.json
    sources = data.get('sources', [])
    
    config = load_config()
    config['sources'] = sources
    save_config(config)
    
    return jsonify({'message': 'Ссылки обновлены'})


@app.route('/api/config/vk', methods=['POST'])
def update_vk():
    """Обновить VK настройки"""
    data = request.json
    
    config = load_config()
    config['vk'] = {
        'access_token': data.get('access_token', ''),
        'groups': data.get('groups', {})
    }
    save_config(config)
    
    return jsonify({'message': 'VK настройки обновлены'})


@app.route('/api/config/telegram', methods=['POST'])
def update_telegram():
    """Обновить Telegram настройки"""
    data = request.json
    
    config = load_config()
    config['telegram'] = {
        'bot_token': data.get('bot_token', ''),
        'channels': data.get('channels', {})
    }
    save_config(config)
    
    return jsonify({'message': 'Telegram настройки обновлены'})


@app.route('/api/config/proxies', methods=['POST'])
def update_proxies():
    """Обновить прокси"""
    data = request.json
    proxies = data.get('proxies', [])
    
    # Фильтруем пустые строки
    proxies = [p.strip() for p in proxies if p.strip()]
    
    config = load_config()
    config['proxies'] = proxies
    save_config(config)
    
    return jsonify({'message': f'Прокси обновлены ({len(proxies)} шт.)'})


@app.route('/api/config/stop-words', methods=['POST'])
def update_stop_words():
    """Обновить стоп-слова"""
    data = request.json
    stop_words = data.get('stop_words', [])
    
    # Фильтруем пустые строки
    stop_words = [w.strip() for w in stop_words if w.strip()]
    
    config = load_config()
    config['stop_words'] = stop_words
    save_config(config)
    
    return jsonify({'message': f'Стоп-слова обновлены ({len(stop_words)} шт.)'})


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
        
        query = session.query(Announcement).order_by(Announcement.created_at.desc())
        
        if status:
            query = query.filter(Announcement.status == status)
        
        announcements = query.limit(limit).all()
        
        return jsonify([ann.to_dict() for ann in announcements])
    finally:
        session.close()


@app.route('/api/logs', methods=['GET'])
def get_logs():
    """Последние логи"""
    session = db.get_session()
    
    try:
        limit = request.args.get('limit', 100, type=int)
        logs = session.query(Log).order_by(Log.created_at.desc()).limit(limit).all()
        
        return jsonify([
            {
                'id': log.id,
                'level': log.level,
                'service': log.service,
                'message': log.message,
                'created_at': log.created_at.isoformat()
            }
            for log in logs
        ])
    finally:
        session.close()


if __name__ == '__main__':
    # Инициализируем БД
    db.init_db()
    
    # Создаём дефолтный конфиг если нет
    if not os.path.exists(CONFIG_PATH):
        save_config(get_default_config())
        print("✅ Создан config.yaml")
    
    print("🚀 Dashboard запущен: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)


@app.route('/api/fill-groups', methods=['POST'])
def fill_groups():
    """Наполнить группы за N дней"""
    data = request.json
    days = data.get('days', 1)  # 1, 3 или 5 дней
    
    if days not in [1, 3, 5]:
        return jsonify({'error': 'days должен быть 1, 3 или 5'}), 400
    
    config = load_config()
    
    if not config.get('city') or not config.get('sources'):
        return jsonify({'error': 'Сначала настрой город и ссылки'}), 400
    
    # Запускаем в фоне
    def fill_job():
        logger.info(f"🔄 Запуск наполнения групп за {days} дней")
        
        try:
            parser = AvitoParser(config)
            
            total_found = 0
            
            # Парсим каждую активную ссылку
            for source in config['sources']:
                if not source.get('enabled', True):
                    continue
                
                logger.info(f"🔍 Парсинг: {source['url']}")
                
                # Парсим больше страниц для наполнения
                max_pages = days * 3  # 1 день = 3 страницы, 3 дня = 9 страниц и т.д.
                raw_announcements = parser.parse_listing_page(source['url'], max_pages)
                
                if not raw_announcements:
                    continue
                
                # Фильтрация
                stop_words = config.get('stop_words', [])
                filtered = parser.filter_announcements(raw_announcements, stop_words)
                
                # Сохранение
                category = source.get('category', 'general')
                stats = parser.save_to_db(filtered, category)
                
                total_found += stats['new']
                logger.info(f"📊 Найдено новых: {stats['new']}")
            
            # Публикация
            signatures = {}
            for source in config['sources']:
                category = source.get('category', 'general')
                signature = source.get('signature', '')
                signatures[category] = signature
            
            # VK
            if config.get('vk', {}).get('access_token'):
                vk_pub = VKPublisher(
                    access_token=config['vk']['access_token'],
                    group_mappings=config['vk']['groups']
                )
                vk_stats = vk_pub.publish_announcements(signatures)
                logger.info(f"📊 VK публикация: {vk_stats}")
            
            # Telegram
            if config.get('telegram', {}).get('bot_token'):
                tg_pub = TelegramPublisher(
                    bot_token=config['telegram']['bot_token'],
                    channel_mappings=config['telegram']['channels']
                )
                tg_stats = tg_pub.publish_announcements(signatures)
                logger.info(f"📊 TG публикация: {tg_stats}")
            
            logger.success(f"✅ Наполнение завершено! Найдено {total_found} новых объявлений")
            
        except Exception as e:
            logger.error(f"❌ Ошибка наполнения: {e}", exc_info=True)
    
    thread = threading.Thread(target=fill_job, daemon=True)
    thread.start()
    
    return jsonify({
        'message': f'Запущено наполнение групп за {days} дней',
        'status': 'running'
    })


@app.route('/api/parser/status', methods=['GET'])
def parser_status():
    """Статус парсера (работает ли)"""
    # TODO: Добавить реальную проверку через PID файл или systemd
    return jsonify({
        'status': 'unknown',
        'message': 'Запусти парсер через: bash start-parser.sh'
    })
