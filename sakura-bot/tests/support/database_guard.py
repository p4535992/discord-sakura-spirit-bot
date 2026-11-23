"""Safety guard for the destructive PostgreSQL integration tests.

The integration fixture drops and recreates every table, so the target must be
provably the throwaway cluster declared in ``docker-compose.test.yml``. The
guard is fail-closed: only the exact host/port/database tuples below are
accepted, no environment variable can widen them, and once connected the
database must also carry the marker row that only the test stack creates.

Error messages never contain the password.
"""

import os
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

APPLICATION_DATABASE_URL_ENV = "SAKURA_BOT_DATABASE_URL"
TEST_DATABASE_URL_ENV = "SAKURA_POSTGRES_TEST_DATABASE_URL"

# Exact targets of the throwaway stack: loopback from the host, service name
# from inside the test network. Port 5432 is deliberately absent on loopback,
# so the application cluster can never be reached by mistake.
APPROVED_TEST_TARGETS = frozenset(
    {
        ("127.0.0.1", 55432, "sakura_test"),
        ("localhost", 55432, "sakura_test"),
        ("sakura-postgres-test", 5432, "sakura_test"),
    }
)
# The dedicated user of the test stack, not the application one.
APPROVED_TEST_USERS = frozenset({"sakura_test"})
# Cluster maintenance databases that must never be dropped.
FORBIDDEN_DATABASE_NAMES = frozenset({"postgres", "template0", "template1"})
# The database name must carry this token: a suffix-only check is not enough.
TEST_DATABASE_TOKEN = "test"
DEFAULT_POSTGRESQL_PORT = 5432

# Created by ``sakura-postgres/test-init/01-test-marker.sql``, which only the
# test stack mounts. Its presence proves the cluster was started for the tests.
MARKER_TABLE = "sakura_test_marker"
MARKER_VALUE = "sakura-destructive-test-database"


class UnsafeTestDatabaseError(RuntimeError):
    """Raised when a URL is not provably a throwaway test database."""


def _approved_targets() -> str:
    """Render the approved targets for diagnostics."""
    return ", ".join(
        f"{host}:{port}/{database}" for host, port, database in sorted(APPROVED_TEST_TARGETS)
    )


def _describe(url: URL) -> str:
    """Render a URL for diagnostics without its password."""
    return url.render_as_string(hide_password=True)


def _parse(url: str) -> URL:
    """Parse a URL without echoing the raw string, which may hold a password."""
    try:
        return make_url(url)
    except ArgumentError:
        raise UnsafeTestDatabaseError(
            "Unparsable test database URL; expected "
            "postgresql+asyncpg://user:password@host:port/database"
        ) from None


def _application_database() -> Optional[URL]:
    """Return the application database URL when the environment declares one."""
    configured = os.environ.get(APPLICATION_DATABASE_URL_ENV)
    if not configured:
        return None
    try:
        return make_url(configured)
    except ArgumentError:
        return None


def assert_safe_test_database_url(url: Optional[str]) -> None:
    """Fail unless ``url`` is a throwaway PostgreSQL test database.

    Raises:
        UnsafeTestDatabaseError: the URL is empty, is not PostgreSQL with the
            asyncpg driver, targets a maintenance database, does not carry the
            ``test`` token, is not one of the approved test targets, uses a
            different user, or resolves to the application database.
    """
    if not url:
        raise UnsafeTestDatabaseError(
            f"{TEST_DATABASE_URL_ENV} is empty: the destructive integration test "
            "needs an explicit throwaway database."
        )

    parsed = _parse(url)

    backend = parsed.get_backend_name()
    if backend != "postgresql":
        raise UnsafeTestDatabaseError(
            f"Test database must use PostgreSQL, got {backend}: {_describe(parsed)}"
        )

    driver = parsed.get_driver_name()
    if driver != "asyncpg":
        raise UnsafeTestDatabaseError(
            f"Test database must use the asyncpg driver, got {driver}: {_describe(parsed)}"
        )

    host = (parsed.host or "").lower()
    port = parsed.port or DEFAULT_POSTGRESQL_PORT
    database = (parsed.database or "").lower()
    user = (parsed.username or "").lower()

    if not database:
        raise UnsafeTestDatabaseError(f"Test database name is missing: {_describe(parsed)}")
    if database in FORBIDDEN_DATABASE_NAMES:
        raise UnsafeTestDatabaseError(
            f"Test database {database} is a cluster maintenance database: {_describe(parsed)}"
        )
    if TEST_DATABASE_TOKEN not in database:
        raise UnsafeTestDatabaseError(
            f"Test database name {database} must contain '{TEST_DATABASE_TOKEN}': "
            f"{_describe(parsed)}"
        )

    if (host, port, database) not in APPROVED_TEST_TARGETS:
        raise UnsafeTestDatabaseError(
            "Test database target is not the throwaway cluster declared in "
            f"docker-compose.test.yml (approved: {_approved_targets()}): "
            f"{_describe(parsed)}"
        )
    if user not in APPROVED_TEST_USERS:
        raise UnsafeTestDatabaseError(
            f"Test database user {user or '<empty>'} is not the dedicated test user "
            f"({', '.join(sorted(APPROVED_TEST_USERS))}): {_describe(parsed)}"
        )

    application = _application_database()
    if application is not None:
        same_target = (
            (application.host or "").lower() == host
            and (application.port or DEFAULT_POSTGRESQL_PORT)
            == (parsed.port or DEFAULT_POSTGRESQL_PORT)
            and (application.database or "").lower() == database
        )
        if same_target:
            raise UnsafeTestDatabaseError(
                "Test database resolves to the application database configured in "
                f"{APPLICATION_DATABASE_URL_ENV}: {_describe(parsed)}"
            )


async def assert_test_database_marker(connection) -> None:
    """Fail unless the connected database carries the test-stack marker row.

    ``connection`` is an ``AsyncConnection``. The check is a single ``SELECT``,
    so it runs before ``drop_all`` and cannot modify anything. A cluster that
    was not started from ``docker-compose.test.yml`` has no marker table, which
    is exactly the case that must never be dropped.

    Raises:
        UnsafeTestDatabaseError: the marker table is missing or its row does not
            carry the expected value.
    """
    try:
        result = await connection.execute(
            text(f"SELECT marker FROM {MARKER_TABLE} WHERE marker = :marker"),
            {"marker": MARKER_VALUE},
        )
    except Exception as exc:
        raise UnsafeTestDatabaseError(
            f"Test database has no '{MARKER_TABLE}' table; start the throwaway "
            "cluster with 'docker compose -f docker-compose.test.yml up -d --wait' "
            f"before running the destructive tests ({type(exc).__name__})."
        ) from None

    if result.scalar_one_or_none() != MARKER_VALUE:
        raise UnsafeTestDatabaseError(
            f"Test database does not contain the '{MARKER_VALUE}' marker row; it is "
            "not the throwaway cluster declared in docker-compose.test.yml."
        )
