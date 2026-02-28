"""
Avito Parser MVP - Main Entry Point
"""
import yaml
import time
import signal
import sys
from loguru import logger
from pathlib import Path

from database import db
from parser import AvitoParser
from publisher import VKPublisher


class AvitoParserApp:
    def __init__(self, config_path: str = "config.yaml"):
        """Инициализация приложения"""
        self.running = True
        self.config = self._load_config(config_path)
        self._setup_logging()
        self._setup_signal_handlers()
        
        # Инициализация БД
        db.init_db()
        
        # Инициализация компонентов
        self.parser = AvitoParser(self.config)
        self.publisher = VKPublisher(
            access_token=self.config['vk']['access_token'],
            group_mappings=self.config['vk']['groups']
        )
        
        logger.info("✅ Приложение инициализировано")
    
    def _load_config(self, path: str) -> dict:
        """Загрузка конфигурации"""
        with open(path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        logger.info(f"✅ Конфигурация загружена из {path}")
        return config
    
    def _setup_logging(self):
        """Настройка логирования"""
        log_config = self.config.get('logging', {})
        log_level = log_config.get('level', 'INFO')
        log_file = log_config.get('file', 'logs/parser.log')
        
        # Создаём директорию для логов
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        
        # Настройка loguru
        logger.remove()  # Убираем дефолтный handler
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
            level=log_level
        )
        logger.add(
            log_file,
            rotation=log_config.get('max_size', '10 MB'),
            retention=log_config.get('backup_count', 5),
            level=log_level
        )
        
        logger.info("✅ Логирование настроено")
    
    def _setup_signal_handlers(self):
        """Обработка сигналов завершения"""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Обработка Ctrl+C и завершения"""
        logger.warning(f"Получен сигнал {signum}, завершаем работу...")
        self.running = False
    
    def run_cycle(self):
        """Один цикл парсинга и публикации"""
        logger.info("=" * 60)
        logger.info("🚀 Запуск цикла парсинга")
        logger.info("=" * 60)
        
        try:
            # Парсим каждую активную ссылку
            for source in self.config['sources']:
                if not source.get('enabled', True):
                    logger.info(f"⏭️ Пропущена (отключена): {source['url']}")
                    continue
                
                logger.info(f"🔍 Парсинг: {source['url']}")
                
                # Парсинг
                max_pages = self.config['parser'].get('max_pages', 3)
                raw_announcements = self.parser.parse_listing_page(source['url'], max_pages)
                
                if not raw_announcements:
                    logger.warning("Не найдено объявлений")
                    continue
                
                # Фильтрация
                stop_words = self.config.get('stop_words', [])
                filtered_announcements = self.parser.filter_announcements(raw_announcements, stop_words)
                
                # Сохранение в БД
                category = source.get('category', 'general')
                stats = self.parser.save_to_db(filtered_announcements, category)
                
                logger.info(f"📊 Статистика: {stats}")
            
            # Публикация в VK
            logger.info("📤 Публикация в VK...")
            
            # Собираем подписи для категорий
            signatures = {}
            for source in self.config['sources']:
                category = source.get('category', 'general')
                signature = source.get('signature', '')
                signatures[category] = signature
            
            publish_stats = self.publisher.publish_announcements(signatures)
            logger.info(f"📊 Публикация: {publish_stats}")
            
            logger.success("✅ Цикл завершён успешно")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в цикле: {e}", exc_info=True)
    
    def run(self):
        """Главный цикл работы"""
        interval = self.config['parser'].get('interval', 300)
        
        logger.info(f"🔄 Запуск с интервалом {interval} секунд")
        logger.info("Нажмите Ctrl+C для остановки")
        
        # Первый запуск сразу
        self.run_cycle()
        
        # Затем по расписанию
        while self.running:
            try:
                logger.info(f"⏰ Ожидание {interval} секунд до следующего цикла...")
                
                # Ждём с проверкой флага каждую секунду
                for _ in range(interval):
                    if not self.running:
                        break
                    time.sleep(1)
                
                if self.running:
                    self.run_cycle()
                    
            except KeyboardInterrupt:
                logger.warning("Получен Ctrl+C, завершаем...")
                break
            except Exception as e:
                logger.error(f"Критическая ошибка: {e}", exc_info=True)
                logger.info("Повторный запуск через 60 секунд...")
                time.sleep(60)
        
        logger.info("👋 Приложение остановлено")


def main():
    """Entry point"""
    try:
        app = AvitoParserApp()
        app.run()
    except Exception as e:
        logger.critical(f"Не удалось запустить приложение: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
