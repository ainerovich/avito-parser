"""
VK Publisher - публикация объявлений в VK группы
"""
import vk_api
from typing import List, Optional, Dict
from loguru import logger
from models import Announcement
from database import db
import requests
import os
import tempfile


class VKPublisher:
    def __init__(self, access_token: str, group_mappings: Dict[str, int]):
        """
        Args:
            access_token: VK access token
            group_mappings: {category: group_id}, например {'auto': -123456}
        """
        self.access_token = access_token
        self.group_mappings = group_mappings
        
        try:
            self.vk_session = vk_api.VkApi(token=access_token)
            self.vk = self.vk_session.get_api()
            logger.info("✅ VK API подключен")
        except Exception as e:
            logger.error(f"Ошибка подключения к VK API: {e}")
            raise
    
    def publish_announcements(self, signatures: Dict[str, str]) -> Dict[str, int]:
        """Публикация всех новых объявлений"""
        stats = {'published': 0, 'failed': 0, 'skipped': 0}
        session = db.get_session()
        
        try:
            # Получаем все новые и обновлённые объявления
            announcements = session.query(Announcement).filter(
                Announcement.published_to_vk == False,
                Announcement.status.in_(['new', 'updated'])
            ).all()
            
            logger.info(f"Найдено {len(announcements)} объявлений для публикации")
            
            for ann in announcements:
                try:
                    # Определяем в какую группу публиковать
                    group_id = self.group_mappings.get(ann.category)
                    
                    if not group_id:
                        logger.warning(f"Не найдена группа для категории {ann.category}")
                        stats['skipped'] += 1
                        continue
                    
                    # Формируем текст поста
                    signature = signatures.get(ann.category, "")
                    post_text = self._format_post(ann, signature)
                    
                    # Загружаем фото (если есть)
                    photo_attachment = None
                    if ann.image_urls and len(ann.image_urls) > 0:
                        photo_attachment = self._upload_photo(ann.image_urls[0], group_id)
                    
                    # Публикуем
                    post_id = self._publish_to_wall(
                        group_id=group_id,
                        message=post_text,
                        photo_attachment=photo_attachment
                    )
                    
                    if post_id:
                        # Обновляем статус в БД
                        ann.published_to_vk = True
                        ann.vk_post_id = str(post_id)
                        ann.status = 'published'
                        stats['published'] += 1
                        logger.success(f"✅ Опубликовано: {ann.title} (post_id={post_id})")
                    else:
                        stats['failed'] += 1
                        
                except Exception as e:
                    logger.error(f"Ошибка публикации объявления {ann.avito_id}: {e}")
                    stats['failed'] += 1
            
            session.commit()
            logger.info(f"Публикация завершена: опубликовано={stats['published']}, ошибок={stats['failed']}, пропущено={stats['skipped']}")
            
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка при публикации: {e}")
        finally:
            session.close()
        
        return stats
    
    def _format_post(self, ann: Announcement, signature: str = "") -> str:
        """Форматирование текста поста"""
        parts = []
        
        # Заголовок
        parts.append(f"📢 {ann.title}")
        
        # Цена
        if ann.price:
            parts.append(f"\n💰 Цена: {int(ann.price):,} ₽".replace(',', ' '))
        
        # Описание (обрезаем до 500 символов)
        if ann.description:
            desc = ann.description[:500]
            if len(ann.description) > 500:
                desc += "..."
            parts.append(f"\n\n{desc}")
        
        # Ссылка
        if ann.url:
            parts.append(f"\n\n🔗 Смотреть объявление: {ann.url}")
        
        # Подпись
        if signature:
            parts.append(f"\n\n{signature}")
        
        return ''.join(parts)
    
    def _upload_photo(self, image_url: str, group_id: int) -> Optional[str]:
        """Загрузка фото в VK"""
        try:
            # Скачиваем изображение
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            
            # Сохраняем временно
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                tmp_file.write(response.content)
                tmp_path = tmp_file.name
            
            try:
                # Получаем URL для загрузки
                upload_url = self.vk.photos.getWallUploadServer(group_id=abs(group_id))['upload_url']
                
                # Загружаем файл
                with open(tmp_path, 'rb') as photo_file:
                    upload_response = requests.post(upload_url, files={'photo': photo_file})
                    upload_data = upload_response.json()
                
                # Сохраняем фото
                saved_photo = self.vk.photos.saveWallPhoto(
                    group_id=abs(group_id),
                    photo=upload_data['photo'],
                    server=upload_data['server'],
                    hash=upload_data['hash']
                )[0]
                
                attachment = f"photo{saved_photo['owner_id']}_{saved_photo['id']}"
                logger.debug(f"Фото загружено: {attachment}")
                return attachment
                
            finally:
                # Удаляем временный файл
                os.unlink(tmp_path)
                
        except Exception as e:
            logger.error(f"Ошибка загрузки фото: {e}")
            return None
    
    def _publish_to_wall(self, group_id: int, message: str, photo_attachment: Optional[str] = None) -> Optional[int]:
        """Публикация на стену группы"""
        try:
            params = {
                'owner_id': group_id,
                'from_group': 1,
                'message': message,
            }
            
            if photo_attachment:
                params['attachments'] = photo_attachment
            
            response = self.vk.wall.post(**params)
            post_id = response.get('post_id')
            
            return post_id
            
        except Exception as e:
            logger.error(f"Ошибка публикации в VK: {e}")
            return None
