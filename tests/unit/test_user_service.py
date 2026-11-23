"""Regression tests for user creation.

The user row must be flushed before the dependent ``user_stats`` row is built,
otherwise the non-nullable foreign key receives ``None``.
"""
from sqlalchemy import func, select

from core.services import UserService
from models import User, UserStats


async def test_get_or_create_user_creates_user_and_stats(sqlite_session):
    user = await UserService.get_or_create_user(sqlite_session, 123456789012345678, "Sakura")

    assert user.id is not None
    assert user.level == 1

    stats = (
        await sqlite_session.execute(
            select(UserStats).where(UserStats.user_id == user.id)
        )
    ).scalar_one()
    assert stats.user_id == user.id


async def test_get_or_create_user_is_idempotent(sqlite_session):
    first = await UserService.get_or_create_user(sqlite_session, 42, "Aoi")
    second = await UserService.get_or_create_user(sqlite_session, 42, "Aoi")

    assert first.id == second.id
    total = (
        await sqlite_session.execute(select(func.count()).select_from(User))
    ).scalar_one()
    assert total == 1


async def test_add_xp_levels_up(sqlite_session):
    user = await UserService.get_or_create_user(sqlite_session, 7, "Hana")
    leveled_up, new_level = await UserService.add_xp(sqlite_session, user, 1000)

    assert leveled_up is True
    assert new_level is not None
    assert new_level > 1
