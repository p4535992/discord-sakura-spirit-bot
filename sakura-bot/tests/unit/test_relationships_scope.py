"""``Relationship.server_id`` must be filtered with the internal ``Server.id``.

The Discord guild id and the database primary key are different values, so a
query comparing the foreign key with ``interaction.guild.id`` returns the wrong
rows. The test keeps the two values distinct on purpose.
"""

import commands.social_commands as social_commands
from commands.social_commands import SocialCommands
from models import Relationship, Server

GUILD_ID = 987654321098765432
OTHER_GUILD_ID = 123456789012345678
ME = 555555555555555555
OTHER = 444444444444444444


class FakeResponse:
    def __init__(self):
        self.messages = []

    def is_done(self):
        return bool(self.messages)

    async def send_message(self, content=None, **kwargs):
        self.messages.append({"content": content, **kwargs})


class FakeGuild:
    def __init__(self, guild_id, name):
        self.id = guild_id
        self.name = name


class FakeInteraction:
    def __init__(self, guild):
        self.guild = guild
        self.response = FakeResponse()
        self.user = type("FakeUser", (), {"id": ME, "name": "tester"})()


class FakeBot:
    async def fetch_user(self, user_id):
        return type("FakeUser", (), {"name": f"user-{user_id}"})()


class _SessionContext:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info):
        return False


async def test_relationships_are_filtered_by_the_internal_server_id(sqlite_session, monkeypatch):
    current = Server(discord_id=GUILD_ID, name="Current")
    other = Server(discord_id=OTHER_GUILD_ID, name="Other")
    sqlite_session.add_all([current, other])
    await sqlite_session.commit()

    # The whole point of the regression: the primary key is not the guild id.
    assert current.id != current.discord_id

    sqlite_session.add_all(
        [
            Relationship(server_id=current.id, user_id_1=ME, user_id_2=OTHER, warmth_score=10.0),
            Relationship(server_id=other.id, user_id_1=ME, user_id_2=OTHER, warmth_score=99.0),
        ]
    )
    await sqlite_session.commit()

    monkeypatch.setattr(social_commands, "get_db_session", lambda: _SessionContext(sqlite_session))
    interaction = FakeInteraction(FakeGuild(GUILD_ID, "Current"))

    await SocialCommands.relationships.callback(SocialCommands(FakeBot()), interaction)

    embed = interaction.response.messages[0]["embed"]
    assert len(embed.fields) == 1, "the other guild must not leak into the result"
    assert f"user-{OTHER}" in embed.fields[0].name
    assert "10.0" in embed.fields[0].value
