"""
Avito Parser - парсинг объявлений
"""
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import time
import re
from loguru import logger
from models import Announcement
from database import db


class AvitoParser:
    def __init__(self, config: dict):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        })
        
    def parse_listing_page(self, url: str, max_pages: int = 3) -> List[Dict]:
        """Парсинг страницы списка объявлений"""
        announcements = []
        
        for page in range(1, max_pages + 1):
            page_url = f"{url}?p={page}" if page > 1 else url
            logger.info(f"Парсинг страницы {page}: {page_url}")
            
            try:
                response = self.session.get(page_url, timeout=30)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Ищем объявления (Avito меняет классы, это базовая версия)
                items = soup.find_all('div', {'data-marker': 'item'})
                
                if not items:
                    logger.warning(f"Не найдено объявлений на странице {page}")
                    break
                
                for item in items:
                    try:
                        announcement = self._parse_item(item)
                        if announcement:
                            announcements.append(announcement)
                    except Exception as e:
                        logger.error(f"Ошибка парсинга объявления: {e}")
                        continue
                
                # Задержка между страницами
                if page < max_pages:
                    time.sleep(2)
                    
            except Exception as e:
                logger.error(f"Ошибка загрузки страницы {page}: {e}")
                break
        
        logger.info(f"Найдено {len(announcements)} объявлений")
        return announcements
    
    def _parse_item(self, item) -> Optional[Dict]:
        """Парсинг одного объявления"""
        try:
            # ID объявления
            avito_id = item.get('data-item-id')
            if not avito_id:
                return None
            
            # Заголовок
            title_elem = item.find('a', {'itemprop': 'url'}) or item.find('a', {'data-marker': 'item-title'})
            title = title_elem.get_text(strip=True) if title_elem else None
            
            # URL
            url = title_elem.get('href') if title_elem else None
            if url and not url.startswith('http'):
                url = f"https://www.avito.ru{url}"
            
            # Цена
            price_elem = item.find('meta', {'itemprop': 'price'}) or item.find('span', {'data-marker': 'item-price'})
            price = None
            if price_elem:
                price_text = price_elem.get('content') or price_elem.get_text(strip=True)
                price = self._extract_price(price_text)
            
            # Описание
            desc_elem = item.find('div', {'class': re.compile('.*description.*', re.I)})
            description = desc_elem.get_text(strip=True) if desc_elem else ""
            
            # Картинка
            img_elem = item.find('img', {'itemprop': 'image'}) or item.find('img')
            image_url = img_elem.get('src') if img_elem else None
            
            # Локация
            location_elem = item.find('div', {'class': re.compile('.*geo.*', re.I)}) or \
                          item.find('span', {'class': re.compile('.*location.*', re.I)})
            location = location_elem.get_text(strip=True) if location_elem else None
            
            # Определяем тип автора (частное лицо или бизнес)
            author_type = "private"
            if item.find('div', {'class': re.compile('.*shop.*|.*company.*', re.I)}):
                author_type = "business"
            
            return {
                'avito_id': avito_id,
                'title': title,
                'description': description,
                'price': price,
                'url': url,
                'image_urls': [image_url] if image_url else [],
                'location': location,
                'author_type': author_type,
            }
            
        except Exception as e:
            logger.error(f"Ошибка парсинга элемента: {e}")
            return None
    
    def _extract_price(self, price_text: str) -> Optional[float]:
        """Извлечение цены из текста"""
        if not price_text:
            return None
        
        # Убираем все кроме цифр
        price_clean = re.sub(r'[^\d]', '', price_text)
        
        try:
            return float(price_clean) if price_clean else None
        except:
            return None
    
    def filter_announcements(self, announcements: List[Dict], stop_words: List[str]) -> List[Dict]:
        """Фильтрация объявлений"""
        filtered = []
        
        for ann in announcements:
            # Пропускаем бизнес объявления
            if ann.get('author_type') == 'business':
                logger.debug(f"Пропущено (бизнес): {ann['title']}")
                continue
            
            # Проверяем стоп-слова
            text_to_check = f"{ann.get('title', '')} {ann.get('description', '')}".lower()
            if any(word.lower() in text_to_check for word in stop_words):
                logger.debug(f"Пропущено (стоп-слово): {ann['title']}")
                continue
            
            filtered.append(ann)
        
        logger.info(f"После фильтрации осталось {len(filtered)} объявлений")
        return filtered
    
    def save_to_db(self, announcements: List[Dict], category: str) -> Dict[str, int]:
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
                        logger.info(f"Обновлена цена: {existing.title} ({existing.price} → {new_price})")
                    else:
                        stats['duplicate'] += 1
                else:
                    # Новое объявление
                    announcement = Announcement(
                        avito_id=avito_id,
                        title=ann_data.get('title'),
                        description=ann_data.get('description'),
                        price=ann_data.get('price'),
                        category=category,
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
                    logger.info(f"Новое объявление: {announcement.title}")
            
            session.commit()
            logger.info(f"Статистика: новых={stats['new']}, дублей={stats['duplicate']}, обновлено={stats['updated']}")
            
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка сохранения в БД: {e}")
        finally:
            session.close()
        
        return stats
