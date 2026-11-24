"""
Per-channel RPG weather models (V4 engine)

The V4 engine is opt-in per channel and keeps three separate concerns:

* ``WeatherChannelConfig`` is the operator's choice: preset, timezone, ranges
  overrides, posting schedule and retention;
* the ``*Snapshot`` tables are generated data, immutable per day and per slot,
  reproducible from their stored seed;
* ``WeatherEventTemplate``/``WeatherEventOccurrence`` and ``WeatherMediaAsset``
  are the narrative layer, while ``WeatherAuditLog`` records every operator
  action.

These tables are additive: they do not alter ``weather_history``, which belongs
to the legacy Sakura weather and stays untouched.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, BigInteger, DateTime, Float, JSON, ForeignKey,
    Boolean, Text, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from .base import Base


class WeatherClimatePreset(Base):
    """A named climate preset available to the channels of a server."""
    __tablename__ = "weather_climate_preset"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(64), nullable=False, unique=True, index=True)
    display_name = Column(String(128), nullable=False)
    family = Column(String(64), nullable=False)
    source = Column(String(64), nullable=False)  # workbook, project, custom
    hemisphere = Column(String(16), default="north")
    version = Column(Integer, default=1, nullable=False)

    # Twelve operational months, as produced by the profile builder.
    months_json = Column(JSON, nullable=False, default=list)
    # Provenance per field: excel_static, project_default, admin_override...
    field_provenance_json = Column(JSON, nullable=False, default=dict)

    is_builtin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<WeatherClimatePreset(slug={self.slug}, version={self.version})>"


class WeatherChannelConfig(Base):
    """Opt-in weather configuration for one Discord channel."""
    __tablename__ = "weather_channel_config"
    __table_args__ = (
        UniqueConstraint("server_id", "channel_id", name="uq_weather_channel"),
        Index("ix_weather_channel_enabled", "server_id", "enabled"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False, index=True)
    channel_id = Column(BigInteger, nullable=False, index=True)

    enabled = Column(Boolean, default=True, nullable=False)
    preset_slug = Column(String(64), nullable=False, default="fresco-piovoso")
    preset_version = Column(Integer, default=1, nullable=False)
    timezone = Column(String(64), nullable=False, default="Europe/Rome")

    # Channel-level narrowing (or widening) of the preset ranges. Validated by
    # ``systems.weather.profiles.validate_overrides`` before it is stored.
    overrides_json = Column(JSON, nullable=False, default=dict)
    # Workbook knobs: temp bounds, freezing point, feature chances.
    defaults_json = Column(JSON, nullable=False, default=dict)
    # Fields an approved event may push outside the hard ranges.
    allow_exceed_json = Column(JSON, nullable=False, default=list)

    # Posting schedule
    daily_post_time = Column(String(5), nullable=False, default="08:00")
    intraday_enabled = Column(Boolean, default=False, nullable=False)
    intraday_interval_minutes = Column(Integer, default=0, nullable=False)
    intraday_slots = Column(Integer, default=0, nullable=False)
    announce_events = Column(Boolean, default=True, nullable=False)

    # Media and retention
    media_enabled = Column(Boolean, default=True, nullable=False)
    retention_days = Column(Integer, default=90, nullable=False)

    created_by_discord_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    server = relationship("Server")
    state = relationship(
        "WeatherChannelState",
        back_populates="config",
        uselist=False,
        cascade="all, delete-orphan",
    )
    daily_snapshots = relationship(
        "WeatherDailySnapshot",
        back_populates="config",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return (
            f"<WeatherChannelConfig(server_id={self.server_id}, "
            f"channel_id={self.channel_id}, preset={self.preset_slug})>"
        )


class WeatherDailySnapshot(Base):
    """One generated day for one channel, reproducible from ``seed``."""
    __tablename__ = "weather_daily_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "config_id", "local_date", "revision", name="uq_weather_daily_snapshot"
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_id = Column(
        Integer, ForeignKey("weather_channel_config.id"), nullable=False, index=True
    )
    local_date = Column(DateTime, nullable=False, index=True)

    # Generation identity: the same seed must always rebuild this row.
    seed = Column(BigInteger, nullable=False)
    revision = Column(Integer, default=0, nullable=False)
    preset_slug = Column(String(64), nullable=False)
    preset_version = Column(Integer, nullable=False)

    # Denormalised highlights, so the daily post does not have to parse JSON.
    condition = Column(String(255), nullable=False)
    temp_min_c = Column(Float, nullable=False)
    temp_max_c = Column(Float, nullable=False)
    temp_current_c = Column(Float, nullable=False)
    precipitation_type = Column(String(16), nullable=False, default="none")
    precipitation_intensity = Column(String(64), nullable=False, default="")
    precipitation_probability = Column(Float, nullable=False, default=0.0)
    humidity_pct = Column(Float, nullable=False)
    wind_speed_kmh = Column(Float, nullable=False)
    wind_gust_kmh = Column(Float, nullable=False)
    wind_direction = Column(String(4), nullable=False)
    wind_class = Column(String(32), nullable=False)
    cloud_cover_pct = Column(Float, nullable=False)
    visibility_km = Column(Float, nullable=False)
    pressure_hpa = Column(Float, nullable=False)
    features_json = Column(JSON, nullable=False, default=list)

    # Full snapshot, including the ranges it was generated from.
    payload_json = Column(JSON, nullable=False, default=dict)
    generated_at = Column(DateTime, default=datetime.utcnow)

    config = relationship("WeatherChannelConfig", back_populates="daily_snapshots")
    intraday = relationship(
        "WeatherIntradaySnapshot",
        back_populates="daily",
        cascade="all, delete-orphan",
    )
    occurrences = relationship(
        "WeatherEventOccurrence",
        back_populates="daily",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return (
            f"<WeatherDailySnapshot(config_id={self.config_id}, "
            f"date={self.local_date:%Y-%m-%d}, condition={self.condition})>"
        )


class WeatherIntradaySnapshot(Base):
    """A partial refresh of a generated day, one row per slot."""
    __tablename__ = "weather_intraday_snapshot"
    __table_args__ = (
        UniqueConstraint("daily_id", "slot_index", name="uq_weather_intraday_slot"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    daily_id = Column(
        Integer, ForeignKey("weather_daily_snapshot.id"), nullable=False, index=True
    )
    slot_index = Column(Integer, nullable=False)
    seed = Column(BigInteger, nullable=False)

    condition = Column(String(255), nullable=False)
    temp_current_c = Column(Float, nullable=False)
    precipitation_type = Column(String(16), nullable=False, default="none")
    precipitation_intensity = Column(String(64), nullable=False, default="")
    humidity_pct = Column(Float, nullable=False)
    wind_speed_kmh = Column(Float, nullable=False)
    wind_gust_kmh = Column(Float, nullable=False)
    wind_direction = Column(String(4), nullable=False)
    wind_class = Column(String(32), nullable=False)
    cloud_cover_pct = Column(Float, nullable=False)
    visibility_km = Column(Float, nullable=False)
    pressure_hpa = Column(Float, nullable=False)
    features_json = Column(JSON, nullable=False, default=list)

    payload_json = Column(JSON, nullable=False, default=dict)
    generated_at = Column(DateTime, default=datetime.utcnow)

    daily = relationship("WeatherDailySnapshot", back_populates="intraday")

    def __repr__(self):
        return (
            f"<WeatherIntradaySnapshot(daily_id={self.daily_id}, "
            f"slot={self.slot_index}, condition={self.condition})>"
        )


class WeatherEventTemplate(Base):
    """A reusable weather event: modifiers plus the narrative to post."""
    __tablename__ = "weather_event_template"
    __table_args__ = (
        UniqueConstraint("server_id", "slug", name="uq_weather_event_template"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False, index=True)
    slug = Column(String(64), nullable=False)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)

    # Modifiers validated by ``systems.weather.generator`` before use.
    modifiers_json = Column(JSON, nullable=False, default=dict)
    allow_exceed_json = Column(JSON, nullable=False, default=list)

    # Selection constraints
    weight = Column(Float, default=1.0, nullable=False)
    min_month = Column(Integer, nullable=True)
    max_month = Column(Integer, nullable=True)
    requires_precipitation = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    media_asset_id = Column(
        Integer, ForeignKey("weather_media_asset.id"), nullable=True
    )
    created_at = Column(DateTime, default=datetime.utcnow)

    media_asset = relationship("WeatherMediaAsset")
    occurrences = relationship("WeatherEventOccurrence", back_populates="template")

    def __repr__(self):
        return f"<WeatherEventTemplate(slug={self.slug}, weight={self.weight})>"


class WeatherEventOccurrence(Base):
    """An event template applied to one generated day."""
    __tablename__ = "weather_event_occurrence"
    __table_args__ = (
        UniqueConstraint("daily_id", "template_id", name="uq_weather_event_occurrence"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    daily_id = Column(
        Integer, ForeignKey("weather_daily_snapshot.id"), nullable=False, index=True
    )
    template_id = Column(
        Integer, ForeignKey("weather_event_template.id"), nullable=False, index=True
    )

    status = Column(String(32), default="applied", nullable=False)
    payload_json = Column(JSON, nullable=False, default=dict)
    announcement_message_id = Column(BigInteger, nullable=True)
    applied_at = Column(DateTime, default=datetime.utcnow)

    daily = relationship("WeatherDailySnapshot", back_populates="occurrences")
    template = relationship("WeatherEventTemplate", back_populates="occurrences")

    def __repr__(self):
        return (
            f"<WeatherEventOccurrence(daily_id={self.daily_id}, "
            f"template_id={self.template_id}, status={self.status})>"
        )


class WeatherMediaAsset(Base):
    """An image or animation attached to a condition or an event."""
    __tablename__ = "weather_media_asset"

    id = Column(Integer, primary_key=True, autoincrement=True)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False, index=True)

    kind = Column(String(16), nullable=False, default="image")  # image, gif, video
    url = Column(String(1024), nullable=False)
    alt_text = Column(String(255), nullable=False)
    attribution = Column(String(255), nullable=True)

    # ``condition_key`` is the snapshot condition, a precipitation type or a
    # preset slug; the resolver picks the most specific match.
    condition_key = Column(String(128), nullable=True, index=True)
    weight = Column(Float, default=1.0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<WeatherMediaAsset(kind={self.kind}, key={self.condition_key})>"


class WeatherChannelState(Base):
    """Scheduler bookkeeping for one channel: what was already posted."""
    __tablename__ = "weather_channel_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_id = Column(
        Integer,
        ForeignKey("weather_channel_config.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    last_daily_date = Column(DateTime, nullable=True)
    last_daily_message_id = Column(BigInteger, nullable=True)
    last_daily_posted_at = Column(DateTime, nullable=True)

    last_intraday_slot = Column(Integer, nullable=True)
    last_intraday_message_id = Column(BigInteger, nullable=True)
    last_intraday_posted_at = Column(DateTime, nullable=True)

    # Failure tracking: the scheduler backs off instead of retrying in a loop.
    consecutive_failures = Column(Integer, default=0, nullable=False)
    last_error = Column(Text, nullable=True)
    last_attempt_at = Column(DateTime, nullable=True)

    config = relationship("WeatherChannelConfig", back_populates="state")

    def __repr__(self):
        return (
            f"<WeatherChannelState(config_id={self.config_id}, "
            f"last_daily={self.last_daily_date})>"
        )


class WeatherAuditLog(Base):
    """Append-only record of every operator action on the weather engine."""
    __tablename__ = "weather_audit_log"
    __table_args__ = (Index("ix_weather_audit_scope", "server_id", "created_at"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False, index=True)
    channel_id = Column(BigInteger, nullable=True, index=True)

    actor_discord_id = Column(BigInteger, nullable=True)
    action = Column(String(64), nullable=False)  # enable, disable, override, regenerate
    payload_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<WeatherAuditLog(action={self.action}, server_id={self.server_id})>"
