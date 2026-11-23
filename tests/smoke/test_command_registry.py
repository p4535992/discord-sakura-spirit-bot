"""Verify that the required extensions load and register the expected commands."""
import pytest

from core.bot import SakuraSpiritBot

EXPECTED_COMMANDS = {
    "admin-set-weather",
    "admin-stats",
    "admin-toggle-feature",
    "daily-dream",
    "explore",
    "game-stats",
    "inventory",
    "lfg",
    "map",
    "my-spirit",
    "profile",
    "quests",
    "relationships",
    "ritual-buff",
    "sakura-help",
    "send-gift",
    "server-info",
    "shop",
    "spirit-adopt",
    "spirit-info",
    "spirit-interact",
    "weather",
    "weather-effects",
    "weather-history",
    "weather-list",
}


@pytest.fixture
async def loaded_bot():
    bot = SakuraSpiritBot()
    for extension in bot.required_extensions:
        await bot.load_extension(extension)
    try:
        yield bot
    finally:
        await bot.close()


async def test_required_extensions_load(loaded_bot):
    """A failing required extension must fail this test, not be swallowed."""
    assert loaded_bot.startup_failures == []
    assert len(loaded_bot.extensions) == len(loaded_bot.required_extensions)


async def test_expected_slash_commands_are_registered(loaded_bot):
    registered = {command.name for command in loaded_bot.tree.get_commands()}
    assert registered == EXPECTED_COMMANDS
