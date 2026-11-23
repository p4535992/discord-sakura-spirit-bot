"""Shared test configuration.

``core.config`` instantiates ``Settings`` at import time, so the environment
must be prepared before any project module is imported.
``SAKURA_BOT_DATABASE_URL`` is always overridden: tests must never reach a real
database by accident.
"""
import os

# Dedicated test database; set SAKURA_POSTGRES_TEST_DATABASE_URL to point at a
# throwaway PostgreSQL instance (for example the compose ``sakura-postgres``
# service).
TEST_DATABASE_URL = os.environ.get(
    "SAKURA_POSTGRES_TEST_DATABASE_URL",
    "postgresql+asyncpg://sakura:sakura@localhost:5432/sakura_test",
)

# Variables are set in their container-prefixed form, exactly as compose does.
# The legacy names are removed first so a value exported in the developer shell
# cannot take precedence over the test value.
_CANONICAL_NAMES = (
    "DATABASE_URL",
    "DISCORD_TOKEN",
    "DISCORD_CLIENT_ID",
    "REDIS_URL",
    "OPENAI_API_KEY",
    "ENVIRONMENT",
    "LOG_LEVEL",
    "LOG_FILE",
    "CACHE_REQUIRED",
    "HEALTH_SERVER_ENABLED",
    "STRICT_STARTUP",
    "BOT_PREFIX",
    "BOT_OWNER_ID",
)
for _name in _CANONICAL_NAMES:
    os.environ.pop(_name, None)

os.environ["SAKURA_BOT_DATABASE_URL"] = TEST_DATABASE_URL
os.environ["SAKURA_BOT_ENVIRONMENT"] = "test"
os.environ["SAKURA_BOT_LOG_LEVEL"] = "WARNING"
os.environ["SAKURA_BOT_LOG_FILE"] = "logs/test.log"
os.environ["SAKURA_BOT_CACHE_REQUIRED"] = "false"
os.environ["SAKURA_BOT_HEALTH_SERVER_ENABLED"] = "false"
os.environ["SAKURA_BOT_STRICT_STARTUP"] = "false"
os.environ.setdefault("SAKURA_BOT_DISCORD_TOKEN", "test-token")
os.environ.setdefault("SAKURA_BOT_DISCORD_CLIENT_ID", "123456789012345678")
os.environ.setdefault("SAKURA_BOT_REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("SAKURA_BOT_OPENAI_API_KEY", "test-openai-key")

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
