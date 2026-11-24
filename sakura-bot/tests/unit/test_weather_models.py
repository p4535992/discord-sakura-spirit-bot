"""ORM regression tests for the per-channel weather tables.

The V4 tables are additive: they must be registered on ``Base.metadata`` so
``create_all`` builds them, and their constraints must hold on a real schema.
These tests use the in-memory SQLite fixture; PostgreSQL remains the
integration target.
"""

from datetime import datetime

import pytest
from models import (
    Server,
    WeatherAuditLog,
    WeatherChannelConfig,
    WeatherChannelState,
    WeatherClimatePreset,
    WeatherDailySnapshot,
    WeatherEventOccurrence,
    WeatherEventTemplate,
    WeatherIntradaySnapshot,
    WeatherMediaAsset,
)
from models.base import Base
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

WEATHER_TABLES = (
    "weather_climate_preset",
    "weather_channel_config",
    "weather_daily_snapshot",
    "weather_intraday_snapshot",
    "weather_event_template",
    "weather_event_occurrence",
    "weather_media_asset",
    "weather_channel_state",
    "weather_audit_log",
)


def test_every_weather_table_is_registered():
    for name in WEATHER_TABLES:
        assert name in Base.metadata.tables, f"{name} is not registered"


def test_the_legacy_weather_table_is_untouched():
    """The V4 engine must not alter the table used by the Sakura weather."""
    assert "weather_history" in Base.metadata.tables
    assert "weather_history" not in WEATHER_TABLES


async def _server(session, discord_id=900000000000000001):
    server = Server(discord_id=discord_id, name="Test Guild")
    session.add(server)
    await session.flush()
    return server


async def test_a_channel_config_round_trips(sqlite_session):
    server = await _server(sqlite_session)
    config = WeatherChannelConfig(
        server_id=server.id,
        channel_id=111222333444555666,
        preset_slug="desertico",
        timezone="Europe/Rome",
        overrides_json={"humidity_pct": {"min": 7, "max": 28}},
        defaults_json={"temp_outer_bound_c": 7.0},
        allow_exceed_json=["temp_max_c"],
        intraday_enabled=True,
        intraday_interval_minutes=120,
        intraday_slots=6,
        retention_days=30,
        created_by_discord_id=123456789012345678,
    )
    sqlite_session.add(config)
    await sqlite_session.commit()

    stored = (
        await sqlite_session.execute(
            select(WeatherChannelConfig).where(
                WeatherChannelConfig.channel_id == 111222333444555666
            )
        )
    ).scalar_one()

    assert stored.enabled is True
    assert stored.preset_slug == "desertico"
    assert stored.overrides_json == {"humidity_pct": {"min": 7, "max": 28}}
    assert stored.allow_exceed_json == ["temp_max_c"]
    assert stored.intraday_slots == 6
    assert stored.daily_post_time == "08:00"
    assert stored.retention_days == 30


async def test_a_channel_cannot_be_configured_twice(sqlite_session):
    server = await _server(sqlite_session)
    sqlite_session.add(
        WeatherChannelConfig(server_id=server.id, channel_id=111, preset_slug="tundra")
    )
    await sqlite_session.commit()

    sqlite_session.add(
        WeatherChannelConfig(server_id=server.id, channel_id=111, preset_slug="polare")
    )

    with pytest.raises(IntegrityError):
        await sqlite_session.commit()

    await sqlite_session.rollback()


async def test_a_preset_stores_twelve_months(sqlite_session):
    preset = WeatherClimatePreset(
        slug="desertico",
        display_name="Desertico",
        family="arid",
        source="workbook",
        version=1,
        months_json=[{"month": month} for month in range(1, 13)],
        field_provenance_json={"temp_cold_c": "project_default"},
        is_builtin=True,
    )
    sqlite_session.add(preset)
    await sqlite_session.commit()

    stored = (
        await sqlite_session.execute(
            select(WeatherClimatePreset).where(WeatherClimatePreset.slug == "desertico")
        )
    ).scalar_one()

    assert len(stored.months_json) == 12
    assert stored.field_provenance_json["temp_cold_c"] == "project_default"
    assert stored.is_builtin is True


