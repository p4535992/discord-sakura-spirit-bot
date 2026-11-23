"""PostgreSQL integration test for user creation.

The fixture drops and recreates the whole schema, so it only runs against the
throwaway cluster declared through ``SAKURA_POSTGRES_TEST_DATABASE_URL``. The
URL is validated by ``assert_safe_test_database_url`` before any engine is
created and the marker row is verified before the first DDL statement.

Two outcomes are kept distinct: without the variable the test is skipped (a
normal offline run), while a declared but unusable database fails the run
instead of pretending success.
"""

import os

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.services import UserService
from models.base import Base
from models import User, UserStats
from tests.support.database_guard import (
    UnsafeTestDatabaseError,
    assert_safe_test_database_url,
    assert_test_database_marker,
)

pytestmark = pytest.mark.integration

TEST_DATABASE_URL = os.environ.get("SAKURA_POSTGRES_TEST_DATABASE_URL")


@pytest.fixture
async def postgres_session():
    if not TEST_DATABASE_URL:
        pytest.skip("SAKURA_POSTGRES_TEST_DATABASE_URL is not set")

    # Runs before create_async_engine and before any DDL: a URL that is not a
    # throwaway test database must fail here, never drop real tables.
    assert_safe_test_database_url(TEST_DATABASE_URL)

    engine = create_async_engine(TEST_DATABASE_URL)
    try:
        # The marker row proves the cluster was started from
        # docker-compose.test.yml; it is checked before any DDL.
        async with engine.connect() as connection:
            await assert_test_database_marker(connection)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    except UnsafeTestDatabaseError:
        await engine.dispose()
        raise
    except Exception as exc:  # pragma: no cover - depends on the environment
        await engine.dispose()
        pytest.fail(f"PostgreSQL test database is not usable: {exc}")

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


async def test_user_and_stats_are_persisted(postgres_session):
    user = await UserService.get_or_create_user(
        postgres_session, 555555555555555555, "Postgres"
    )

    assert user.id is not None
    stats = (
        await postgres_session.execute(
            select(UserStats).where(UserStats.user_id == user.id)
        )
    ).scalar_one()
    assert stats.user_id == user.id

    total = (
        await postgres_session.execute(select(func.count()).select_from(User))
    ).scalar_one()
    assert total == 1
