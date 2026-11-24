"""Guild-dependent commands and raw events must fail safely.

Everything is mocked: no Discord connection and no PostgreSQL server is
contacted. The callbacks are invoked through ``Command.callback``; the LFG
reaction test uses the in-memory SQLite session factory of ``conftest``.
"""

from contextlib import asynccontextmanager

import commands.gaming_commands as gaming_commands
import commands.spirit_commands as spirit_commands
from commands.gaming_commands import GamingCommands
from commands.spirit_commands import SpiritCommands
from core.lfg_repository import create_session, get_session, list_member_ids

SERVER_ONLY_MESSAGE = "This command can only be used in a server!"


class FakeResponse:
    def __init__(self):
        self.messages = []
        self.deferred = False

    def is_done(self):
        return bool(self.messages) or self.deferred

    async def defer(self):
        self.deferred = True

    async def send_message(self, content=None, **kwargs):
        self.messages.append({"content": content, **kwargs})


class FakeUser:
    id = 111111111111111111
    name = "tester"


class FakeChannel:
    id = 222222222222222222


class FakeInteraction:
    def __init__(self, guild=None):
        self.guild = guild
        self.response = FakeResponse()
        self.user = FakeUser()
        self.channel = FakeChannel()


class FakeEmoji:
    name = "✅"


class FakeMember:
    def __init__(self, bot=False):
        self.bot = bot


class FakePayload:
    def __init__(self, *, guild_id=1, channel_id=2, message_id=3, user_id=4, member=None):
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.message_id = message_id
        self.user_id = user_id
        self.member = member
        self.emoji = FakeEmoji()


class FakeBot:
    def __init__(self, channel=None):
        self._channel = channel

    def get_channel(self, channel_id):
        return self._channel


def _unexpected_session():
    raise AssertionError("the database must not be opened for an ignored reaction")


def _session_provider(factory):
    """Return a ``get_db_session`` replacement bound to the test database."""

    @asynccontextmanager
    async def _provider():
        async with factory() as session:
            yield session

    return _provider


async def test_spirit_interact_rejects_a_direct_message(monkeypatch):
    monkeypatch.setattr(spirit_commands, "get_db_session", _unexpected_session)
    interaction = FakeInteraction(guild=None)

    await SpiritCommands.spirit_interact.callback(SpiritCommands(None), interaction, "hello")

    assert interaction.response.deferred is False
    assert interaction.response.messages == [{"content": SERVER_ONLY_MESSAGE, "ephemeral": True}]


async def test_lfg_rejects_a_direct_message(monkeypatch):
    monkeypatch.setattr(gaming_commands, "get_db_session", _unexpected_session)
    interaction = FakeInteraction(guild=None)

    await GamingCommands.lfg.callback(GamingCommands(None), interaction, "Valorant", 5, None)

    assert interaction.response.messages == [{"content": SERVER_ONLY_MESSAGE, "ephemeral": True}]


async def test_raw_reaction_without_a_member_is_ignored(monkeypatch):
    monkeypatch.setattr(gaming_commands, "get_db_session", _unexpected_session)

    await GamingCommands(FakeBot()).on_raw_reaction_add(FakePayload(member=None))


async def test_raw_reaction_outside_a_guild_is_ignored(monkeypatch):
    monkeypatch.setattr(gaming_commands, "get_db_session", _unexpected_session)

    await GamingCommands(FakeBot()).on_raw_reaction_add(
        FakePayload(guild_id=None, member=FakeMember())
    )


async def test_raw_reaction_from_a_bot_is_ignored(monkeypatch):
    monkeypatch.setattr(gaming_commands, "get_db_session", _unexpected_session)

    await GamingCommands(FakeBot()).on_raw_reaction_add(FakePayload(member=FakeMember(bot=True)))


async def test_raw_reaction_in_an_unknown_channel_is_ignored(monkeypatch, sqlite_session_factory):
    async with sqlite_session_factory() as session:
        await create_session(
            session,
            guild_id=1,
            message_id=3,
            channel_id=2,
            creator_id=4,
            game="Valorant",
            party_size=5,
        )
        await session.commit()

    monkeypatch.setattr(
        gaming_commands, "get_db_session", _session_provider(sqlite_session_factory)
    )

    await GamingCommands(FakeBot(channel=None)).on_raw_reaction_add(
        FakePayload(guild_id=1, channel_id=2, message_id=3, user_id=99, member=FakeMember())
    )

    # The join is persisted before the message is edited, and the missing
    # channel must not raise.
    async with sqlite_session_factory() as session:
        lfg = await get_session(session, guild_id=1, message_id=3)
        assert await list_member_ids(session, lfg) == [4, 99]
