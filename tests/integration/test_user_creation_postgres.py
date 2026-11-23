"""PostgreSQL integration test for user creation.

Skipped unless ``POSTGRES_TEST_DATABASE_URL`` points at a throwaway database.
The fixture drops and recreates the schema, so it must never target real data.
"""
import os

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.services import UserService
from models.base import Base
from models import User, UserStats

pytestmark = pytest.mark.integration

TEST_DATABASE_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")


@pytest.fixture
async def postgres_session():
    if not TEST_DATABASE_URL:
        pytest.skip("POSTGRES_TEST_DATABASE_URL is not set")

    engine = create_async_engine(TEST_DATABASE_URL)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:  # pragma: no cover - depends on the environment
        await engine.dispose()
        pytest.skip(f"PostgreSQL is not reachable: {exc}")

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
