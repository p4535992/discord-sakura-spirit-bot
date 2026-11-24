"""
PostgreSQL persistence for LFG sessions and ritual cooldowns.

Both were Redis keys with a TTL. They are game state, not cache: a restart must
not lose a group or reset a cooldown, so they live in PostgreSQL and the TTL
becomes an ``expires_at`` column. The in-process cache of ``core.cache`` only
holds rebuildable read-through data.

Concurrency rules:

- the join locks the session row with ``SELECT ... FOR UPDATE`` (a no-op on
  SQLite, a real row lock on PostgreSQL) and the unique constraint on
  ``(session_id, discord_user_id)`` is the second guard;
- the cooldown is acquired with a conditional ``UPDATE`` and, only when no
  expired row exists, with an ``INSERT`` inside a SAVEPOINT, so a concurrent
  loser gets an ``IntegrityError`` that rolls back just that savepoint.

No network call happens inside these functions: the caller commits first and
updates the Discord message afterwards.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models.gaming import (
    STATUS_EXPIRED,
    STATUS_FULL,
    STATUS_OPEN,
    LfgMember,
    LfgSession,
    RitualCooldown,
    utcnow,
)

logger = logging.getLogger(__name__)

# Same durations as the former Redis keys: LFG 3600 s, ritual cooldown 1800 s.
LFG_TTL_SECONDS = 3600
RITUAL_COOLDOWN_SECONDS = 1800

# Outcomes of ``join_session``; the caller decides what to tell the user.
JOIN_OK = "joined"
JOIN_DUPLICATE = "duplicate"
JOIN_FULL = "full"
JOIN_EXPIRED = "expired"
JOIN_MISSING = "missing"


def _as_utc(value: datetime) -> datetime:
    """Return ``value`` as an aware UTC datetime.

    PostgreSQL returns an aware value because the column is ``timezone=True``;
    SQLite drops the offset, so a naive value is interpreted as UTC instead of
    being compared with an aware one (which would raise ``TypeError``).
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


# --- LFG sessions ------------------------------------------------------------


async def create_session(
    session: AsyncSession,
    *,
    guild_id: int,
    message_id: int,
    channel_id: int,
    creator_id: int,
    game: str,
    party_size: int,
    ttl_seconds: int = LFG_TTL_SECONDS,
) -> LfgSession:
    """Store a new LFG session and register the creator as first member."""
    now = utcnow()
    lfg = LfgSession(
        guild_id=guild_id,
        message_id=message_id,
        channel_id=channel_id,
        creator_id=creator_id,
        game=game,
        party_size=party_size,
        status=STATUS_OPEN,
        created_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )
    session.add(lfg)
    await session.flush()
    session.add(LfgMember(session_id=lfg.id, discord_user_id=creator_id, joined_at=now))
    await session.flush()
    return lfg


async def get_session(
    session: AsyncSession,
    *,
    guild_id: int,
    message_id: int,
    for_update: bool = False,
) -> Optional[LfgSession]:
    """Return the session bound to ``message_id``, optionally locking the row."""
    statement = select(LfgSession).where(
        LfgSession.guild_id == guild_id,
        LfgSession.message_id == message_id,
    )
    if for_update:
        statement = statement.with_for_update()
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def list_member_ids(session: AsyncSession, lfg: LfgSession) -> list[int]:
    """Return the member ids of ``lfg`` in join order.

    The relationship is not lazy-loaded: an async session cannot emit implicit
    IO, so the rows are queried explicitly.
    """
    result = await session.execute(
        select(LfgMember.discord_user_id)
        .where(LfgMember.session_id == lfg.id)
        .order_by(LfgMember.id)
    )
    return [row[0] for row in result.all()]


