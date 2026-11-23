"""Unit tests for the destructive-test database guard.

No database is contacted: every case stops at URL validation, which is exactly
the point of the guard.
"""

import pytest

from tests.support.database_guard import (
    MARKER_TABLE,
    MARKER_VALUE,
    UnsafeTestDatabaseError,
    assert_safe_test_database_url,
    assert_test_database_marker,
)

SAFE_URL = "postgresql+asyncpg://sakura_test:sakura_test_pw@sakura-postgres-test:5432/sakura_test"
LOOPBACK_URL = "postgresql+asyncpg://sakura_test:sakura_test_pw@127.0.0.1:55432/sakura_test"


def test_accepts_a_dedicated_test_database():
    assert_safe_test_database_url(SAFE_URL)


def test_rejects_a_missing_url():
    with pytest.raises(UnsafeTestDatabaseError, match="is empty"):
        assert_safe_test_database_url(None)
    with pytest.raises(UnsafeTestDatabaseError, match="is empty"):
        assert_safe_test_database_url("")


def test_rejects_a_non_postgresql_backend():
    with pytest.raises(UnsafeTestDatabaseError, match="must use PostgreSQL"):
        assert_safe_test_database_url("sqlite+aiosqlite:///./sakura_test.db")


def test_rejects_a_missing_asyncpg_driver():
    with pytest.raises(UnsafeTestDatabaseError, match="asyncpg"):
        assert_safe_test_database_url(
            "postgresql://sakura_test:sakura_test_pw@sakura-postgres-test:5432/sakura_test"
        )


def test_accepts_the_loopback_test_target():
    assert_safe_test_database_url(LOOPBACK_URL)


def test_rejects_an_unexpected_host():
    with pytest.raises(UnsafeTestDatabaseError, match="not the throwaway cluster"):
        assert_safe_test_database_url(
            "postgresql+asyncpg://sakura_test:sakura_test_pw@db.example.com:5432/sakura_test"
        )


def test_rejects_a_test_like_database_on_the_application_port():
    """A ``test`` name on port 5432 is the application cluster, not the stack."""
    with pytest.raises(UnsafeTestDatabaseError, match="not the throwaway cluster"):
        assert_safe_test_database_url(
            "postgresql+asyncpg://sakura_test:sakura_test_pw@localhost:5432/sakura_test"
        )


def test_rejects_a_wrong_port():
    with pytest.raises(UnsafeTestDatabaseError, match="not the throwaway cluster"):
        assert_safe_test_database_url(
            "postgresql+asyncpg://sakura_test:sakura_test_pw@127.0.0.1:5433/sakura_test"
        )


def test_rejects_a_wrong_user():
    with pytest.raises(UnsafeTestDatabaseError, match="dedicated test user"):
        assert_safe_test_database_url(
            "postgresql+asyncpg://sakura:sakura_test_pw@127.0.0.1:55432/sakura_test"
        )


def test_environment_cannot_widen_the_allow_list(monkeypatch):
    """A destructive test must not be redirectable through configuration."""
    monkeypatch.setenv("SAKURA_TEST_DB_ALLOWED_HOSTS", "db.example.com")
    with pytest.raises(UnsafeTestDatabaseError, match="not the throwaway cluster"):
        assert_safe_test_database_url(
            "postgresql+asyncpg://sakura_test:sakura_test_pw@db.example.com:55432/sakura_test"
        )


def test_rejects_a_cluster_maintenance_database():
    with pytest.raises(UnsafeTestDatabaseError, match="maintenance database"):
        assert_safe_test_database_url(
            "postgresql+asyncpg://sakura_test:sakura_test_pw@sakura-postgres-test:5432/postgres"
        )


def test_rejects_a_database_without_the_test_token():
    with pytest.raises(UnsafeTestDatabaseError, match="must contain 'test'"):
        assert_safe_test_database_url(
            "postgresql+asyncpg://sakura_test:sakura_test_pw@sakura-postgres-test:5432/sakura_bot"
        )


def test_rejects_the_application_database(monkeypatch):
    monkeypatch.setenv("SAKURA_BOT_DATABASE_URL", SAFE_URL)
    with pytest.raises(UnsafeTestDatabaseError, match="application database"):
        assert_safe_test_database_url(SAFE_URL)


def test_rejects_the_application_database_with_an_implicit_port(monkeypatch):
    monkeypatch.setenv(
        "SAKURA_BOT_DATABASE_URL",
        "postgresql+asyncpg://sakura_test:sakura_test_pw@sakura-postgres-test/sakura_test",
    )
    with pytest.raises(UnsafeTestDatabaseError, match="application database"):
        assert_safe_test_database_url(SAFE_URL)


def test_error_message_never_contains_the_password():
    with pytest.raises(UnsafeTestDatabaseError) as error:
        assert_safe_test_database_url(
            "postgresql+asyncpg://sakura_test:super-secret-pw@db.example.com:5432/sakura_test"
        )
    assert "super-secret-pw" not in str(error.value)
    assert "***" in str(error.value)


class FakeResult:
    """Stand-in for ``CursorResult``: only the scalar accessor is used."""

    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class FakeConnection:
    """Stand-in for ``AsyncConnection``: records the executed statement."""

    def __init__(self, value=None, error=None):
        self._value = value
        self._error = error
        self.executed = []

    async def execute(self, statement, parameters=None):
        self.executed.append((str(statement), parameters))
        if self._error is not None:
            raise self._error
        return FakeResult(self._value)


async def test_marker_accepts_the_test_stack_database():
    connection = FakeConnection(value=MARKER_VALUE)

    await assert_test_database_marker(connection)

    statement, parameters = connection.executed[0]
    assert MARKER_TABLE in statement
    assert parameters == {"marker": MARKER_VALUE}


async def test_marker_rejects_a_database_without_the_marker_table():
    connection = FakeConnection(error=RuntimeError("relation does not exist"))

    with pytest.raises(UnsafeTestDatabaseError, match="has no"):
        await assert_test_database_marker(connection)


async def test_marker_rejects_a_database_with_a_different_marker():
    connection = FakeConnection(value="some-other-database")

    with pytest.raises(UnsafeTestDatabaseError, match="marker row"):
        await assert_test_database_marker(connection)


async def test_marker_error_does_not_echo_the_connection_details():
    connection = FakeConnection(
        error=RuntimeError("password authentication failed for user sakura_test")
    )

    with pytest.raises(UnsafeTestDatabaseError) as error:
        await assert_test_database_marker(connection)

    assert "password" not in str(error.value)
