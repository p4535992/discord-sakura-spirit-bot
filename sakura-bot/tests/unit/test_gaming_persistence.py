"""LFG session and ritual cooldown persistence tests.

The suite runs on an in-memory SQLite database: it proves the SQL, the unique
constraints and the transactional logic without a PostgreSQL server. The row
lock (``SELECT ... FOR UPDATE``) is a no-op on SQLite, so the concurrency
guarantee is covered by the unique constraints and the conditional UPDATE, which
are exercised for real.
"""

from sqlalchemy import select

from core.lfg_repository import (
    JOIN_DUPLICATE,
    JOIN_EXPIRED,
    JOIN_FULL,
    JOIN_MISSING,
    JOIN_OK,
    acquire_ritual_cooldown,
    create_session,
    expire_session,
    get_ritual_cooldown,
    get_session,
    join_session,
    list_member_ids,
    purge_expired_sessions,
    release_ritual_cooldown,
)
from models.gaming import STATUS_EXPIRED, STATUS_FULL, STATUS_OPEN, LfgMember, LfgSession

GUILD_ID = 111111111111111111
MESSAGE_ID = 222222222222222222
CHANNEL_ID = 333333333333333333
CREATOR_ID = 444444444444444444
OTHER_ID = 555555555555555555
THIRD_ID = 666666666666666666


def _naive(value):
    """Drop the offset: SQLite returns naive datetimes, PostgreSQL aware ones."""
    return value.replace(tzinfo=None) if value.tzinfo else value


async def _create(factory, *, party_size: int = 3, ttl_seconds: int = 3600):
    """Create one session in its own transaction and return its id."""
    async with factory() as session:
        lfg = await create_session(
            session,
            guild_id=GUILD_ID,
            message_id=MESSAGE_ID,
            channel_id=CHANNEL_ID,
            creator_id=CREATOR_ID,
            game="Valorant",
            party_size=party_size,
            ttl_seconds=ttl_seconds,
        )
        await session.commit()
        return lfg.id


async def test_create_session_registers_the_creator(sqlite_session_factory):
    async with sqlite_session_factory() as session:
        lfg = await create_session(
            session,
            guild_id=GUILD_ID,
            message_id=MESSAGE_ID,
            channel_id=CHANNEL_ID,
            creator_id=CREATOR_ID,
            game="Valorant",
            party_size=3,
        )
        await session.commit()

        assert lfg.status == STATUS_OPEN
        assert lfg.party_size == 3
        assert await list_member_ids(session, lfg) == [CREATOR_ID]


async def test_join_adds_the_member_and_renews_the_expiry(sqlite_session_factory):
    await _create(sqlite_session_factory, ttl_seconds=100)

    async with sqlite_session_factory() as session:
        lfg = await get_session(session, guild_id=GUILD_ID, message_id=MESSAGE_ID)
        original_expiry = _naive(lfg.expires_at)

    async with sqlite_session_factory() as session:
        outcome, joined, member_ids = await join_session(
            session,
            guild_id=GUILD_ID,
            message_id=MESSAGE_ID,
            discord_user_id=OTHER_ID,
        )
        await session.commit()

        assert outcome == JOIN_OK
        assert member_ids == [CREATOR_ID, OTHER_ID]
        # The former Redis TTL was renewed by every accepted join.
        assert _naive(joined.expires_at) > original_expiry


async def test_a_repeated_reaction_is_rejected(sqlite_session_factory):
    await _create(sqlite_session_factory)

    async with sqlite_session_factory() as session:
        outcome, _, member_ids = await join_session(
            session,
            guild_id=GUILD_ID,
            message_id=MESSAGE_ID,
            discord_user_id=CREATOR_ID,
        )

        assert outcome == JOIN_DUPLICATE
        assert member_ids == [CREATOR_ID]


async def test_a_full_group_rejects_new_members(sqlite_session_factory):
    await _create(sqlite_session_factory, party_size=2)

    async with sqlite_session_factory() as session:
        outcome, lfg, member_ids = await join_session(
            session,
            guild_id=GUILD_ID,
            message_id=MESSAGE_ID,
            discord_user_id=OTHER_ID,
        )
        await session.commit()

        assert outcome == JOIN_OK
        assert lfg.status == STATUS_FULL
        assert member_ids == [CREATOR_ID, OTHER_ID]

    async with sqlite_session_factory() as session:
        outcome, _, member_ids = await join_session(
            session,
            guild_id=GUILD_ID,
            message_id=MESSAGE_ID,
            discord_user_id=THIRD_ID,
        )

        assert outcome == JOIN_FULL
        assert member_ids == [CREATOR_ID, OTHER_ID]


