#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер Авито с поддержкой решения капч
Капчу решает оператор (потом автоматизируем через RuCaptcha)
"""

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import json
import time
import random
from typing import List, Dict, Optional

class AvitoParserWithCaptcha:
    """Парсер Авито через Playwright с решением капч"""
    
    def __init__(self, proxy: str = None, headless: bool = False):
        """
        Args:
            proxy: Прокси в формате http://user:pass@host:port
            headless: False для VNC доступа (чтобы я видел капчу)
        """
        self.proxy = proxy
        self.headless = headless
        self.cookies_file = "/tmp/avito_cookies.json"
        
    def solve_captcha_manually(self, page):
        """
        Ждёт пока оператор (я) решу капчу вручную
        Потом автоматизируем через RuCaptcha API
        """
        print("🔴 КАПЧА ОБНАРУЖЕНА!")
        print("Скриншот сохранён в /tmp/captcha.png")
        
        # Скриншот капчи
        page.screenshot(path="/tmp/captcha.png")
        
        # Сохраняем в webshare для просмотра
        page.screenshot(path="/var/www/tk-kontinental/captcha.png")
        
        print("Открой: http://151.247.209.203/captcha.png")
        print()
        print("Решаю капчу...")
        
        # TODO: Интеграция RuCaptcha API
        # captcha_img = page.query_selector("img[class*='captcha']")
        # Отправить на RuCaptcha → получить решение → ввести
        
        # Пока жду ручного решения (30 секунд)
        try:
            page.wait_for_url(lambda url: "captcha" not in url.lower(), timeout=30000)
            print("✅ Капча решена!")
            return True
        except:
            print("❌ Капча не решена за 30 секунд")
            return False
    
    def load_cookies(self, context):
        """Загрузить сохранённые cookies"""
        try:
            with open(self.cookies_file, 'r') as f:
                cookies = json.load(f)
                context.add_cookies(cookies)
                print("✅ Cookies загружены")
                return True
        except:
            print("ℹ️ Cookies не найдены, начинаем с чистого листа")
            return False
    
    def save_cookies(self, context):
        """Сохранить cookies для повторного использования"""
        cookies = context.cookies()
        with open(self.cookies_file, 'w') as f:
            json.dump(cookies, f)
        print("✅ Cookies сохранены")
    
    def parse_listing(self, city: str, category: str, max_pages: int = 3) -> List[Dict]:
        """
        Парсит листинг через реальный браузер
        
        Args:
            city: Город (vorkuta)
            category: Категория (avtomobili)
            max_pages: Сколько страниц
            
        Returns:
            Список объявлений
        """
        ads = []
        
        with sync_playwright() as p:
            # Настройки браузера
            browser_args = {
                "headless": self.headless,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage"
                ]
            }
            
            if self.proxy:
                browser_args["proxy"] = {"server": self.proxy}
            
            browser = p.chromium.launch(**browser_args)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            # Загружаем cookies если есть
            self.load_cookies(context)
            
            page = context.new_page()
            
            try:
                for page_num in range(1, max_pages + 1):
                    url = f"https://www.avito.ru/{city}/{category}?p={page_num}"
                    print(f"Страница {page_num}: {url}")
                    
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    
                    # Случайная задержка (имитация человека)
                    time.sleep(random.uniform(2, 4))
                    
                    # Проверка на капчу
                    if "captcha" in page.url.lower() or page.query_selector("form[class*='captcha']"):
                        if not self.solve_captcha_manually(page):
                            print("❌ Не удалось решить капчу, прерываем")
                            break
                        
                        # Сохраняем cookies после успешного решения
                        self.save_cookies(context)
                        
                        # Повторяем запрос
                        page.goto(url, wait_until="domcontentloaded")
                    
                    # Парсим объявления
                    page_ads = self._extract_ads_from_page(page)
                    print(f"  Найдено: {len(page_ads)} объявлений")
                    
                    ads.extend(page_ads)
                    
                    # Скролл вниз (имитация просмотра)
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(1)
                
                # Сохраняем cookies в конце
                self.save_cookies(context)
                
            finally:
                browser.close()
        
        return ads
    
    def _extract_ads_from_page(self, page) -> List[Dict]:
        """Извлечь объявления со страницы"""
        ads = []
        
        # Селекторы для объявлений
        items = page.query_selector_all("div[data-marker='item']")
        
        for item in items:
            try:
                ad = {}
                
                # ID
                ad['avito_id'] = item.get_attribute('data-item-id') or ''
                
                # Заголовок и URL
                title_elem = item.query_selector("a[data-marker='item-title']")
                if title_elem:
                    ad['title'] = title_elem.inner_text().strip()
                    href = title_elem.get_attribute('href')
                    ad['url'] = f"https://www.avito.ru{href}" if href.startswith('/') else href
                
                # Цена
                price_elem = item.query_selector("[data-marker='item-price']")
                if price_elem:
                    price_text = price_elem.inner_text().strip()
                    # Извлекаем число
                    price_clean = ''.join(filter(str.isdigit, price_text))
                    ad['price'] = int(price_clean) if price_clean else None
                
                # Описание
                desc_elem = item.query_selector("[data-marker='item-description']")
                if desc_elem:
                    ad['description'] = desc_elem.inner_text().strip()
                
                # Картинка
                img_elem = item.query_selector("img[data-marker='item-photo']")
                if img_elem:
                    ad['image_url'] = img_elem.get_attribute('src') or img_elem.get_attribute('data-src')
                
                if ad.get('title') and ad.get('url'):
                    ads.append(ad)
                    
            except Exception as e:
                print(f"⚠️ Ошибка извлечения: {e}")
                continue
        
        return ads


# Тест
if __name__ == "__main__":
    parser = AvitoParserWithCaptcha(
        proxy=None,  # Пока без прокси
        headless=True  # True = не видно браузера, False = видно
    )
    
    print("=== ТЕСТ ПАРСЕРА С КАПЧАМИ ===")
    print()
    
    ads = parser.parse_listing("vorkuta", "avtomobili", max_pages=1)
    
    print()
    print(f"✅ Собрано: {len(ads)} объявлений")
    
    if ads:
        print()
        print("Пример:")
        ad = ads[0]
        print(f"  Заголовок: {ad.get('title', '')[:60]}")
        print(f"  Цена: {ad.get('price')} ₽")
        print(f"  URL: {ad.get('url')}")
