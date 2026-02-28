#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Облегчённый парсер Авито - берёт данные из листинга (не заходит в объявления)
"""

import requests
from bs4 import BeautifulSoup
import time
import random
import re
from typing import List, Dict, Optional

class AvitoLightweightParser:
    """Парсер листинга Авито без захода в объявления"""
    
    def __init__(self, proxies: List[str] = None, stop_words: List[str] = None):
        self.proxies = proxies or []
        self.stop_words = [w.lower() for w in (stop_words or [])]
        self.session = requests.Session()
        
    def _get_proxy(self) -> Optional[Dict]:
        """Получить случайный прокси"""
        if not self.proxies:
            return None
        proxy_url = random.choice(self.proxies)
        return {"http": proxy_url, "https": proxy_url}
    
    def _get_headers(self) -> Dict:
        """HTTP заголовки как у браузера"""
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0"
        }
    
    def parse_listing(self, city: str, category: str, max_pages: int = 3) -> List[Dict]:
        """
        Парсит листинг (НЕ заходит в объявления!)
        
        Args:
            city: Город (vorkuta, moskva)
            category: Категория (avtomobili, kvartiry)
            max_pages: Сколько страниц парсить
            
        Returns:
            List[Dict]: Список объявлений
        """
        ads = []
        
        for page in range(1, max_pages + 1):
            url = f"https://www.avito.ru/{city}/{category}?p={page}"
            
            try:
                # Случайная задержка
                if page > 1:
                    time.sleep(random.uniform(2, 5))
                
                # Запрос
                response = self.session.get(
                    url,
                    headers=self._get_headers(),
                    proxies=self._get_proxy(),
                    timeout=15
                )
                
                if response.status_code != 200:
                    print(f"⚠️ Страница {page}: HTTP {response.status_code}")
                    continue
                
                # Проверка на капчу
                if "captcha" in response.text.lower() or "проверка" in response.text.lower():
                    print(f"❌ Капча на странице {page}")
                    break
                
                # Парсинг
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Объявления (разные селекторы для разных версий Авито)
                items = soup.find_all("div", {"data-marker": "item"})
                
                if not items:
                    # Альтернативный селектор
                    items = soup.find_all("div", class_=lambda x: x and "iva-item" in str(x))
                
                print(f"Страница {page}: найдено {len(items)} объявлений")
                
                for item in items:
                    ad = self._extract_from_snippet(item, city)
                    
                    if ad and self._is_valid(ad):
                        ads.append(ad)
                
            except Exception as e:
                print(f"❌ Ошибка на странице {page}: {e}")
                continue
        
        return ads
    
    def _extract_from_snippet(self, item_div, city: str) -> Optional[Dict]:
        """Извлекает данные ИЗ СНИППЕТА (без захода в объявление)"""
        try:
            ad = {
                "city": city,
                "avito_id": None,
                "title": None,
                "price": None,
                "description": None,
                "url": None,
                "image_url": None
            }
            
            # ID объявления
            item_id = item_div.get("data-item-id") or item_div.get("id", "").split("-")[-1]
            ad["avito_id"] = item_id
            
            # Заголовок
            title_elem = item_div.find("a", {"data-marker": "item-title"}) or \
                         item_div.find("h3") or \
                         item_div.find("a", {"itemprop": "url"})
            
            if title_elem:
                ad["title"] = title_elem.get_text(strip=True)
                
                # URL
                href = title_elem.get("href")
                if href:
                    if href.startswith("/"):
                        ad["url"] = f"https://www.avito.ru{href}"
                    else:
                        ad["url"] = href
            
            # Цена
            price_elem = item_div.find(attrs={"data-marker": "item-price"}) or \
                         item_div.find(attrs={"itemprop": "price"}) or \
                         item_div.find("span", class_=lambda x: x and "price" in str(x).lower())
            
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                # Извлекаем число
                price_match = re.search(r'(\d[\d\s]*)', price_text)
                if price_match:
                    ad["price"] = int(price_match.group(1).replace(' ', ''))
            
            # Описание (краткое из сниппета)
            desc_elem = item_div.find(attrs={"data-marker": "item-description"}) or \
                        item_div.find("div", class_=lambda x: x and "description" in str(x).lower())
            
            if desc_elem:
                ad["description"] = desc_elem.get_text(strip=True)
            elif ad["title"]:
                # Если нет описания - используем заголовок
                ad["description"] = ad["title"]
            
            # Картинка
            img_elem = item_div.find("img", attrs={"data-marker": "item-photo"}) or \
                       item_div.find("img") or \
                       item_div.find("source")
            
            if img_elem:
                img_url = img_elem.get("src") or img_elem.get("data-src") or \
                          img_elem.get("srcset", "").split(",")[0].split()[0]
                
                if img_url and not img_url.startswith("data:"):
                    ad["image_url"] = img_url
            
            return ad if ad["avito_id"] and ad["title"] else None
            
        except Exception as e:
            print(f"⚠️ Ошибка извлечения: {e}")
            return None
    
    def _is_valid(self, ad: Dict) -> bool:
        """Проверка валидности (стоп-слова, цена)"""
        # Стоп-слова
        if self.stop_words:
            text = f"{ad.get('title', '')} {ad.get('description', '')}".lower()
            for word in self.stop_words:
                if word in text:
                    return False
        
        # Минимальная цена
        if ad.get("price") and ad["price"] < 1000:
            return False
        
        # Обязательные поля
        if not ad.get("title") or not ad.get("url"):
            return False
        
        return True


def test_parser():
    """Тест парсера"""
    parser = AvitoLightweightParser(
        proxies=[],  # Добавь прокси
        stop_words=["автосалон", "кредит", "рассрочка"]
    )
    
    print("=== ТЕСТ ПАРСЕРА ===")
    print()
    
    ads = parser.parse_listing("vorkuta", "avtomobili", max_pages=1)
    
    print()
    print(f"✅ Собрано объявлений: {len(ads)}")
    print()
    
    if ads:
        print("Пример объявления:")
        ad = ads[0]
        print(f"  ID: {ad['avito_id']}")
        print(f"  Заголовок: {ad['title'][:80]}")
        print(f"  Цена: {ad['price']} ₽")
        print(f"  URL: {ad['url']}")
        print(f"  Картинка: {ad['image_url'][:60] if ad['image_url'] else 'нет'}...")


if __name__ == "__main__":
    test_parser()