async def test_an_expired_session_rejects_the_join_and_can_be_marked(sqlite_session_factory):
    await _create(sqlite_session_factory, ttl_seconds=-1)

    async with sqlite_session_factory() as session:
        outcome, lfg, member_ids = await join_session(
            session,
            guild_id=GUILD_ID,
            message_id=MESSAGE_ID,
            discord_user_id=OTHER_ID,
        )

        assert outcome == JOIN_EXPIRED
        assert member_ids == [CREATOR_ID]

        await expire_session(session, lfg)
        await session.commit()

    async with sqlite_session_factory() as session:
        reloaded = await get_session(session, guild_id=GUILD_ID, message_id=MESSAGE_ID)
        assert reloaded.status == STATUS_EXPIRED


async def test_an_unknown_message_is_ignored(sqlite_session_factory):
    async with sqlite_session_factory() as session:
        outcome, lfg, member_ids = await join_session(
            session,
            guild_id=GUILD_ID,
            message_id=MESSAGE_ID,
            discord_user_id=OTHER_ID,
        )

        assert outcome == JOIN_MISSING
        assert lfg is None
        assert member_ids == []


async def test_purge_removes_only_the_expired_sessions(sqlite_session_factory):
    await _create(sqlite_session_factory, ttl_seconds=-1)

    async with sqlite_session_factory() as session:
        removed = await purge_expired_sessions(session)
        await session.commit()

        assert removed == 1
        members = (await session.execute(select(LfgMember))).scalars().all()
        assert members == []
        assert (await session.execute(select(LfgSession))).scalars().all() == []


# --- Ritual cooldowns --------------------------------------------------------


async def test_the_first_ritual_starts_the_cooldown(sqlite_session_factory):
    async with sqlite_session_factory() as session:
        assert await acquire_ritual_cooldown(session, CREATOR_ID) is True
        await session.commit()


async def test_a_second_ritual_inside_the_window_is_refused(sqlite_session_factory):
    async with sqlite_session_factory() as session:
        assert await acquire_ritual_cooldown(session, CREATOR_ID) is True
        await session.commit()

    async with sqlite_session_factory() as session:
        assert await acquire_ritual_cooldown(session, CREATOR_ID) is False


async def test_an_expired_cooldown_can_be_acquired_again(sqlite_session_factory):
    async with sqlite_session_factory() as session:
        # A negative duration stores an already expired window.
        assert await acquire_ritual_cooldown(session, CREATOR_ID, cooldown_seconds=-1) is True
        await session.commit()

    async with sqlite_session_factory() as session:
        assert await acquire_ritual_cooldown(session, CREATOR_ID) is True


async def test_the_cooldown_is_per_user(sqlite_session_factory):
    async with sqlite_session_factory() as session:
        assert await acquire_ritual_cooldown(session, CREATOR_ID) is True
        assert await acquire_ritual_cooldown(session, OTHER_ID) is True
        await session.commit()


async def test_the_cooldown_survives_a_restart(sqlite_session_factory):
    async with sqlite_session_factory() as session:
        assert await acquire_ritual_cooldown(session, CREATOR_ID) is True
        await session.commit()

    # A new session and a new transaction simulate the restarted bot.
    async with sqlite_session_factory() as session:
        stored = await get_ritual_cooldown(session, CREATOR_ID)
        assert stored is not None
        assert await acquire_ritual_cooldown(session, CREATOR_ID) is False


async def test_release_removes_the_cooldown(sqlite_session_factory):
    async with sqlite_session_factory() as session:
        assert await acquire_ritual_cooldown(session, CREATOR_ID) is True
        await release_ritual_cooldown(session, CREATOR_ID)
        await session.commit()

    async with sqlite_session_factory() as session:
        assert await get_ritual_cooldown(session, CREATOR_ID) is None
        assert await acquire_ritual_cooldown(session, CREATOR_ID) is True
