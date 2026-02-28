#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Авито Парсер - API для работы с единицами (units)
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import yaml
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

DB_PATH = '../data/avito_parser.db'
CONFIG_PATH = 'config.yaml'

# Инициализация БД
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Таблица единиц
    c.execute('''
        CREATE TABLE IF NOT EXISTS units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            city_slug TEXT NOT NULL,
            vk_group_id TEXT,
            telegram_channel_id TEXT,
            is_enabled INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица ссылок единицы
    c.execute('''
        CREATE TABLE IF NOT EXISTS unit_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id INTEGER,
            category TEXT NOT NULL,
            url_path TEXT NOT NULL,
            signature TEXT,
            is_enabled INTEGER DEFAULT 1,
            FOREIGN KEY (unit_id) REFERENCES units(id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")

init_db()

# Категории по умолчанию
DEFAULT_SOURCES = [
    {'category': 'avtomobili', 'url_path': 'avtomobili', 'signature': '🚗 Авто'},
    {'category': 'zapchasti', 'url_path': 'zapchasti_i_aksessuary', 'signature': '🔧 Запчасти'},
    {'category': 'kvartiry', 'url_path': 'kvartiry', 'signature': '🏠 Квартиры'},
    {'category': 'doma', 'url_path': 'doma_dachi_kottedzhi', 'signature': '🏡 Дома'},
    {'category': 'komnaty', 'url_path': 'komnaty', 'signature': '🚪 Комнаты'},
    {'category': 'noutbuki', 'url_path': 'noutbuki', 'signature': '💻 Ноутбуки'},
    {'category': 'telefony', 'url_path': 'telefony', 'signature': '📱 Телефоны'},
]

# Frontend
@app.route('/')
def index():
    return send_from_directory('../frontend', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('../frontend', path)

# API: Получить все единицы
@app.route('/api/units', methods=['GET'])
def get_units():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute('SELECT * FROM units ORDER BY created_at DESC')
    units = [dict(row) for row in c.fetchall()]
    
    # Добавляем ссылки к каждой единице
    for unit in units:
        c.execute('SELECT * FROM unit_sources WHERE unit_id = ?', (unit['id'],))
        unit['sources'] = [dict(row) for row in c.fetchall()]
    
    conn.close()
    return jsonify(units)

# API: Создать единицу
@app.route('/api/units', methods=['POST'])
def create_unit():
    data = request.json
    name = data.get('name')
    city_slug = data.get('city_slug')
    vk_group_id = data.get('vk_group_id', '')
    telegram_channel_id = data.get('telegram_channel_id', '')
    
    if not name or not city_slug:
        return jsonify({'error': 'Заполни название и город'}), 400
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Создаём единицу
    c.execute('''
        INSERT INTO units (name, city_slug, vk_group_id, telegram_channel_id)
        VALUES (?, ?, ?, ?)
    ''', (name, city_slug, vk_group_id, telegram_channel_id))
    
    unit_id = c.lastrowid
    
    # Добавляем ссылки по умолчанию
    for src in DEFAULT_SOURCES:
        c.execute('''
            INSERT INTO unit_sources (unit_id, category, url_path, signature, is_enabled)
            VALUES (?, ?, ?, ?, 0)
        ''', (unit_id, src['category'], src['url_path'], src['signature']))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'id': unit_id, 'message': 'Единица создана'})

# API: Обновить ссылки единицы
@app.route('/api/units/<int:unit_id>/sources', methods=['POST'])
def update_sources(unit_id):
    data = request.json
    sources = data.get('sources', [])
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Обновляем is_enabled для каждой ссылки
    for src in sources:
        c.execute('''
            UPDATE unit_sources 
            SET is_enabled = ?
            WHERE id = ? AND unit_id = ?
        ''', (1 if src.get('is_enabled') else 0, src['id'], unit_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# API: Включить/выключить единицу
@app.route('/api/units/<int:unit_id>/toggle', methods=['POST'])
def toggle_unit(unit_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('SELECT is_enabled FROM units WHERE id = ?', (unit_id,))
    row = c.fetchone()
    
    if row:
        new_state = 0 if row[0] else 1
        c.execute('UPDATE units SET is_enabled = ? WHERE id = ?', (new_state, unit_id))
        conn.commit()
    
    conn.close()
    return jsonify({'success': True})

# API: Удалить единицу
@app.route('/api/units/<int:unit_id>', methods=['DELETE'])
def delete_unit(unit_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('DELETE FROM units WHERE id = ?', (unit_id,))
    c.execute('DELETE FROM unit_sources WHERE unit_id = ?', (unit_id,))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# API: Наполнить единицу
@app.route('/api/units/<int:unit_id>/fill', methods=['POST'])
def fill_unit(unit_id):
    data = request.json
    days = data.get('days', 1)
    
    # TODO: Запустить парсер для этой единицы
    return jsonify({'success': True, 'message': f'Запущено наполнение за {days} дней'})

# API: Статистика
@app.route('/api/stats', methods=['GET'])
def get_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('SELECT COUNT(*) FROM ads')
    total = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM ads WHERE is_published = 0')
    new = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM ads WHERE is_published = 1')
    published = c.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'total': total,
        'new': new,
        'published': published
    })

# API: Конфиг (для совместимости)
@app.route('/api/config', methods=['GET'])
def get_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return jsonify(config)
    return jsonify({})

if __name__ == '__main__':
    print("🚀 Dashboard запущен: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
