"""Settings precedence tests.

Every value is synthetic: no real secret is read, logged or written. The tests
only prove how ``Settings`` resolves the container-prefixed name, the legacy
alias and the defaults.
"""

import pytest

from core.config import Settings

REQUIRED_ENV = {
    "SAKURA_BOT_DISCORD_TOKEN": "prefixed-token",
    "SAKURA_BOT_DISCORD_CLIENT_ID": "123456789012345678",
    "SAKURA_BOT_DATABASE_URL": "postgresql+asyncpg://user:password@localhost:5432/sakura_bot",
    "SAKURA_BOT_OPENAI_API_KEY": "prefixed-openai-key",
}

LEGACY_ALIASES = (
    "DISCORD_TOKEN",
    "DISCORD_CLIENT_ID",
    "DATABASE_URL",
    "OPENAI_API_KEY",
    "BOT_PREFIX",
    "BOT_OWNER_ID",
)

# Values the shared conftest forces for the offline suite. These tests need the
# library defaults, so the overrides are removed before instantiating Settings.
CONFTEST_OVERRIDES = ("SAKURA_BOT_STRICT_STARTUP",)


@pytest.fixture
def settings_env(monkeypatch):
    """Provide a complete synthetic environment and drop every legacy alias."""
    for name in LEGACY_ALIASES + CONFTEST_OVERRIDES:
        monkeypatch.delenv(name, raising=False)
    # A developer shell may export a provider or a prefix: these tests assert the
    # library defaults, so the overrides are removed as well.
    for name in ("SAKURA_BOT_AI_PROVIDER", "AI_PROVIDER"):
        monkeypatch.delenv(name, raising=False)
    for name, value in REQUIRED_ENV.items():
        monkeypatch.setenv(name, value)
    return monkeypatch


def test_prefixed_name_wins_over_the_legacy_alias(settings_env):
    settings_env.setenv("DISCORD_TOKEN", "legacy-token")

    assert Settings().discord_token == "prefixed-token"


def test_legacy_alias_is_still_accepted(settings_env):
    settings_env.delenv("SAKURA_BOT_DISCORD_TOKEN")
    settings_env.setenv("DISCORD_TOKEN", "legacy-token")

    assert Settings().discord_token == "legacy-token"


def test_prefix_setting_accepts_both_names(settings_env):
    settings_env.setenv("SAKURA_BOT_PREFIX", "?")
    assert Settings().bot_prefix == "?"

    settings_env.delenv("SAKURA_BOT_PREFIX")
    settings_env.setenv("BOT_PREFIX", "!")
    assert Settings().bot_prefix == "!"


def test_defaults_are_applied(settings_env):
    settings = Settings()

    assert settings.openai_model == "gpt-4.1-mini"
    assert settings.ai_provider == "openai"
    assert settings.health_port == 8080


def test_boolean_flags_are_parsed(settings_env):
    settings_env.setenv("SAKURA_BOT_STRICT_STARTUP", "false")

    settings = Settings()

    assert settings.strict_startup is False
