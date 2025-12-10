"""
Configuration management for Sakura Spirit Bot
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Discord Configuration
    discord_token: str = Field(..., env="DISCORD_TOKEN")
    discord_client_id: str = Field(..., env="DISCORD_CLIENT_ID")
    bot_prefix: str = Field(default="!", env="BOT_PREFIX")
    bot_owner_id: Optional[str] = Field(default=None, env="BOT_OWNER_ID")
    
    # Database Configuration
    database_url: str = Field(..., env="DATABASE_URL")
    
    # Redis Configuration
    redis_url: str = Field(..., env="REDIS_URL")
    
    # OpenAI Configuration
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    
    # Riot Games API (Optional)
    riot_api_key: Optional[str] = Field(default=None, env="RIOT_API_KEY")
    
    # Environment
    environment: str = Field(default="development", env="ENVIRONMENT")
    
    # Feature Flags
    enable_spirits: bool = Field(default=True, env="ENABLE_SPIRITS")
    enable_weather: bool = Field(default=True, env="ENABLE_WEATHER")
    enable_social: bool = Field(default=True, env="ENABLE_SOCIAL")
    enable_gaming: bool = Field(default=True, env="ENABLE_GAMING")
    enable_world: bool = Field(default=True, env="ENABLE_WORLD")
    enable_gacha: bool = Field(default=True, env="ENABLE_GACHA")
    enable_events: bool = Field(default=True, env="ENABLE_EVENTS")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_file: str = Field(default="logs/sakura_bot.log", env="LOG_FILE")
    
    # Bot Behavior Settings
    command_timeout: int = 30  # seconds
    max_concurrent_events: int = 10
    spirit_roam_interval: int = 600  # 10 minutes
    weather_change_interval: int = 3600  # 1 hour
    dream_generation_hour: int = 6  # 6 AM
    
    # XP and Leveling
    xp_per_message: int = 5
    xp_cooldown: int = 60  # seconds between XP gains
    xp_multiplier_base: float = 1.0
    
    # Gacha Settings
    gacha_cost: int = 100  # currency cost per pull
    gacha_rarity_rates: dict = {
        "common": 0.60,
        "uncommon": 0.25,
        "rare": 0.10,
        "epic": 0.04,
        "legendary": 0.01
    }
    
    # Weather System
    weather_types: list = [
        "Petal Storm",
        "Lunar Bloom",
        "Eclipse",
        "Mistfall",
        "Crimson Dawn",
        "Starlight Shower",
        "Gentle Breeze",
        "Thunder Blossom",
        "Frost Petal",
        "Golden Hour",
        "Twilight Veil",
        "Chaos Wind"
    ]
    
    # Emotional States
    emotional_states: list = [
        "Blossoming",
        "Wilting",
        "Chaotic Bloom",
        "Lunar Calm",
        "Radiant",
        "Melancholic",
        "Energized",
        "Peaceful"
    ]
    
    # Spirit Factions
    spirit_factions: list = [
        "Blossoms",
        "Moonborn",
        "Stormkin"
    ]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()


def is_production() -> bool:
    """Check if running in production environment"""
    return settings.environment.lower() == "production"


def is_development() -> bool:
    """Check if running in development environment"""
    return settings.environment.lower() == "development"
