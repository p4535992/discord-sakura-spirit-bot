"""Runtime authorization for the administrative slash commands.

The registered ``app_commands.Command`` objects are inspected directly: the
permission check is evaluated with a fake interaction and the callback is
invoked with a fake guild, so no Discord API call is made and no database is
contacted.
"""

import inspect

import discord
import pytest
from discord import app_commands

import commands.admin_commands as admin_commands
from commands.admin_commands import AdminCommands

ADMIN_COMMAND_NAMES = (
    "sakura-admin-toggle-feature",
    "sakura-admin-set-weather",
    "sakura-admin-stats",
)


class FakeResponse:
    """Record the messages sent through ``interaction.response``."""

    def __init__(self):
        self.messages = []
        self.deferred = False

    def is_done(self):
        return bool(self.messages) or self.deferred

    async def send_message(self, content=None, **kwargs):
        self.messages.append({"content": content, **kwargs})


class FakeGuild:
    id = 987654321098765432
    name = "Sakura Test Guild"


class FakeUser:
    id = 111111111111111111
    name = "tester"


class FakeInteraction:
    def __init__(self, *, guild=None, administrator=False):
        self.guild = guild
        # ``app_commands.checks.has_permissions`` reads this attribute only.
        self.permissions = discord.Permissions(administrator=administrator)
        self.response = FakeResponse()
        self.user = FakeUser()


def _command(name):
    """Return the registered command object without loading the extension."""
    for value in vars(AdminCommands).values():
        if isinstance(value, app_commands.Command) and value.name == name:
            return value
    raise AssertionError(f"command {name} is not registered")


async def _run_checks(command, interaction):
    """Evaluate the registered checks the way ``Command._check_can_run`` does."""
    for check in command.checks:
        result = check(interaction)
        if inspect.isawaitable(result):
            result = await result
        if result is False:
            raise app_commands.CheckFailure("a registered check returned False")
    return True


@pytest.mark.parametrize("name", ADMIN_COMMAND_NAMES)
def test_admin_commands_declare_a_runtime_permission_check(name):
    command = _command(name)

    assert command.default_permissions is not None
    assert command.default_permissions.administrator is True
    assert command.checks, "the Discord default is metadata, not enforcement"


@pytest.mark.parametrize("name", ADMIN_COMMAND_NAMES)
async def test_a_member_without_administrator_is_rejected(name):
    interaction = FakeInteraction(guild=FakeGuild(), administrator=False)

    with pytest.raises(app_commands.MissingPermissions):
        await _run_checks(_command(name), interaction)


@pytest.mark.parametrize("name", ADMIN_COMMAND_NAMES)
async def test_an_administrator_passes_the_check(name):
    interaction = FakeInteraction(guild=FakeGuild(), administrator=True)

    assert await _run_checks(_command(name), interaction) is True


async def test_a_direct_message_is_rejected_by_the_check():
    """``interaction.permissions`` is empty in a DM, so the check fails there."""
    interaction = FakeInteraction(guild=None, administrator=False)

    with pytest.raises(app_commands.MissingPermissions):
        await _run_checks(_command("sakura-admin-toggle-feature"), interaction)


async def test_the_toggle_body_rejects_a_direct_message_before_the_database(monkeypatch):
    def _unexpected_session():
        raise AssertionError("the database must not be opened in a direct message")

    monkeypatch.setattr(admin_commands, "get_db_session", _unexpected_session)
    interaction = FakeInteraction(guild=None)

    await AdminCommands.toggle_feature.callback(AdminCommands(None), interaction, "weather", False)

    assert interaction.response.messages == [
        {"content": "This command can only be used in a server!", "ephemeral": True}
    ]


async def test_the_weather_body_rejects_a_direct_message_before_the_database(monkeypatch):
    def _unexpected_session():
        raise AssertionError("the database must not be opened in a direct message")

    monkeypatch.setattr(admin_commands, "get_db_session", _unexpected_session)
    interaction = FakeInteraction(guild=None)

    await AdminCommands.set_weather.callback(AdminCommands(None), interaction, "Petal Storm")

    assert interaction.response.messages == [
        {"content": "This command can only be used in a server!", "ephemeral": True}
    ]
