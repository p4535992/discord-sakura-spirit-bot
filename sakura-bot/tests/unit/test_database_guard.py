"""Unit tests for the destructive-test database guard.

No database is contacted: every case stops at URL validation, which is exactly
the point of the guard.
"""

import pytest

from tests.support.database_guard import (
    UnsafeTestDatabaseError,
    assert_safe_test_database_url,
)

SAFE_URL = "postgresql+asyncpg://sakura_test:sakura_test_pw@sakura-postgres-test:5432/sakura_test"


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


def test_rejects_an_unexpected_host():
    with pytest.raises(UnsafeTestDatabaseError, match="is not allowed"):
        assert_safe_test_database_url(
            "postgresql+asyncpg://sakura_test:sakura_test_pw@db.example.com:5432/sakura_test"
        )


def test_accepts_a_host_declared_in_the_environment(monkeypatch):
    monkeypatch.setenv("SAKURA_TEST_DB_ALLOWED_HOSTS", "db.example.com")
    assert_safe_test_database_url(
        "postgresql+asyncpg://sakura_test:sakura_test_pw@db.example.com:5432/sakura_test"
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
