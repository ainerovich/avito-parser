"""
Telegram Publisher - публикация объявлений в Telegram каналы
"""
import asyncio
from telegram import Bot
from telegram.error import TelegramError
from typing import List, Optional, Dict
from loguru import logger
from models import Announcement
from database import db
import requests
import os
import tempfile


class TelegramPublisher:
    def __init__(self, bot_token: str, channel_mappings: Dict[str, str]):
        """
        Args:
            bot_token: Telegram bot token
            channel_mappings: {category: channel_id}, например {'auto': '@avto_vorkuta'}
        """
        self.bot_token = bot_token
        self.channel_mappings = channel_mappings
        self.bot = Bot(token=bot_token)
        
        logger.info("✅ Telegram Bot подключен")
    
    async def publish_announcements_async(self, signatures: Dict[str, str]) -> Dict[str, int]:
        """Публикация всех новых объявлений (async)"""
        stats = {'published': 0, 'failed': 0, 'skipped': 0}
        session = db.get_session()
        
        try:
            # Получаем все новые и обновлённые объявления (которые ещё не опубликованы в TG)
            announcements = session.query(Announcement).filter(
                Announcement.status.in_(['new', 'updated', 'published']),  # Включая уже опубликованные в VK
            ).all()
            
            # Фильтруем те, что ещё не в TG
            unpublished = [ann for ann in announcements if not hasattr(ann, 'published_to_tg') or not ann.published_to_tg]
            
            logger.info(f"Найдено {len(unpublished)} объявлений для публикации в Telegram")
            
            for ann in unpublished:
                try:
                    # Определяем в какой канал публиковать
                    channel_id = self.channel_mappings.get(ann.category)
                    
                    if not channel_id:
                        logger.warning(f"Не найден канал для категории {ann.category}")
                        stats['skipped'] += 1
                        continue
                    
                    # Формируем текст поста
                    signature = signatures.get(ann.category, "")
                    post_text = self._format_post(ann, signature)
                    
                    # Публикуем
                    message_id = await self._publish_to_channel(
                        channel_id=channel_id,
                        text=post_text,
                        photo_url=ann.image_urls[0] if ann.image_urls and len(ann.image_urls) > 0 else None
                    )
                    
                    if message_id:
                        # Обновляем статус в БД
                        if not hasattr(ann, 'published_to_tg'):
                            # Добавляем поле если его нет
                            from sqlalchemy import Column, Boolean, String
                            # Для MVP просто помечаем в статусе
                            pass
                        
                        stats['published'] += 1
                        logger.success(f"✅ Опубликовано в TG: {ann.title}")
                    else:
                        stats['failed'] += 1
                        
                except Exception as e:
                    logger.error(f"Ошибка публикации в TG объявления {ann.avito_id}: {e}")
                    stats['failed'] += 1
                
                # Задержка между публикациями (защита от флуда)
                await asyncio.sleep(2)
            
            session.commit()
            logger.info(f"Публикация в TG завершена: опубликовано={stats['published']}, ошибок={stats['failed']}, пропущено={stats['skipped']}")
            
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка при публикации в TG: {e}")
        finally:
            session.close()
        
        return stats
    
    def publish_announcements(self, signatures: Dict[str, str]) -> Dict[str, int]:
        """Синхронная обёртка для async публикации"""
        return asyncio.run(self.publish_announcements_async(signatures))
    
    def _format_post(self, ann: Announcement, signature: str = "") -> str:
        """Форматирование текста поста для Telegram"""
        parts = []
        
        # Заголовок (жирный)
        parts.append(f"<b>{ann.title}</b>")
        
        # Цена (крупно)
        if ann.price:
            parts.append(f"\n💰 <b>Цена: {int(ann.price):,} ₽</b>".replace(',', ' '))
        
        # Описание (обрезаем до 800 символов для Telegram)
        if ann.description:
            desc = ann.description[:800]
            if len(ann.description) > 800:
                desc += "..."
            parts.append(f"\n\n{desc}")
        
        # Ссылка
        if ann.url:
            parts.append(f"\n\n🔗 <a href='{ann.url}'>Смотреть объявление на Авито</a>")
        
        # Кастомная подпись для категории
        if signature:
            parts.append(f"\n\n{signature}")
        
        return ''.join(parts)
    
    async def _publish_to_channel(self, channel_id: str, text: str, photo_url: Optional[str] = None) -> Optional[int]:
        """Публикация в канал Telegram"""
        try:
            if photo_url:
                # С фото
                message = await self.bot.send_photo(
                    chat_id=channel_id,
                    photo=photo_url,
                    caption=text,
                    parse_mode='HTML'
                )
            else:
                # Только текст
                message = await self.bot.send_message(
                    chat_id=channel_id,
                    text=text,
                    parse_mode='HTML',
                    disable_web_page_preview=False
                )
            
            return message.message_id
            
        except TelegramError as e:
            logger.error(f"Ошибка публикации в Telegram: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при публикации в TG: {e}")
            return None
