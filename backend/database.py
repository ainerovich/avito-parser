"""
Database connection and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from models import Base
import os


class Database:
    def __init__(self, db_path: str = "data/avito_parser.db"):
        """Инициализация БД"""
        # Создаём директорию если не существует
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.db_url = f"sqlite:///{db_path}"
        self.engine = create_engine(
            self.db_url,
            connect_args={"check_same_thread": False},  # Для SQLite
            echo=False  # True для debug SQL запросов
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
    def init_db(self):
        """Создание таблиц"""
        Base.metadata.create_all(bind=self.engine)
        print("✅ База данных инициализирована")
    
    def get_session(self) -> Session:
        """Получить сессию БД"""
        return self.SessionLocal()
    
    def close(self):
        """Закрыть соединение"""
        self.engine.dispose()


# Singleton instance
db = Database()
