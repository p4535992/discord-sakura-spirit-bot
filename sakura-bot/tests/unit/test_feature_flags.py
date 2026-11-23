"""Feature flags must survive a new ORM session.

``Server.enabled_features`` is a plain JSON column: SQLAlchemy does not track an
in-place mutation, so the command has to reassign the whole mapping. The test
drives the real command callback against the in-memory SQLite schema.
"""

from sqlalchemy import select

import commands.admin_commands as admin_commands
from commands.admin_commands import AdminCommands
from models import Server


class FakeResponse:
    def __init__(self):
        self.messages = []

    def is_done(self):
        return bool(self.messages)

    async def send_message(self, content=None, **kwargs):
        self.messages.append({"content": content, **kwargs})


class FakeGuild:
    id = 987654321098765432
    name = "Sakura Test Guild"


class FakeInteraction:
    def __init__(self, guild):
        self.guild = guild
        self.response = FakeResponse()


class _SessionContext:
    """Minimal async context manager matching ``get_db_session``."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info):
        return False


async def test_a_toggled_feature_survives_a_new_session(sqlite_session, monkeypatch):
    monkeypatch.setattr(admin_commands, "get_db_session", lambda: _SessionContext(sqlite_session))
    interaction = FakeInteraction(FakeGuild())

    await AdminCommands.toggle_feature.callback(AdminCommands(None), interaction, "weather", False)

    assert interaction.response.messages, "the command must answer the interaction"

    # Force a reload from the database instead of the identity map.
    sqlite_session.expire_all()
    server = (await sqlite_session.execute(select(Server))).scalar_one()
    assert server.enabled_features["weather"] is False
    assert server.enabled_features["spirits"] is True


async def test_an_unknown_feature_is_rejected_without_touching_the_database(monkeypatch):
    def _unexpected_session():
        raise AssertionError("the database must not be opened for an invalid feature")

    monkeypatch.setattr(admin_commands, "get_db_session", _unexpected_session)
    interaction = FakeInteraction(FakeGuild())

    await AdminCommands.toggle_feature.callback(AdminCommands(None), interaction, "economy", True)

    message = interaction.response.messages[0]
    assert message["ephemeral"] is True
    assert "Invalid feature" in message["content"]
