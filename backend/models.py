"""
Database models for Avito Parser MVP
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
import hashlib
import json

Base = declarative_base()


class Announcement(Base):
    """Объявление с Avito"""
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True)
    avito_id = Column(String, unique=True, index=True, nullable=False)
    
    # Основные данные
    title = Column(String, nullable=False)
    description = Column(Text)
    price = Column(Float)
    category = Column(String)  # auto, real_estate, sport, etc.
    
    # Мета
    url = Column(String)
    image_urls = Column(JSON)  # Список URL картинок
    author_type = Column(String)  # private или business
    location = Column(String)
    
    # Дедупликация
    content_hash = Column(String, index=True)  # SHA256 хеш для дедупликации
    
    # Статус
    status = Column(String, default="new")  # new, published, filtered, duplicate
    published_to_vk = Column(Boolean, default=False)
    vk_post_id = Column(String, nullable=True)
    
    # Timestamps
    first_seen_at = Column(DateTime, default=func.now())
    last_price = Column(Float)
    last_updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    created_at = Column(DateTime, default=func.now())

    def __repr__(self):
        return f"<Announcement {self.avito_id}: {self.title[:30]}...>"

    @staticmethod
    def generate_hash(avito_id: str, title: str, description: str = "") -> str:
        """Генерация хеша для дедупликации"""
        content = f"{avito_id}_{title}_{description[:100]}"
        return hashlib.sha256(content.encode()).hexdigest()

    def to_dict(self):
        """Сериализация в dict"""
        return {
            "id": self.id,
            "avito_id": self.avito_id,
            "title": self.title,
            "description": self.description,
            "price": self.price,
            "category": self.category,
            "url": self.url,
            "image_urls": self.image_urls,
            "author_type": self.author_type,
            "location": self.location,
            "status": self.status,
            "published_to_vk": self.published_to_vk,
            "first_seen_at": self.first_seen_at.isoformat() if self.first_seen_at else None,
            "last_updated_at": self.last_updated_at.isoformat() if self.last_updated_at else None,
        }


class Log(Base):
    """Логи работы системы"""
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    level = Column(String)  # INFO, WARNING, ERROR
    service = Column(String)  # parser, publisher, proxy, system
    message = Column(Text)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now())

    def __repr__(self):
        return f"<Log [{self.level}] {self.service}: {self.message[:50]}...>"
