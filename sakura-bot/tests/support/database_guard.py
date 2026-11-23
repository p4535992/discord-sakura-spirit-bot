"""Safety guard for the destructive PostgreSQL integration tests.

The integration fixture drops and recreates every table, so the target URL must
be provably a throwaway test database. The guard runs before any engine is
created: a misconfigured URL fails with an explicit error instead of touching
real data. Error messages never contain the password.
"""

import os
from typing import Optional

from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

APPLICATION_DATABASE_URL_ENV = "SAKURA_BOT_DATABASE_URL"
TEST_DATABASE_URL_ENV = "SAKURA_POSTGRES_TEST_DATABASE_URL"
ALLOWED_HOSTS_ENV = "SAKURA_TEST_DB_ALLOWED_HOSTS"

# Hosts reachable from a developer workstation or from the test compose stack.
DEFAULT_ALLOWED_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "sakura-postgres-test"})
# Cluster maintenance databases that must never be dropped.
FORBIDDEN_DATABASE_NAMES = frozenset({"postgres", "template0", "template1"})
# The database name must carry this token: a suffix-only check is not enough.
TEST_DATABASE_TOKEN = "test"
DEFAULT_POSTGRESQL_PORT = 5432


class UnsafeTestDatabaseError(RuntimeError):
    """Raised when a URL is not provably a throwaway test database."""


def _allowed_hosts() -> frozenset[str]:
    """Return the default hosts plus the ones declared in the environment."""
    declared = os.environ.get(ALLOWED_HOSTS_ENV, "")
    extra = {host.strip().lower() for host in declared.split(",") if host.strip()}
    return DEFAULT_ALLOWED_HOSTS | extra


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
            asyncpg driver, points at an unknown host, targets a maintenance
            database, does not carry the ``test`` token, or resolves to the
            application database.
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
    if host not in _allowed_hosts():
        raise UnsafeTestDatabaseError(
            f"Test database host {host or '<empty>'} is not allowed; declare it in "
            f"{ALLOWED_HOSTS_ENV} only for a dedicated test server: {_describe(parsed)}"
        )

    database = (parsed.database or "").lower()
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
