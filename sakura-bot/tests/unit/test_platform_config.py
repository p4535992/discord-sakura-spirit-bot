"""Platform selection tests.

The transport patches are global, so every test restores them: the suite must
stay order independent and the ``discord`` mode must remain the untouched
default. No real endpoint is contacted; only class attributes are inspected.
"""

import pytest
from discord.asset import Asset
from discord.gateway import DiscordWebSocket
from discord.http import Route

from core.config import Settings
from core.platform import (
    PlatformConfigurationError,
    apply_platform_overrides,
    restore_platform_overrides,
    validate_platform_settings,
)

DISCORD_REST_BASE = "https://discord.com/api/v10"
DISCORD_GATEWAY = "wss://gateway.discord.gg/"

REQUIRED_ENV = {
    "SAKURA_BOT_DISCORD_TOKEN": "test-token",
    "SAKURA_BOT_DISCORD_CLIENT_ID": "123456789012345678",
    "SAKURA_BOT_DATABASE_URL": "postgresql+asyncpg://user:password@localhost:5432/sakura_bot",
    "SAKURA_BOT_OPENAI_API_KEY": "test-openai-key",
}

PLATFORM_ENV = (
    "SAKURA_BOT_PLATFORM",
    "SAKURA_BOT_API_BASE_URL",
    "SAKURA_BOT_GATEWAY_URL",
    "SAKURA_BOT_ASSET_BASE_URL",
)

LEGACY_ALIASES = (
    "DISCORD_TOKEN",
    "DISCORD_CLIENT_ID",
    "DATABASE_URL",
    "OPENAI_API_KEY",
)


@pytest.fixture(autouse=True)
def restore_after_test():
    """Always undo the patches, even when a test fails halfway."""
    yield
    restore_platform_overrides()


@pytest.fixture
def env(monkeypatch):
    """Complete synthetic environment with no platform overrides."""
    for name in LEGACY_ALIASES + PLATFORM_ENV:
        monkeypatch.delenv(name, raising=False)
    for name, value in REQUIRED_ENV.items():
        monkeypatch.setenv(name, value)
    return monkeypatch


def test_default_platform_is_discord(env):
    assert Settings().platform == "discord"


def test_unknown_platform_is_rejected(env):
    env.setenv("SAKURA_BOT_PLATFORM", "matrix")

    with pytest.raises(PlatformConfigurationError, match="PLATFORM must be one of"):
        validate_platform_settings(Settings())


def test_spacebar_requires_api_base_url(env):
    env.setenv("SAKURA_BOT_PLATFORM", "spacebar")
    env.setenv("SAKURA_BOT_GATEWAY_URL", "ws://spacebar-gateway:3001")

    with pytest.raises(PlatformConfigurationError, match="SAKURA_BOT_API_BASE_URL is required"):
        validate_platform_settings(Settings())


def test_spacebar_requires_gateway_url(env):
    env.setenv("SAKURA_BOT_PLATFORM", "spacebar")
    env.setenv("SAKURA_BOT_API_BASE_URL", "http://spacebar-api:3001/api/v9")

    with pytest.raises(PlatformConfigurationError, match="SAKURA_BOT_GATEWAY_URL is required"):
        validate_platform_settings(Settings())


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("SAKURA_BOT_API_BASE_URL", "https://discord.com/api/v10"),
        ("SAKURA_BOT_API_BASE_URL", "https://api.discord.com/api/v10"),
        ("SAKURA_BOT_API_BASE_URL", "https://api.openai.com/v1"),
        ("SAKURA_BOT_GATEWAY_URL", "wss://gateway.discord.gg/"),
        ("SAKURA_BOT_ASSET_BASE_URL", "https://cdn.discordapp.com"),
    ],
)
def test_spacebar_rejects_public_service_hosts(env, name, value):
    env.setenv("SAKURA_BOT_PLATFORM", "spacebar")
    env.setenv("SAKURA_BOT_API_BASE_URL", "http://spacebar-api:3001/api/v9")
    env.setenv("SAKURA_BOT_GATEWAY_URL", "ws://spacebar-gateway:3001")
    env.setenv(name, value)

    with pytest.raises(PlatformConfigurationError, match="public service host"):
        validate_platform_settings(Settings())


