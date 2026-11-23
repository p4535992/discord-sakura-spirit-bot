"""
Configuration management for Sakura Spirit Bot

``.env`` is loaded by ``SettingsConfigDict`` itself, so the settings object is
the single entry point for configuration and no separate ``load_dotenv`` call
is required.

``.env`` groups variables by container (``SAKURA_BOT_*``, ``POSTGRES_*``, ...).
Every bot setting therefore accepts both the canonical name and the container
prefixed one, so the same file works for the container and for a host run.
"""
from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _bot_env(name: str) -> AliasChoices:
    """Accept the container-prefixed ``SAKURA_BOT_<name>`` and the ``name``.

    ``.env`` keeps variables grouped by container, so the prefixed form has
    precedence; the canonical name stays supported for existing deployments.
    """
    return AliasChoices(f"SAKURA_BOT_{name}", name)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Discord Configuration
    discord_token: str = Field(
        ...,
        validation_alias=_bot_env("DISCORD_TOKEN"),
        description="Discord bot token, e.g. the value shown in the Developer Portal.",
    )
    discord_client_id: str = Field(
        ...,
        validation_alias=_bot_env("DISCORD_CLIENT_ID"),
        description="Discord application client ID, e.g. 123456789012345678.",
    )
    bot_prefix: str = Field(
        default="!",
        validation_alias=AliasChoices("SAKURA_BOT_PREFIX", "BOT_PREFIX"),
        description="Legacy text command prefix, e.g. !.",
    )
    bot_owner_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("SAKURA_BOT_OWNER_ID", "BOT_OWNER_ID"),
        description="Discord user ID of the bot owner, e.g. 123456789012345678.",
    )

    # Database Configuration
    database_url: str = Field(
        ...,
        validation_alias=_bot_env("DATABASE_URL"),
        description="SQLAlchemy async URL, e.g. postgresql+asyncpg://user:pass@host:5432/db.",
    )

    # Redis Configuration
    redis_url: str = Field(
        ...,
        validation_alias=_bot_env("REDIS_URL"),
        description="Redis URL used for caching, e.g. redis://localhost:6379/0.",
    )
    cache_required: bool = Field(
        default=True,
        validation_alias=_bot_env("CACHE_REQUIRED"),
        description="Fail startup when Redis is unreachable; false enables degraded cache mode.",
    )

    # OpenAI Configuration
    openai_api_key: str = Field(
        ...,
        validation_alias=_bot_env("OPENAI_API_KEY"),
        description="OpenAI API key used by the spirit AI provider.",
    )
    openai_model: str = Field(
        default="gpt-4.1-mini",
        validation_alias=_bot_env("OPENAI_MODEL"),
        description="Chat completion model used by the spirit AI, e.g. gpt-4.1-mini.",
    )
    openai_timeout_seconds: float = Field(
        default=20.0,
        validation_alias=_bot_env("OPENAI_TIMEOUT_SECONDS"),
        description="Timeout in seconds for a single AI request, e.g. 20.0.",
    )

    # Riot Games API (Optional)
    riot_api_key: Optional[str] = Field(
        default=None,
        validation_alias=_bot_env("RIOT_API_KEY"),
        description="Optional Riot Games API key; unused by the current commands.",
    )

    # Environment
    environment: str = Field(
        default="development",
        validation_alias=_bot_env("ENVIRONMENT"),
        description="Deployment environment label, e.g. development or production.",
    )
    strict_startup: bool = Field(
        default=True,
        validation_alias=_bot_env("STRICT_STARTUP"),
        description="Abort startup when a required extension fails to load.",
    )

    # Health endpoint used by container orchestration
    health_server_enabled: bool = Field(
        default=True,
        validation_alias=_bot_env("HEALTH_SERVER_ENABLED"),
        description="Expose the HTTP health endpoint used by Docker healthchecks.",
    )
    health_host: str = Field(
        default="0.0.0.0",
        validation_alias=_bot_env("HEALTH_HOST"),
        description="Bind address of the health endpoint, e.g. 0.0.0.0.",
    )
    health_port: int = Field(
        default=8080,
        validation_alias=_bot_env("HEALTH_PORT"),
        description="TCP port of the health endpoint, e.g. 8080.",
    )

    # Feature Flags
    enable_spirits: bool = Field(
        default=True,
        validation_alias=_bot_env("ENABLE_SPIRITS"),
        description="Enable the spirit system.",
    )
    enable_weather: bool = Field(
        default=True,
        validation_alias=_bot_env("ENABLE_WEATHER"),
        description="Enable the weather system.",
    )
    enable_social: bool = Field(
        default=True,
        validation_alias=_bot_env("ENABLE_SOCIAL"),
        description="Enable the social system.",
    )
    enable_gaming: bool = Field(
        default=True,
        validation_alias=_bot_env("ENABLE_GAMING"),
        description="Enable the gaming utilities.",
    )
    enable_world: bool = Field(
        default=True,
        validation_alias=_bot_env("ENABLE_WORLD"),
        description="Enable the Sakura Park world.",
    )
    enable_gacha: bool = Field(
        default=True,
        validation_alias=_bot_env("ENABLE_GACHA"),
        description="Enable the gacha system.",
    )
    enable_events: bool = Field(
        default=True,
        validation_alias=_bot_env("ENABLE_EVENTS"),
        description="Enable global events.",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        validation_alias=_bot_env("LOG_LEVEL"),
        description="Root log level, e.g. INFO or DEBUG.",
    )
    log_file: str = Field(
        default="logs/sakura_bot.log",
        validation_alias=_bot_env("LOG_FILE"),
        description="Log file path; its parent directory is created at startup.",
    )
    
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


# Global settings instance
settings = Settings()


def is_production() -> bool:
    """Check if running in production environment"""
    return settings.environment.lower() == "production"


def is_development() -> bool:
    """Check if running in development environment"""
    return settings.environment.lower() == "development"
