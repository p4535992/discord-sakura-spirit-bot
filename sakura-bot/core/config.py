"""
Configuration management for Sakura Spirit Bot

``.env`` is loaded by ``SettingsConfigDict`` itself, so the settings object is
the single entry point for configuration and no separate ``load_dotenv`` call
is required. Two locations are read, in this order: the repository root
``.env`` (the file Compose interpolates) and ``sakura-bot/.env`` next to the
code, which wins when both exist.

``.env`` groups variables by container (``SAKURA_BOT_*``, ``POSTGRES_*``, ...).
Every bot setting therefore accepts both the canonical name and the container
prefixed one, so the same file works for the container and for a host run.
"""
from typing import Optional

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Environment label that turns on the Discord beta behaviour: slash commands are
# registered on a single test guild instead of globally. Every other value keeps
# the production behaviour, so a leftover variable cannot narrow a live
# deployment by accident.
DISCORD_BETA_ENVIRONMENT = "discord-beta"

# AI providers. ``openai`` is the production default and the only one that opens
# a network connection; ``stub`` answers inside the process with deterministic
# text, for betas that must not spend credit or leak prompts.
OPENAI_PROVIDER = "openai"
STUB_PROVIDER = "stub"
SUPPORTED_AI_PROVIDERS = (OPENAI_PROVIDER, STUB_PROVIDER)

# Prefix of the values shipped in ``.env.discord-beta.example``. A run that still
# carries one of them must stop before the login instead of reaching Discord with
# a fake credential.
PLACEHOLDER_PREFIX = "INSERISCI_"


def _bot_env(name: str) -> AliasChoices:
    """Accept the container-prefixed ``SAKURA_BOT_<name>`` and the ``name``.

    ``.env`` keeps variables grouped by container, so the prefixed form has
    precedence; the canonical name stays supported for existing deployments.
    """
    return AliasChoices(f"SAKURA_BOT_{name}", name)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        # Repository root .env first, then the optional local one next to the
        # code: the later file wins, so sakura-bot/.env overrides the root file.
        env_file=("../.env", ".env"),
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
    test_guild_id: Optional[int] = Field(
        default=None,
        validation_alias=_bot_env("TEST_GUILD_ID"),
        description=(
            "Guild that receives the slash commands when SAKURA_BOT_ENVIRONMENT=discord-beta, "
            "e.g. 123456789012345678."
        ),
    )

    # Platform / transport selection
    platform: str = Field(
        default="discord",
        validation_alias=_bot_env("PLATFORM"),
        description="Chat platform to connect to: discord or spacebar, e.g. discord.",
    )
    api_base_url: Optional[str] = Field(
        default=None,
        validation_alias=_bot_env("API_BASE_URL"),
        description="REST base override; required by spacebar, e.g. http://spacebar-api:3001/api/v9.",
    )
    gateway_url: Optional[str] = Field(
        default=None,
        validation_alias=_bot_env("GATEWAY_URL"),
        description="Gateway override; required by spacebar, e.g. ws://spacebar-gateway:3001/.",
    )
    asset_base_url: Optional[str] = Field(
        default=None,
        validation_alias=_bot_env("ASSET_BASE_URL"),
        description="CDN base override for avatars and icons, e.g. http://spacebar-cdn:3001.",
    )

    # Database Configuration
    database_url: str = Field(
        ...,
        validation_alias=_bot_env("DATABASE_URL"),
        description="SQLAlchemy async URL, e.g. postgresql+asyncpg://user:pass@host:5432/db.",
    )

    # The cache is in-process (``core/cache.py``): there is no Redis URL and no
    # cache flag to configure. LFG sessions and ritual cooldowns are game state
    # and live in PostgreSQL (``core/lfg_repository.py``).

    # OpenAI Configuration
    openai_api_key: Optional[str] = Field(
        default=None,
        validation_alias=_bot_env("OPENAI_API_KEY"),
        description=(
            "OpenAI API key used by the spirit AI; required when "
            "SAKURA_BOT_AI_PROVIDER=openai, e.g. sk-..."
        ),
    )
    ai_provider: str = Field(
        default=OPENAI_PROVIDER,
        validation_alias=_bot_env("AI_PROVIDER"),
        description="AI backend: openai (network) or stub (deterministic, offline), e.g. openai.",
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
    openai_base_url: Optional[str] = Field(
        default=None,
        validation_alias=_bot_env("OPENAI_BASE_URL"),
        description="Override of the OpenAI API base, e.g. http://ai-mock:8081/v1 for the local stub.",
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
    # No log file: the application writes to stdout/stderr and Docker rotates
    # the json-file driver output (max-size/max-file in the Compose files).
    
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

    @field_validator("ai_provider")
    @classmethod
    def _normalize_ai_provider(cls, value: str) -> str:
        """Accept ``Stub`` or `` openai `` and store the canonical lowercase value."""
        return (value or "").strip().lower()

    @model_validator(mode="after")
    def _require_openai_key_for_openai_provider(self):
        """Keep the fail-fast contract: the network provider needs its key.

        ``stub`` is the only provider that works without a key, so a beta cannot
        start with a half-configured OpenAI client either.
        """
        if self.ai_provider == OPENAI_PROVIDER and not (self.openai_api_key or "").strip():
            raise ValueError(
                "SAKURA_BOT_OPENAI_API_KEY is required when SAKURA_BOT_AI_PROVIDER=openai"
            )
        return self

    @model_validator(mode="after")
    def _reject_template_placeholders(self):
        """Refuse the ``.env`` template placeholders instead of failing at login.

        ``.env.discord-beta.example`` ships ``INSERISCI_*`` values: starting with
        one of them would reach Discord with a fake token and fail with a
        misleading "improper token" error.
        """
        pending = [
            name
            for name, value in (
                ("SAKURA_BOT_DISCORD_TOKEN", self.discord_token),
                ("SAKURA_BOT_DISCORD_CLIENT_ID", self.discord_client_id),
            )
            if isinstance(value, str) and value.strip().upper().startswith(PLACEHOLDER_PREFIX)
        ]
        if pending:
            raise ValueError(
                "Replace the .env template placeholders before starting: " + ", ".join(pending)
            )
        return self


# Global settings instance
settings = Settings()


def is_production() -> bool:
    """Check if running in production environment"""
    return settings.environment.lower() == "production"


def is_development() -> bool:
    """Check if running in development environment"""
    return settings.environment.lower() == "development"


def is_discord_beta() -> bool:
    """Check if running the Discord beta environment (guild-scoped command sync)"""
    return settings.environment.strip().lower() == DISCORD_BETA_ENVIRONMENT
