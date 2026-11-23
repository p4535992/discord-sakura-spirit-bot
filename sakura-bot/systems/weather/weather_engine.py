"""
Dynamic weather system for Sakura Spirit Bot
"""
import logging
import random
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Server, WeatherHistory
from core.config import settings

logger = logging.getLogger(__name__)


class WeatherType:
    """Weather type definitions with effects"""
    
    WEATHER_DATA = {
        "Petal Storm": {
            "description": "Cherry blossoms swirl violently through the air, creating a beautiful chaos",
            "effects": {
                "xp_multiplier": 1.3,
                "gacha_luck": 1.1,
                "spirit_activity": "high"
            },
            "emoji": "🌸💨",
            "rarity": "uncommon"
        },
        "Lunar Bloom": {
            "description": "Moonlight illuminates the blossoms, creating an ethereal glow",
            "effects": {
                "xp_multiplier": 1.2,
                "dream_quality": "enhanced",
                "spirit_activity": "medium"
            },
            "emoji": "🌙🌸",
            "rarity": "rare"
        },
        "Eclipse": {
            "description": "Darkness falls as the moon covers the sun, spirits grow restless",
            "effects": {
                "xp_multiplier": 1.5,
                "event_spawn_rate": 2.0,
                "spirit_activity": "very_high"
            },
            "emoji": "🌑",
            "rarity": "rare"
        },
        "Mistfall": {
            "description": "A gentle mist descends, obscuring the world in mystery",
            "effects": {
                "xp_multiplier": 1.0,
                "secret_discovery": 1.5,
                "spirit_activity": "low"
            },
            "emoji": "🌫️",
            "rarity": "common"
        },
        "Crimson Dawn": {
            "description": "The sky burns red as dawn breaks, filling all with energy",
            "effects": {
                "xp_multiplier": 1.4,
                "currency_gain": 1.3,
                "spirit_activity": "high"
            },
            "emoji": "🌅",
            "rarity": "uncommon"
        },
        "Starlight Shower": {
            "description": "Stars fall like rain, granting wishes to those who witness them",
            "effects": {
                "xp_multiplier": 1.3,
                "gacha_luck": 1.5,
                "spirit_activity": "medium"
            },
            "emoji": "✨⭐",
            "rarity": "rare"
        },
        "Gentle Breeze": {
            "description": "A calm wind carries petals softly through the air",
            "effects": {
                "xp_multiplier": 1.0,
                "harmony_boost": 0.5,
                "spirit_activity": "medium"
            },
            "emoji": "🍃",
            "rarity": "common"
        },
        "Thunder Blossom": {
            "description": "Lightning crackles through the cherry trees, electrifying the atmosphere",
            "effects": {
                "xp_multiplier": 1.6,
                "event_spawn_rate": 1.5,
                "spirit_activity": "very_high"
            },
            "emoji": "⚡🌸",
            "rarity": "epic"
        },
        "Frost Petal": {
            "description": "Ice crystals form on the blossoms, creating a winter wonderland",
            "effects": {
                "xp_multiplier": 1.1,
                "spirit_power": 1.2,
                "spirit_activity": "low"
            },
            "emoji": "❄️🌸",
            "rarity": "uncommon"
        },
        "Golden Hour": {
            "description": "Warm golden light bathes everything in a peaceful glow",
            "effects": {
                "xp_multiplier": 1.2,
                "harmony_boost": 1.0,
                "currency_gain": 1.2,
                "spirit_activity": "medium"
            },
            "emoji": "🌟",
            "rarity": "common"
        },
        "Twilight Veil": {
            "description": "The boundary between day and night blurs, magic flows freely",
            "effects": {
                "xp_multiplier": 1.3,
                "gacha_luck": 1.2,
                "secret_discovery": 1.3,
                "spirit_activity": "high"
            },
            "emoji": "🌆",
            "rarity": "uncommon"
        },
        "Chaos Wind": {
            "description": "Unpredictable winds tear through the realm, anything can happen",
            "effects": {
                "xp_multiplier": 2.0,
                "random_events": True,
                "gacha_luck": 0.8,
                "spirit_activity": "chaotic"
            },
            "emoji": "🌪️",
            "rarity": "legendary"
        }
    }
    
    @staticmethod
    def get_weather_info(weather_type: str) -> Dict:
        """Get information about a weather type"""
        return WeatherType.WEATHER_DATA.get(weather_type, {
            "description": "Unknown weather",
            "effects": {},
            "emoji": "❓",
            "rarity": "common"
        })
    
    @staticmethod
    def get_all_weather_types() -> List[str]:
        """Get list of all weather types"""
        return list(WeatherType.WEATHER_DATA.keys())


