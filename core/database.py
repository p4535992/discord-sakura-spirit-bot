"""
Database connection and session management
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy.pool import NullPool

from models.base import Base
from core.config import settings

logger = logging.getLogger(__name__)


class Database:
    """Database manager for async SQLAlchemy operations"""
    
    def __init__(self):
        self.engine: AsyncEngine | None = None
        self.session_factory: async_sessionmaker | None = None
    
    async def connect(self):
        """Initialize database connection"""
        try:
            self.engine = create_async_engine(
                settings.database_url,
                echo=settings.log_level == "DEBUG",
                poolclass=NullPool if settings.environment == "development" else None,
                pool_pre_ping=True,
            )
            
            self.session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    async def disconnect(self):
        """Close database connection"""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connection closed")
    
    async def create_tables(self):
        """Create all database tables"""
        if not self.engine:
            raise RuntimeError("Database not connected")
        
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session context manager"""
        if not self.session_factory:
            raise RuntimeError("Database not connected")
        
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def get_session(self) -> AsyncSession:
        """Get a new database session"""
        if not self.session_factory:
            raise RuntimeError("Database not connected")
        return self.session_factory()


# Global database instance
db = Database()


async def init_database():
    """Initialize database connection and create tables"""
    await db.connect()
    await db.create_tables()


async def close_database():
    """Close database connection"""
    await db.disconnect()


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database sessions"""
    async with db.session() as session:
        yield session
