"""
Service layer for database operations
"""
import logging
from typing import Optional
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import User, UserStats, Server
from core.cache import set_server_cache, set_user_cache

logger = logging.getLogger(__name__)


class UserService:
    """Service for user-related operations"""
    
    @staticmethod
    async def get_or_create_user(session: AsyncSession, discord_id: int, username: str) -> User:
        """Get existing user or create new one"""
        # Query database
        result = await session.execute(
            select(User).where(User.discord_id == discord_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            # Create new user
            user = User(
                discord_id=discord_id,
                username=username,
                xp=0,
                level=1,
                currency=100,  # Starting currency
                emotional_state="Blossoming"
            )
            session.add(user)
            
            # Flush assigns the autoincremented primary key before the dependent
            # row is built; without it ``user.id`` is still None and the
            # non-nullable ``user_stats.user_id`` foreign key fails.
            await session.flush()
            
            # Create user stats
            stats = UserStats(user_id=user.id)
            session.add(stats)
            
            await session.commit()
            await session.refresh(user)
            
            logger.info(f"Created new user: {username} (ID: {discord_id})")
        else:
            # Update last active
            user.last_active = datetime.utcnow()
            user.username = username  # Update username if changed
            await session.commit()
        
        # Cache user data
        await set_user_cache(discord_id, "profile", {
            "id": user.id,
            "level": user.level,
            "xp": user.xp,
            "currency": user.currency,
            "emotional_state": user.emotional_state
        }, expire=300)
        
        return user
    
    @staticmethod
    async def add_xp(session: AsyncSession, user: User, amount: int) -> tuple[bool, Optional[int]]:
        """
        Add XP to user and check for level up
        Returns: (level_up_occurred, new_level)
        """
        leveled_up = user.add_xp(amount)
        user.last_xp_gain = datetime.utcnow()
        
        await session.commit()
        
        # Update cache
        await set_user_cache(user.discord_id, "profile", {
            "id": user.id,
            "level": user.level,
            "xp": user.xp,
            "currency": user.currency,
            "emotional_state": user.emotional_state
        }, expire=300)
        
        if leveled_up:
            logger.info(f"User {user.username} leveled up to {user.level}")
            return True, user.level
        
        return False, None
    
    @staticmethod
    async def can_gain_xp(user: User, cooldown_seconds: int = 60) -> bool:
        """Check if user can gain XP (cooldown check)"""
        if not user.last_xp_gain:
            return True
        
        time_since_last = datetime.utcnow() - user.last_xp_gain
        return time_since_last.total_seconds() >= cooldown_seconds
    
    @staticmethod
    async def add_currency(session: AsyncSession, user: User, amount: int):
        """Add currency to user"""
        user.currency += amount
        await session.commit()
        
        # Update cache
        await set_user_cache(user.discord_id, "currency", user.currency, expire=300)
    
    @staticmethod
    async def spend_currency(session: AsyncSession, user: User, amount: int) -> bool:
        """
        Spend currency if user has enough
        Returns: True if successful, False if insufficient funds
        """
        if user.currency < amount:
            return False
        
        user.currency -= amount
        await session.commit()
        
        # Update cache
        await set_user_cache(user.discord_id, "currency", user.currency, expire=300)
        
        return True
    
    @staticmethod
    async def update_emotional_state(session: AsyncSession, user: User, new_state: str):
        """Update user's emotional state"""
        from models import EmotionalHistory
        
        old_state = user.emotional_state
        user.emotional_state = new_state
        
        # Record in history
        history_entry = EmotionalHistory(
            user_id=user.id,
            emotional_state=new_state,
            intensity=1.0
        )
        session.add(history_entry)
        
        await session.commit()
        
        logger.info(f"User {user.username} emotional state changed: {old_state} -> {new_state}")


class ServerService:
    """Service for server-related operations"""
    
    @staticmethod
    async def get_or_create_server(session: AsyncSession, discord_id: int, name: str) -> Server:
        """Get existing server or create new one"""
        # Query database
        result = await session.execute(
            select(Server).where(Server.discord_id == discord_id)
        )
        server = result.scalar_one_or_none()
        
        if not server:
            # Create new server
            from core.config import settings
            
            server = Server(
                discord_id=discord_id,
                name=name,
                harmony_score=50.0,
                current_weather="Gentle Breeze",
                enabled_features={
                    "spirits": settings.enable_spirits,
                    "weather": settings.enable_weather,
                    "social": settings.enable_social,
                    "gaming": settings.enable_gaming,
                    "world": settings.enable_world,
                    "gacha": settings.enable_gacha,
                    "events": settings.enable_events,
                }
            )
            session.add(server)
            await session.commit()
            await session.refresh(server)
            
            logger.info(f"Created new server: {name} (ID: {discord_id})")
        else:
            # Update last active
            server.last_active = datetime.utcnow()
            server.name = name  # Update name if changed
            await session.commit()
        
        # Cache server data
        await set_server_cache(discord_id, "config", {
            "id": server.id,
            "harmony_score": server.harmony_score,
            "current_weather": server.current_weather,
            "enabled_features": server.enabled_features
        }, expire=600)
        
        return server
    
    @staticmethod
    async def update_harmony(session: AsyncSession, server: Server, change: float):
        """Update server harmony score"""
        server.harmony_score = max(0.0, min(100.0, server.harmony_score + change))
        await session.commit()
        
        # Update cache
        await set_server_cache(server.discord_id, "harmony", server.harmony_score, expire=300)
    
    @staticmethod
    async def change_weather(session: AsyncSession, server: Server, new_weather: str):
        """Change server weather"""
        from models import WeatherHistory
        
        # End current weather period
        result = await session.execute(
            select(WeatherHistory)
            .where(WeatherHistory.server_id == server.id)
            .where(WeatherHistory.ended_at.is_(None))
        )
        current_weather_record = result.scalar_one_or_none()
        
        if current_weather_record:
            current_weather_record.ended_at = datetime.utcnow()
        
        # Create new weather record
        new_weather_record = WeatherHistory(
            server_id=server.id,
            weather_type=new_weather,
            triggered_by="scheduled"
        )
        session.add(new_weather_record)
        
        # Update server
        server.current_weather = new_weather
        server.weather_changed_at = datetime.utcnow()
        
        await session.commit()
        
        # Update cache
        await set_server_cache(server.discord_id, "weather", new_weather, expire=3600)
        
        logger.info(f"Server {server.name} weather changed to: {new_weather}")
    
    @staticmethod
    async def is_feature_enabled(server: Server, feature: str) -> bool:
        """Check if a feature is enabled for the server"""
        if not server.enabled_features:
            return True  # Default to enabled
        
        return server.enabled_features.get(feature, True)