async def _config(session, server):
    config = WeatherChannelConfig(server_id=server.id, channel_id=222, preset_slug="fresco-piovoso")
    session.add(config)
    await session.flush()
    return config


def _daily(config_id, **overrides):
    payload = {
        "config_id": config_id,
        "local_date": datetime(2026, 7, 4),
        "seed": 1234567890123456789,
        "preset_slug": "desertico",
        "preset_version": 1,
        "condition": "Steady rainfall, Gray, slightly overcast",
        "temp_min_c": 26.1,
        "temp_max_c": 38.1,
        "temp_current_c": 33.0,
        "precipitation_type": "rain",
        "precipitation_intensity": "Steady rainfall",
        "precipitation_probability": 0.05,
        "humidity_pct": 36.9,
        "wind_speed_kmh": 13.1,
        "wind_gust_kmh": 17.5,
        "wind_direction": "E",
        "wind_class": "Gentle breeze",
        "cloud_cover_pct": 52.0,
        "visibility_km": 24.8,
        "pressure_hpa": 992.2,
        "features_json": [],
        "payload_json": {"seed": 1234567890123456789, "ranges": {}},
    }
    payload.update(overrides)
    return WeatherDailySnapshot(**payload)


async def test_a_daily_snapshot_round_trips(sqlite_session):
    server = await _server(sqlite_session)
    config = await _config(sqlite_session, server)
    sqlite_session.add(_daily(config.id))
    await sqlite_session.commit()

    stored = (await sqlite_session.execute(select(WeatherDailySnapshot))).scalar_one()

    assert stored.seed == 1234567890123456789
    assert stored.temp_max_c == pytest.approx(38.1)
    assert stored.payload_json["seed"] == 1234567890123456789
    assert stored.features_json == []


async def test_a_day_cannot_be_generated_twice_at_the_same_revision(sqlite_session):
    server = await _server(sqlite_session)
    config = await _config(sqlite_session, server)
    sqlite_session.add(_daily(config.id))
    await sqlite_session.commit()

    sqlite_session.add(_daily(config.id))

    with pytest.raises(IntegrityError):
        await sqlite_session.commit()

    await sqlite_session.rollback()


async def test_a_new_revision_is_allowed(sqlite_session):
    server = await _server(sqlite_session)
    config = await _config(sqlite_session, server)
    sqlite_session.add(_daily(config.id))
    sqlite_session.add(_daily(config.id, revision=1, temp_max_c=39.5))
    await sqlite_session.commit()

    rows = (await sqlite_session.execute(select(WeatherDailySnapshot))).scalars().all()

    assert len(rows) == 2
    assert {row.revision for row in rows} == {0, 1}


async def test_intraday_slots_belong_to_their_day(sqlite_session):
    server = await _server(sqlite_session)
    config = await _config(sqlite_session, server)
    daily = _daily(config.id)
    sqlite_session.add(daily)
    await sqlite_session.flush()

    for slot in range(3):
        sqlite_session.add(
            WeatherIntradaySnapshot(
                daily_id=daily.id,
                slot_index=slot,
                seed=daily.seed + slot,
                condition="A few clouds",
                temp_current_c=30.0 + slot,
                precipitation_type="none",
                precipitation_intensity="",
                humidity_pct=30.0,
                wind_speed_kmh=10.0,
                wind_gust_kmh=14.0,
                wind_direction="N",
                wind_class="Light breeze",
                cloud_cover_pct=20.0,
                visibility_km=30.0,
                pressure_hpa=1000.0,
                features_json=[],
                payload_json={},
            )
        )
    await sqlite_session.commit()

    stored = (
        (
            await sqlite_session.execute(
                select(WeatherIntradaySnapshot).order_by(WeatherIntradaySnapshot.slot_index)
            )
        )
        .scalars()
        .all()
    )

    assert [row.slot_index for row in stored] == [0, 1, 2]
    assert stored[2].temp_current_c == pytest.approx(32.0)