async def join_session(
    session: AsyncSession,
    *,
    guild_id: int,
    message_id: int,
    discord_user_id: int,
    ttl_seconds: int = LFG_TTL_SECONDS,
) -> tuple[str, Optional[LfgSession], list[int]]:
    """Add ``discord_user_id`` to the session, atomically.

    Returns ``(outcome, session, member_ids)`` where ``outcome`` is one of the
    ``JOIN_*`` constants and ``member_ids`` is the group after the call (the
    caller rebuilds the embed from it, without a second query).
    """
    lfg = await get_session(session, guild_id=guild_id, message_id=message_id, for_update=True)
    if lfg is None:
        return JOIN_MISSING, None, []

    now = utcnow()
    member_ids = await list_member_ids(session, lfg)

    if lfg.status == STATUS_EXPIRED or _as_utc(lfg.expires_at) <= now:
        return JOIN_EXPIRED, lfg, member_ids
    if discord_user_id in member_ids:
        return JOIN_DUPLICATE, lfg, member_ids
    if len(member_ids) >= lfg.party_size:
        return JOIN_FULL, lfg, member_ids

    try:
        # SAVEPOINT: a duplicate insert from a concurrent reaction rolls back
        # only this statement, not the caller's transaction.
        async with session.begin_nested():
            session.add(
                LfgMember(session_id=lfg.id, discord_user_id=discord_user_id, joined_at=now)
            )
    except IntegrityError:
        logger.info(
            "LFG join ignored: user %s is already in session %s", discord_user_id, lfg.id
        )
        return JOIN_DUPLICATE, lfg, member_ids

    member_ids.append(discord_user_id)
    # Same semantic as the former Redis TTL: an accepted join renews the window.
    lfg.expires_at = now + timedelta(seconds=ttl_seconds)
    if len(member_ids) >= lfg.party_size:
        lfg.status = STATUS_FULL
    await session.flush()
    return JOIN_OK, lfg, member_ids


async def expire_session(session: AsyncSession, lfg: LfgSession) -> None:
    """Mark ``lfg`` as expired without deleting its rows."""
    lfg.status = STATUS_EXPIRED
    await session.flush()


async def purge_expired_sessions(session: AsyncSession, *, now: Optional[datetime] = None) -> int:
    """Delete the sessions whose window is over and return how many were removed.

    The members are deleted explicitly instead of relying only on the
    ``ON DELETE CASCADE``: SQLite does not enforce foreign keys unless the
    pragma is enabled, so the statement must be portable for the test suite.
    """
    reference = now or utcnow()
    expired_ids = (
        await session.execute(select(LfgSession.id).where(LfgSession.expires_at <= reference))
    ).scalars().all()
    if not expired_ids:
        return 0

    await session.execute(
        delete(LfgMember)
        .where(LfgMember.session_id.in_(expired_ids))
        .execution_options(synchronize_session=False)
    )
    result = await session.execute(
        delete(LfgSession)
        .where(LfgSession.id.in_(expired_ids))
        .execution_options(synchronize_session=False)
    )
    return result.rowcount or 0


# --- Ritual cooldowns --------------------------------------------------------


async def acquire_ritual_cooldown(
    session: AsyncSession,
    discord_user_id: int,
    *,
    cooldown_seconds: int = RITUAL_COOLDOWN_SECONDS,
) -> bool:
    """Try to start the cooldown of ``discord_user_id``.

    Returns ``True`` only for the caller that actually acquired it: an active
    cooldown returns ``False`` and must be reported to the user. The cooldown is
    global per user, as the former ``ritual_cooldown:<user_id>`` key was.
    """
    now = utcnow()
    expires_at = now + timedelta(seconds=cooldown_seconds)

    # Expired row (or no row): the conditional UPDATE is atomic, so exactly one
    # concurrent caller can win it. ``synchronize_session=False``: only the row
    # count matters, and the ORM cannot compare an aware bound value with a
    # naive value loaded from a backend that drops the offset.
    result = await session.execute(
        update(RitualCooldown)
        .where(
            RitualCooldown.discord_user_id == discord_user_id,
            RitualCooldown.expires_at <= now,
        )
        .values(expires_at=expires_at, updated_at=now)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount:
        return True

    try:
        async with session.begin_nested():
            session.add(
                RitualCooldown(
                    discord_user_id=discord_user_id,
                    expires_at=expires_at,
                    created_at=now,
                    updated_at=now,
                )
            )
    except IntegrityError:
        # Another request inserted the row first: its cooldown is active.
        return False
    return True


async def get_ritual_cooldown(
    session: AsyncSession, discord_user_id: int
) -> Optional[RitualCooldown]:
    """Return the stored cooldown row, expired or not."""
    result = await session.execute(
        select(RitualCooldown).where(RitualCooldown.discord_user_id == discord_user_id)
    )
    return result.scalar_one_or_none()


async def release_ritual_cooldown(session: AsyncSession, discord_user_id: int) -> None:
    """Remove the cooldown of ``discord_user_id`` (used by tests and support)."""
    await session.execute(
        delete(RitualCooldown)
        .where(RitualCooldown.discord_user_id == discord_user_id)
        .execution_options(synchronize_session=False)
    )