class WeatherEngine:
    """Manage weather changes and effects"""
    
    @staticmethod
    async def change_weather(
        session: AsyncSession,
        server: Server,
        new_weather: Optional[str] = None,
        triggered_by: str = "scheduled",
        trigger_user_id: Optional[int] = None
    ) -> str:
        """Change server weather"""
        
        # If no weather specified, select randomly
        if not new_weather:
            new_weather = WeatherEngine.select_random_weather(
                current_weather=server.current_weather,
                harmony_score=server.harmony_score
            )
        
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
        weather_info = WeatherType.get_weather_info(new_weather)
        new_weather_record = WeatherHistory(
            server_id=server.id,
            weather_type=new_weather,
            triggered_by=triggered_by,
            trigger_user_id=trigger_user_id,
            effects_json=weather_info.get("effects", {})
        )
        session.add(new_weather_record)
        
        # Update server
        old_weather = server.current_weather
        server.current_weather = new_weather
        server.weather_changed_at = datetime.utcnow()
        
        await session.commit()
        
        logger.info(f"Server {server.name} weather changed: {old_weather} -> {new_weather}")
        
        return new_weather
    
    @staticmethod
    def select_random_weather(
        current_weather: str,
        harmony_score: float,
        exclude_current: bool = True
    ) -> str:
        """Select a random weather type based on rarity and conditions"""
        
        # Rarity weights
        rarity_weights = {
            "common": 40,
            "uncommon": 25,
            "rare": 15,
            "epic": 5,
            "legendary": 1
        }
        
        # Adjust weights based on harmony
        if harmony_score > 80:
            # More chance for rare weather
            rarity_weights["rare"] += 10
            rarity_weights["epic"] += 5
        elif harmony_score < 30:
            # More chance for chaotic weather
            rarity_weights["legendary"] += 4
            rarity_weights["epic"] += 5
        
        # Build weighted list
        weather_choices = []
        for weather_type, data in WeatherType.WEATHER_DATA.items():
            if exclude_current and weather_type == current_weather:
                continue
            
            rarity = data.get("rarity", "common")
            weight = rarity_weights.get(rarity, 10)
            
            weather_choices.extend([weather_type] * weight)
        
        return random.choice(weather_choices)
    
    @staticmethod
    def get_xp_multiplier(weather_type: str) -> float:
        """Get XP multiplier for current weather"""
        weather_info = WeatherType.get_weather_info(weather_type)
        return weather_info.get("effects", {}).get("xp_multiplier", 1.0)
    
    @staticmethod
    def get_gacha_luck_multiplier(weather_type: str) -> float:
        """Get gacha luck multiplier for current weather"""
        weather_info = WeatherType.get_weather_info(weather_type)
        return weather_info.get("effects", {}).get("gacha_luck", 1.0)
    
    @staticmethod
    def get_currency_multiplier(weather_type: str) -> float:
        """Get currency gain multiplier for current weather"""
        weather_info = WeatherType.get_weather_info(weather_type)
        return weather_info.get("effects", {}).get("currency_gain", 1.0)
    
    @staticmethod
    def get_spirit_activity_level(weather_type: str) -> str:
        """Get spirit activity level for current weather"""
        weather_info = WeatherType.get_weather_info(weather_type)
        return weather_info.get("effects", {}).get("spirit_activity", "medium")
    
    @staticmethod
    def should_spawn_event(weather_type: str) -> bool:
        """Check if weather should trigger event spawning"""
        weather_info = WeatherType.get_weather_info(weather_type)
        event_rate = weather_info.get("effects", {}).get("event_spawn_rate", 1.0)
        
        # Base 5% chance, modified by weather
        base_chance = 0.05
        modified_chance = base_chance * event_rate
        
        return random.random() < modified_chance
    
    @staticmethod
    async def get_weather_history(
        session: AsyncSession,
        server_id: int,
        limit: int = 10
    ) -> List[WeatherHistory]:
        """Get recent weather history for a server"""
        result = await session.execute(
            select(WeatherHistory)
            .where(WeatherHistory.server_id == server_id)
            .order_by(WeatherHistory.started_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    @staticmethod
    def format_weather_effects(weather_type: str) -> List[str]:
        """Format weather effects as readable list"""
        weather_info = WeatherType.get_weather_info(weather_type)
        effects = weather_info.get("effects", {})
        
        formatted = []
        
        if "xp_multiplier" in effects and effects["xp_multiplier"] != 1.0:
            multiplier = effects["xp_multiplier"]
            percentage = int((multiplier - 1.0) * 100)
            formatted.append(f"XP gain {'+' if percentage > 0 else ''}{percentage}%")
        
        if "gacha_luck" in effects and effects["gacha_luck"] != 1.0:
            multiplier = effects["gacha_luck"]
            percentage = int((multiplier - 1.0) * 100)
            formatted.append(f"Gacha luck {'+' if percentage > 0 else ''}{percentage}%")
        
        if "currency_gain" in effects and effects["currency_gain"] != 1.0:
            multiplier = effects["currency_gain"]
            percentage = int((multiplier - 1.0) * 100)
            formatted.append(f"Currency gain {'+' if percentage > 0 else ''}{percentage}%")
        
        if "spirit_activity" in effects:
            activity = effects["spirit_activity"]
            formatted.append(f"Spirit activity: {activity}")
        
        if "harmony_boost" in effects:
            formatted.append("Harmony boost active")
        
        if "random_events" in effects:
            formatted.append("Random events may occur!")
        
        return formatted if formatted else ["No special effects"]
