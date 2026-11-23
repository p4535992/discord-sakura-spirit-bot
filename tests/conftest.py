"""Shared test configuration.

``core.config`` instantiates ``Settings`` at import time, so the environment
must be prepared before any project module is imported. ``DATABASE_URL`` is
always overridden: tests must never reach a real database by accident.
"""
import os

# Dedicated test database; set SAKURA_TEST_DATABASE_URL to point at a
# throwaway PostgreSQL instance (for example the compose ``postgres`` service).
TEST_DATABASE_URL = os.environ.get(
    "SAKURA_TEST_DATABASE_URL",
    "postgresql+asyncpg://sakura:sakura@localhost:5432/sakura_test",
)

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("DISCORD_TOKEN", "test-token")
os.environ.setdefault("DISCORD_CLIENT_ID", "123456789012345678")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("LOG_FILE", "logs/test.log")
os.environ.setdefault("CACHE_REQUIRED", "false")
os.environ.setdefault("HEALTH_SERVER_ENABLED", "false")
os.environ.setdefault("STRICT_STARTUP", "false")

import pytest  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import models  # noqa: E402,F401  # Registers every ORM class on Base.metadata.
from models.base import Base  # noqa: E402


@pytest.fixture
async def sqlite_session():
    """Provide a session bound to a fresh in-memory SQLite schema.

    SQLite is used only for fast ORM regression tests; PostgreSQL remains the
    integration target in ``tests/integration``.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()