async def test_deleting_a_config_removes_its_snapshots(sqlite_session):
    server = await _server(sqlite_session)
    config = await _config(sqlite_session, server)
    sqlite_session.add(_daily(config.id))
    await sqlite_session.commit()

    await sqlite_session.delete(config)
    await sqlite_session.commit()

    remaining = (await sqlite_session.execute(select(WeatherDailySnapshot))).scalars().all()

    assert remaining == []


async def test_an_event_occurrence_links_a_template_to_a_day(sqlite_session):
    server = await _server(sqlite_session)
    config = await _config(sqlite_session, server)

    asset = WeatherMediaAsset(
        server_id=server.id,
        kind="gif",
        url="https://example.invalid/blizzard.gif",
        alt_text="A blizzard over a frozen plain",
        attribution="Test asset",
        condition_key="Blizzard",
    )
    sqlite_session.add(asset)
    await sqlite_session.flush()

    template = WeatherEventTemplate(
        server_id=server.id,
        slug="blizzard",
        name="Blizzard",
        description="A sudden blizzard closes the roads",
        modifiers_json={"temp_delta_c": -12.0, "wind_multiplier": 2.0},
        allow_exceed_json=["wind_gust_kmh"],
        weight=0.5,
        min_month=11,
        max_month=2,
        requires_precipitation=True,
        media_asset_id=asset.id,
    )
    sqlite_session.add(template)
    await sqlite_session.flush()

    daily = _daily(config.id)
    sqlite_session.add(daily)
    await sqlite_session.flush()

    sqlite_session.add(
        WeatherEventOccurrence(
            daily_id=daily.id,
            template_id=template.id,
            status="applied",
            payload_json={"modifiers": {"temp_delta_c": -12.0}},
            announcement_message_id=555666777888999000,
        )
    )
    await sqlite_session.commit()

    stored = (await sqlite_session.execute(select(WeatherEventOccurrence))).scalar_one()

    assert stored.template.slug == "blizzard"
    assert stored.template.media_asset.alt_text == "A blizzard over a frozen plain"
    assert stored.daily.condition.startswith("Steady rainfall")
    assert stored.template.allow_exceed_json == ["wind_gust_kmh"]
    assert stored.announcement_message_id == 555666777888999000


async def test_a_template_slug_is_unique_per_server(sqlite_session):
    server = await _server(sqlite_session)
    sqlite_session.add(WeatherEventTemplate(server_id=server.id, slug="heatwave", name="Heatwave"))
    await sqlite_session.commit()

    sqlite_session.add(WeatherEventTemplate(server_id=server.id, slug="heatwave", name="Again"))

    with pytest.raises(IntegrityError):
        await sqlite_session.commit()

    await sqlite_session.rollback()


async def test_channel_state_tracks_the_last_post(sqlite_session):
    server = await _server(sqlite_session)
    config = await _config(sqlite_session, server)

    state = WeatherChannelState(
        config_id=config.id,
        last_daily_date=datetime(2026, 7, 4),
        last_daily_message_id=123456789012345678,
        last_intraday_slot=3,
        consecutive_failures=2,
        last_error="Discord returned 503",
    )
    sqlite_session.add(state)
    await sqlite_session.commit()

    stored = (await sqlite_session.execute(select(WeatherChannelState))).scalar_one()

    assert stored.config.channel_id == 222
    assert stored.last_intraday_slot == 3
    assert stored.consecutive_failures == 2
    assert stored.last_error == "Discord returned 503"


async def test_the_audit_log_records_operator_actions(sqlite_session):
    server = await _server(sqlite_session)

    sqlite_session.add(
        WeatherAuditLog(
            server_id=server.id,
            channel_id=222,
            actor_discord_id=123456789012345678,
            action="enable",
            payload_json={"preset_slug": "desertico", "overrides": {}},
        )
    )
    await sqlite_session.commit()

    stored = (await sqlite_session.execute(select(WeatherAuditLog))).scalar_one()

    assert stored.action == "enable"
    assert stored.payload_json["preset_slug"] == "desertico"
    assert stored.created_at is not None