def test_gateway_scheme_must_be_websocket(env):
    env.setenv("SAKURA_BOT_PLATFORM", "spacebar")
    env.setenv("SAKURA_BOT_API_BASE_URL", "http://spacebar-api:3001/api/v9")
    env.setenv("SAKURA_BOT_GATEWAY_URL", "http://spacebar-gateway:3001")

    with pytest.raises(PlatformConfigurationError, match="must use one of ws, wss"):
        validate_platform_settings(Settings())


def test_discord_platform_keeps_library_defaults(env):
    apply_platform_overrides(Settings())

    assert Route.BASE == DISCORD_REST_BASE
    assert str(DiscordWebSocket.DEFAULT_GATEWAY) == DISCORD_GATEWAY


def test_discord_platform_ignores_leftover_spacebar_endpoints(env):
    """Production must not be redirected by variables left in the environment."""
    env.setenv("SAKURA_BOT_API_BASE_URL", "http://spacebar-api:3001/api/v9")
    env.setenv("SAKURA_BOT_GATEWAY_URL", "ws://spacebar-gateway:3001")
    env.setenv("SAKURA_BOT_ASSET_BASE_URL", "http://spacebar-cdn:3001")

    apply_platform_overrides(Settings())

    assert Route.BASE == DISCORD_REST_BASE
    assert str(DiscordWebSocket.DEFAULT_GATEWAY) == DISCORD_GATEWAY


def test_platform_name_is_case_insensitive(env):
    env.setenv("SAKURA_BOT_PLATFORM", "  SpaceBar  ")
    env.setenv("SAKURA_BOT_API_BASE_URL", "http://spacebar-api:3001/api/v9")
    env.setenv("SAKURA_BOT_GATEWAY_URL", "ws://spacebar-gateway:3001")

    apply_platform_overrides(Settings())

    assert Route.BASE == "http://spacebar-api:3001/api/v9"


def test_spacebar_platform_patches_transport(env):
    env.setenv("SAKURA_BOT_PLATFORM", "spacebar")
    env.setenv("SAKURA_BOT_API_BASE_URL", "http://spacebar-api:3001/api/v9/")
    env.setenv("SAKURA_BOT_GATEWAY_URL", "ws://spacebar-gateway:3001")
    env.setenv("SAKURA_BOT_ASSET_BASE_URL", "http://spacebar-cdn:3001")

    apply_platform_overrides(Settings())

    assert Route.BASE == "http://spacebar-api:3001/api/v9"
    assert str(DiscordWebSocket.DEFAULT_GATEWAY) == "ws://spacebar-gateway:3001/"
    assert Asset.BASE == "http://spacebar-cdn:3001"


def test_asset_base_is_optional(env):
    env.setenv("SAKURA_BOT_PLATFORM", "spacebar")
    env.setenv("SAKURA_BOT_API_BASE_URL", "http://spacebar-api:3001/api/v9")
    env.setenv("SAKURA_BOT_GATEWAY_URL", "ws://spacebar-gateway:3001")

    original_asset_base = Asset.BASE
    apply_platform_overrides(Settings())

    assert Asset.BASE == original_asset_base
    assert Route.BASE == "http://spacebar-api:3001/api/v9"


def test_restore_brings_back_library_defaults(env):
    env.setenv("SAKURA_BOT_PLATFORM", "spacebar")
    env.setenv("SAKURA_BOT_API_BASE_URL", "http://spacebar-api:3001/api/v9")
    env.setenv("SAKURA_BOT_GATEWAY_URL", "ws://spacebar-gateway:3001")

    apply_platform_overrides(Settings())
    restore_platform_overrides()

    assert Route.BASE == DISCORD_REST_BASE
    assert str(DiscordWebSocket.DEFAULT_GATEWAY) == DISCORD_GATEWAY
