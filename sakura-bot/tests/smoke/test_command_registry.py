"""Verify that the required extensions load and register the expected commands."""
import pytest

from core.bot import SakuraSpiritBot

# Every slash command is namespaced with this prefix, so the bot cannot collide
# with commands registered by other bots in the same guild.
COMMAND_PREFIX = "sakura-"

EXPECTED_COMMANDS = {
    "sakura-admin-set-weather",
    "sakura-admin-stats",
    "sakura-admin-toggle-feature",
    "sakura-daily-dream",
    "sakura-explore",
    "sakura-game-stats",
    "sakura-help",
    "sakura-inventory",
    "sakura-lfg",
    "sakura-map",
    "sakura-my-spirit",
    "sakura-profile",
    "sakura-quests",
    "sakura-relationships",
    "sakura-ritual-buff",
    "sakura-send-gift",
    "sakura-server-info",
    "sakura-shop",
    "sakura-spirit-adopt",
    "sakura-spirit-info",
    "sakura-spirit-interact",
    "sakura-weather",
    "sakura-weather-effects",
    "sakura-weather-history",
    "sakura-weather-list",
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


async def test_every_command_uses_the_sakura_prefix(loaded_bot):
    """A new command without the namespace prefix must fail here, not in Discord."""
    for command in loaded_bot.tree.get_commands():
        assert command.name.startswith(COMMAND_PREFIX), command.name
