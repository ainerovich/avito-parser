"""
Улучшенный Avito Parser - с поддержкой нескольких городов и лучшей фильтрацией
"""
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import time
import re
import random
from loguru import logger
from models import Announcement
from database import db


class ImprovedAvitoParser:
    """Улучшенный парсер с кешированием, ротацией, антибан механизмами"""
    
    def __init__(self, config: dict):
        self.config = config
        self.session = requests.Session()
        self.proxies = config.get('proxies', [])
        self.proxy_index = 0
        self._setup_session()
        
    def _setup_session(self):
        """Настройка сессии с User-Agent и таймаутами"""
        user_agent = self.config.get('parser', {}).get('user_agent') or \
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        
        self.session.headers.update({
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def _get_next_proxy(self) -> Optional[Dict]:
        """Ротация прокси"""
        if not self.proxies:
            return None
        
        proxy = self.proxies[self.proxy_index % len(self.proxies)]
        self.proxy_index += 1
        
        return {'http': proxy, 'https': proxy}
    
    def parse_city(self, city_data: dict, max_pages: int = 3) -> List[Dict]:
        """Парсинг всех активных ссылок для города"""
        city_name = city_data['name']
        url_slug = city_data['url_slug']
        announcements = []
        
        logger.info(f"🌍 Парсинг города: {city_name}")
        
        for source in city_data.get('sources', []):
            if not source.get('enabled', True):
                logger.debug(f"⏭️ Пропущена (отключена): {source['category']}")
                continue
            
            url = f"https://www.avito.ru/{url_slug}/{source['url_path']}"
            logger.info(f"🔍 {source['category']}: {url}")
            
            try:
                items = self.parse_listing_page(url, max_pages, source['category'], city_name)
                announcements.extend(items)
                
                # Задержка между категориями (антибан)
                delay = self.config.get('parser', {}).get('delay_between_requests', 2)
                time.sleep(delay)
                
            except Exception as e:
                logger.error(f"Ошибка при парсинге {source['category']}: {e}")
                continue
        
        logger.info(f"✅ Город {city_name}: найдено {len(announcements)} объявлений")
        return announcements
    
    def parse_listing_page(self, url: str, max_pages: int = 3, category: str = "general", city: str = "") -> List[Dict]:
        """Парсинг страницы списка объявлений с защитой от бана"""
        announcements = []
        
        for page in range(1, max_pages + 1):
            page_url = f"{url}?p={page}" if page > 1 else url
            
            try:
                # Ротация прокси и User-Agent
                proxies = self._get_next_proxy()
                
                logger.debug(f"Страница {page}/{max_pages}: {page_url}")
                
                response = self.session.get(
                    page_url,
                    timeout=self.config.get('parser', {}).get('timeout', 30),
                    proxies=proxies,
                    allow_redirects=True
                )
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Ищем объявления (разные селекторы для разных вариантов вёрстки Авито)
                items = soup.find_all('div', {'data-marker': 'item'})
                
                if not items:
                    logger.warning(f"Страница {page}: не найдено объявлений (возможно, Авито изменила вёрстку)")
                    break
                
                for item in items:
                    try:
                        announcement = self._parse_item(item, category, city)
                        if announcement:
                            announcements.append(announcement)
                    except Exception as e:
                        logger.debug(f"Ошибка парсинга элемента: {e}")
                        continue
                
                # Случайная задержка между страницами (антибан)
                delay = random.uniform(1, 3)
                time.sleep(delay)
                
            except requests.exceptions.ProxyError:
                logger.warning(f"Ошибка прокси на странице {page}, пробую без прокси")
                try:
                    response = self.session.get(page_url, timeout=30)
                    response.raise_for_status()
                    # Повторяем парсинг без прокси
                except Exception as e:
                    logger.error(f"Ошибка без прокси: {e}")
                    break
            except Exception as e:
                logger.error(f"Ошибка загрузки страницы {page}: {e}")
                break
        
        return announcements
    
    def _parse_item(self, item, category: str = "", city: str = "") -> Optional[Dict]:
        """Парсинг одного объявления с улучшениями"""
        try:
            # ID объявления
            avito_id = item.get('data-item-id')
            if not avito_id:
                return None
            
            # Заголовок
            title_elem = item.find('a', {'itemprop': 'url'}) or item.find('a', {'data-marker': 'item-title'})
            title = title_elem.get_text(strip=True) if title_elem else None
            
            if not title:
                return None
            
            # URL
            url = title_elem.get('href') if title_elem else None
            if url and not url.startswith('http'):
                url = f"https://www.avito.ru{url}"
            
            # Цена (лучшая обработка)
            price = self._extract_price(item)
            
            # Описание
            desc_elem = item.find('div', {'class': re.compile('.*description.*', re.I)})
            description = desc_elem.get_text(strip=True) if desc_elem else ""
            
            # Картинка
            img_elem = item.find('img', {'itemprop': 'image'}) or item.find('img')
            image_url = img_elem.get('src') if img_elem else None
            
            # Локация
            location_elem = item.find('div', {'class': re.compile('.*geo.*', re.I)})
            location = location_elem.get_text(strip=True) if location_elem else city
            
            # Определяем тип автора (private или business)
            author_type = self._detect_author_type(item)
            
            return {
                'avito_id': avito_id,
                'title': title,
                'description': description,
                'price': price,
                'url': url,
                'image_urls': [image_url] if image_url else [],
                'location': location,
                'author_type': author_type,
                'category': category,
            }
            
        except Exception as e:
            logger.debug(f"Ошибка парсинга элемента: {e}")
            return None
    
    def _extract_price(self, item) -> Optional[float]:
        """Улучшенное извлечение цены"""
        try:
            # Пытаемся разные селекторы
            price_elem = item.find('meta', {'itemprop': 'price'})
            if price_elem:
                price_text = price_elem.get('content')
            else:
                price_elem = item.find('span', {'data-marker': 'item-price'})
                if price_elem:
                    price_text = price_elem.get_text()
                else:
                    # Ищем по классам
                    price_elem = item.find('span', {'class': re.compile('.*price.*', re.I)})
                    price_text = price_elem.get_text() if price_elem else None
            
            if not price_text:
                return None
            
            # Очищаем и конвертируем
            price_clean = re.sub(r'[^\d]', '', str(price_text))
            return float(price_clean) if price_clean else None
            
        except Exception as e:
            logger.debug(f"Ошибка извлечения цены: {e}")
            return None
    
    def _detect_author_type(self, item) -> str:
        """Определение типа автора (private или business)"""
        try:
            # Признаки бизнеса
            business_indicators = [
                'data-marker.*shop',
                'data-marker.*company',
                'class.*shop',
                'class.*company',
                'class.*seller',
                'class.*business',
            ]
            
            item_str = str(item)
            for indicator in business_indicators:
                if re.search(indicator, item_str, re.I):
                    return "business"
            
            return "private"
        except:
            return "private"
    
    def filter_announcements(self, announcements: List[Dict], stop_words: List[str]) -> List[Dict]:
        """Фильтрация объявлений с улучшениями"""
        filtered = []
        
        for ann in announcements:
            # 1. Пропускаем бизнес
            if ann.get('author_type') == 'business':
                logger.debug(f"Фильтр: бизнес - {ann['title']}")
                continue
            
            # 2. Проверяем стоп-слова (и заголовок и описание)
            text_to_check = f"{ann.get('title', '')} {ann.get('description', '')}".lower()
            found_stop_word = False
            for word in stop_words:
                if word.lower() in text_to_check:
                    logger.debug(f"Фильтр: стоп-слово '{word}' - {ann['title']}")
                    found_stop_word = True
                    break
            
            if found_stop_word:
                continue
            
            # 3. Проверяем минимальную цену (исключаем бесплатное)
            if ann.get('price') is None or ann.get('price') == 0:
                logger.debug(f"Фильтр: нет цены - {ann['title']}")
                continue
            
            # 4. Проверяем минимальную длину описания (защита от спама)
            if len(ann.get('description', '')) < 10:
                logger.debug(f"Фильтр: очень короткое описание - {ann['title']}")
                continue
            
            filtered.append(ann)
        
        logger.info(f"✅ После фильтрации: {len(filtered)}/{len(announcements)} объявлений")
        return filtered
    
    def save_to_db(self, announcements: List[Dict]) -> Dict[str, int]:
        """Сохранение в БД с дедупликацией"""
        stats = {'new': 0, 'duplicate': 0, 'updated': 0}
        session = db.get_session()
        
        try:
            for ann_data in announcements:
                avito_id = ann_data['avito_id']
                
                # Проверяем существует ли
                existing = session.query(Announcement).filter_by(avito_id=avito_id).first()
                
                if existing:
                    # Проверяем изменилась ли цена
                    new_price = ann_data.get('price')
                    if new_price and existing.price != new_price:
                        existing.price = new_price
                        existing.last_price = existing.price
                        existing.status = 'updated'
                        stats['updated'] += 1
                        logger.info(f"🔄 Обновлена цена: {existing.title}")
                    else:
                        stats['duplicate'] += 1
                else:
                    # Новое объявление
                    announcement = Announcement(
                        avito_id=avito_id,
                        title=ann_data.get('title'),
                        description=ann_data.get('description'),
                        price=ann_data.get('price'),
                        category=ann_data.get('category'),
                        url=ann_data.get('url'),
                        image_urls=ann_data.get('image_urls'),
                        author_type=ann_data.get('author_type'),
                        location=ann_data.get('location'),
                        content_hash=Announcement.generate_hash(
                            avito_id,
                            ann_data.get('title', ''),
                            ann_data.get('description', '')
                        ),
                        status='new'
                    )
                    session.add(announcement)
                    stats['new'] += 1
                    logger.info(f"✨ Новое: {announcement.title}")
            
            session.commit()
            
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка сохранения в БД: {e}")
        finally:
            session.close()
        
        return stats
