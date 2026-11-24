"""
Gaming state that must survive a restart.

LFG sessions and ritual cooldowns used to live in Redis with a TTL. They are
game state, not a cache: a restart must not lose a group or reset a cooldown, so
they are stored in PostgreSQL and read through ``core.lfg_repository``. Only the
rebuildable read-through data stays in ``core.cache``.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .base import Base

# Session states. ``expired`` is set lazily when a reaction reaches a session
# whose ``expires_at`` already passed; the row is kept until a purge runs.
STATUS_OPEN = "open"
STATUS_FULL = "full"
STATUS_EXPIRED = "expired"


def utcnow() -> datetime:
    """Return the current time as an aware UTC datetime.

    Every timestamp of this module is timezone aware: the columns are declared
    with ``timezone=True`` and the values are compared after normalisation, so a
    backend that drops the offset (SQLite in the unit suite) cannot shift them.
    """
    return datetime.now(timezone.utc)


class LfgSession(Base):
    """A "looking for group" post bound to one Discord message."""

    __tablename__ = "lfg_sessions"
    __table_args__ = (
        # One session per message: a duplicate insert is a programming error, not
        # a second group on the same embed.
        UniqueConstraint("guild_id", "message_id", name="uq_lfg_sessions_message"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    message_id = Column(BigInteger, nullable=False, index=True)
    channel_id = Column(BigInteger, nullable=False)
    creator_id = Column(BigInteger, nullable=False)
    game = Column(String(200), nullable=False)
    party_size = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default=STATUS_OPEN)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    # Renewed by every accepted join, exactly like the former Redis TTL.
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

    members = relationship(
        "LfgMember",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="LfgMember.id",
    )

    def __repr__(self):
        return (
            f"<LfgSession(guild_id={self.guild_id}, message_id={self.message_id}, "
            f"game={self.game}, status={self.status})>"
        )


class LfgMember(Base):
    """A participant of an LFG session; the creator is the first row."""

    __tablename__ = "lfg_members"
    __table_args__ = (
        # The database, not the application, guarantees one row per user and
        # session: two simultaneous reactions cannot both insert.
        UniqueConstraint("session_id", "discord_user_id", name="uq_lfg_members_user"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        Integer, ForeignKey("lfg_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    discord_user_id = Column(BigInteger, nullable=False, index=True)
    joined_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    session = relationship("LfgSession", back_populates="members")

    def __repr__(self):
        return f"<LfgMember(session_id={self.session_id}, user={self.discord_user_id})>"


class RitualCooldown(Base):
    """Per-user ritual cooldown, global across guilds as before.

    The former key was ``ritual_cooldown:<user_id>`` with a 1800 s TTL, so the
    cooldown never depended on the guild; the unique column keeps that semantic.
    """

    __tablename__ = "ritual_cooldowns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    discord_user_id = Column(BigInteger, nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    def __repr__(self):
        return f"<RitualCooldown(user={self.discord_user_id}, expires_at={self.expires_at})>"
