"""Regression tests for the pure, seeded weather generator.

The generator must be reproducible from the seed alone and must never leave the
hard ranges resolved by :mod:`systems.weather.profiles`. These tests pin both
properties across every climate and month, plus the event and intraday rules.
"""

from dataclasses import replace
from datetime import date

import pytest
from systems.weather.generator import (
    FEATURE_LIGHTNING,
    PRECIPITATION_NONE,
    PRECIPITATION_RAIN,
    PRECIPITATION_SNOW,
    DailyConditions,
    WeatherInvariantError,
    derive_intraday_seed,
    derive_seed,
    generate_daily_weather,
    generate_intraday_update,
    validate_daily,
    wind_class_for,
    wind_classes,
)
from systems.weather.profiles import load_profiles, resolve_effective_profile

WORLD_SEED = 4242


@pytest.fixture(scope="module")
def catalog():
    return load_profiles()


def _seed(local_date, revision=0, channel_id=200):
    return derive_seed(
        world_seed=WORLD_SEED,
        guild_id=100,
        channel_id=channel_id,
        local_date=local_date,
        preset_version=1,
        revision=revision,
    )


def _days(climate, month, count=8):
    effective = resolve_effective_profile(climate, month)
    for offset in range(count):
        local_date = date(2026, month, 1 + offset)
        yield effective, generate_daily_weather(
            effective=effective, local_date=local_date, seed=_seed(local_date)
        )


def test_the_same_seed_produces_the_same_day(catalog):
    effective = resolve_effective_profile(catalog.get("desertico"), 7)
    local_date = date(2026, 7, 4)
    seed = _seed(local_date)

    first = generate_daily_weather(effective=effective, local_date=local_date, seed=seed)
    second = generate_daily_weather(effective=effective, local_date=local_date, seed=seed)

    assert first == second
    assert first.to_dict() == second.to_dict()


def test_the_seed_depends_on_channel_and_date():
    local_date = date(2026, 7, 4)

    assert _seed(local_date) != _seed(local_date, channel_id=201)
    assert _seed(local_date) != _seed(local_date, revision=1)
    assert _seed(local_date) != _seed(date(2026, 7, 5))


def test_different_channels_get_different_weather(catalog):
    effective = resolve_effective_profile(catalog.get("fresco-piovoso"), 4)
    local_date = date(2026, 4, 9)

    first = generate_daily_weather(
        effective=effective, local_date=local_date, seed=_seed(local_date)
    )
    other = generate_daily_weather(
        effective=effective, local_date=local_date, seed=_seed(local_date, channel_id=201)
    )

    assert first != other


def test_every_day_respects_the_hard_ranges(catalog):
    for climate in catalog:
        for month in range(1, 13):
            for effective, day in _days(climate, month):
                validate_daily(day, effective)

                assert effective.temp_min.contains(day.temp_min_c)
                assert effective.temp_max.contains(day.temp_max_c)
                assert day.temp_min_c <= day.temp_current_c <= day.temp_max_c
                assert effective.humidity.contains(day.humidity_pct)
                assert effective.cloud_cover.contains(day.cloud_cover_pct)
                assert effective.wind_speed.contains(day.wind_speed_kmh)
                assert effective.wind_gust.contains(day.wind_gust_kmh)
                assert effective.visibility.contains(day.visibility_km)
                assert effective.pressure.contains(day.pressure_hpa)


def test_gust_is_never_below_the_sustained_wind(catalog):
    for climate in catalog:
        for month in (1, 7):
            for _effective, day in _days(climate, month):
                assert day.wind_gust_kmh >= day.wind_speed_kmh


def test_wind_class_matches_the_speed(catalog):
    for climate in catalog:
        for _effective, day in _days(climate, 5, count=4):
            assert day.wind_class == wind_class_for(day.wind_speed_kmh)


def test_wind_classes_are_ordered_and_contiguous():
    classes = wind_classes()

    assert len(classes) == 13
    for _low, _high, name in classes:
        assert name
    for previous, current in zip(classes, classes[1:]):
        assert previous[1] <= current[0] + 0.01, (previous, current)


def test_a_dry_day_carries_no_intensity(catalog):
    for climate in catalog:
        for _effective, day in _days(climate, 2, count=12):
            if day.precipitation_type == PRECIPITATION_NONE:
                assert day.precipitation_intensity == ""
            else:
                assert day.precipitation_intensity


def test_snow_never_falls_on_a_warm_day(catalog):
    polar = resolve_effective_profile(catalog.get("polare"), 1)
    tropical = resolve_effective_profile(catalog.get("equatoriale"), 7)

    for effective in (polar, tropical):
        for offset in range(30):
            local_date = date(2026, effective.month.month, 1 + offset % 28)
            day = generate_daily_weather(
                effective=effective, local_date=local_date, seed=_seed(local_date, offset)
            )
            if day.precipitation_type == PRECIPITATION_NONE:
                continue
            mean = (day.temp_min_c + day.temp_max_c) / 2.0
            if mean <= -2.0:
                assert day.precipitation_type != PRECIPITATION_RAIN
            if mean >= 2.0:
                assert day.precipitation_type != PRECIPITATION_SNOW


def test_the_previous_day_smooths_but_never_widens(catalog):
    effective = resolve_effective_profile(catalog.get("steppico"), 3)
    local_date = date(2026, 3, 10)
    seed = _seed(local_date)
    yesterday = date(2026, 3, 9)

    cold = replace(
        generate_daily_weather(effective=effective, local_date=yesterday, seed=_seed(yesterday)),
        temp_min_c=effective.temp_min.min,
        temp_max_c=effective.temp_min.min,
    )

    smoothed = generate_daily_weather(
        effective=effective, local_date=local_date, seed=seed, previous=cold
    )

    validate_daily(smoothed, effective)
    assert effective.temp_min.contains(smoothed.temp_min_c)
    assert effective.temp_max.contains(smoothed.temp_max_c)


def test_event_modifiers_are_clamped_to_the_hard_ranges(catalog):
    effective = resolve_effective_profile(catalog.get("desertico"), 7)
    local_date = date(2026, 7, 12)

    modified = generate_daily_weather(
        effective=effective,
        local_date=local_date,
        seed=_seed(local_date),
        event_modifiers={"temp_delta_c": 60.0, "wind_multiplier": 12.0},
    )

    assert modified.temp_max_c == effective.temp_max.max
    assert modified.wind_speed_kmh == effective.wind_speed.max
    assert modified.wind_gust_kmh >= modified.wind_speed_kmh
    validate_daily(modified, effective)


def test_event_modifiers_can_exceed_when_explicitly_allowed(catalog):
    effective = resolve_effective_profile(catalog.get("desertico"), 7)
    local_date = date(2026, 7, 12)
    day = generate_daily_weather(effective=effective, local_date=local_date, seed=_seed(local_date))

    modified = generate_daily_weather(
        effective=effective,
        local_date=local_date,
        seed=_seed(local_date),
        event_modifiers={"temp_delta_c": 20.0},
        allow_exceed=("temp_max_c",),
    )

    assert modified.temp_max_c > effective.temp_max.max
    assert modified.temp_max_c == pytest.approx(day.temp_max_c + 20.0, abs=0.1)
    validate_daily(modified, effective, allow_exceed=("temp_max_c",))


def test_an_unknown_event_modifier_is_rejected(catalog):
    effective = resolve_effective_profile(catalog.get("desertico"), 7)
    local_date = date(2026, 7, 12)

    with pytest.raises(WeatherInvariantError):
        generate_daily_weather(
            effective=effective,
            local_date=local_date,
            seed=_seed(local_date),
            event_modifiers={"temperature_delta": 5.0},
        )


def test_event_precipitation_override_replaces_the_type(catalog):
    effective = resolve_effective_profile(catalog.get("desertico"), 7)
    local_date = date(2026, 7, 12)

    day = generate_daily_weather(
        effective=effective,
        local_date=local_date,
        seed=_seed(local_date),
        event_modifiers={"precipitation_override": {"type": "rain", "intensity": "Downpour"}},
    )

    assert day.precipitation_type == PRECIPITATION_RAIN
    assert day.precipitation_intensity == "Downpour"
    validate_daily(day, effective)


def test_intraday_stays_inside_the_daily_envelope(catalog):
    for climate in catalog:
        for month in (1, 6):
            effective = resolve_effective_profile(climate, month)
            local_date = date(2026, month, 3)
            day = generate_daily_weather(
                effective=effective, local_date=local_date, seed=_seed(local_date)
            )

            previous = None
            for slot in range(6):
                seed = derive_intraday_seed(day.seed, slot)
                update = generate_intraday_update(
                    daily=day,
                    effective=effective,
                    slot_index=slot,
                    seed=seed,
                    previous=previous,
                )
                previous = update

                assert update.slot_index == slot
                assert day.temp_min_c <= update.temp_current_c <= day.temp_max_c
                assert update.wind_gust_kmh >= update.wind_speed_kmh
                assert update.precipitation_type == day.precipitation_type
                assert update.wind_class == wind_class_for(update.wind_speed_kmh)


def test_intraday_cannot_invent_precipitation(catalog):
    effective = resolve_effective_profile(catalog.get("desertico"), 1)
    local_date = date(2026, 1, 5)
    day = generate_daily_weather(effective=effective, local_date=local_date, seed=_seed(local_date))
    dry = replace(day, precipitation_type=PRECIPITATION_NONE, precipitation_intensity="")

    update = generate_intraday_update(
        daily=dry,
        effective=effective,
        slot_index=0,
        seed=derive_intraday_seed(dry.seed, 0),
    )

    assert update.precipitation_type == PRECIPITATION_NONE
    assert update.precipitation_intensity == ""


def test_a_negative_slot_index_is_rejected(catalog):
    effective = resolve_effective_profile(catalog.get("desertico"), 1)
    local_date = date(2026, 1, 5)
    day = generate_daily_weather(effective=effective, local_date=local_date, seed=_seed(local_date))

    with pytest.raises(WeatherInvariantError):
        generate_intraday_update(daily=day, effective=effective, slot_index=-1, seed=day.seed)


def test_validation_rejects_a_broken_snapshot(catalog):
    effective = resolve_effective_profile(catalog.get("desertico"), 7)
    local_date = date(2026, 7, 4)
    day = generate_daily_weather(effective=effective, local_date=local_date, seed=_seed(local_date))

    with pytest.raises(WeatherInvariantError):
        validate_daily(replace(day, wind_gust_kmh=day.wind_speed_kmh - 5.0), effective)

    with pytest.raises(WeatherInvariantError):
        validate_daily(replace(day, temp_current_c=day.temp_max_c + 5.0), effective)

    with pytest.raises(WeatherInvariantError):
        validate_daily(
            replace(
                day,
                precipitation_type=PRECIPITATION_RAIN,
                precipitation_intensity="",
            ),
            effective,
        )

    with pytest.raises(WeatherInvariantError):
        validate_daily(
            replace(
                day,
                precipitation_type=PRECIPITATION_NONE,
                precipitation_intensity="Drizzle",
            ),
            effective,
        )


def test_the_snapshot_round_trips_through_a_dict(catalog):
    effective = resolve_effective_profile(catalog.get("tundra"), 11)
    local_date = date(2026, 11, 20)
    day = generate_daily_weather(effective=effective, local_date=local_date, seed=_seed(local_date))

    assert DailyConditions.from_dict(day.to_dict()) == day


def test_lightning_only_accompanies_a_storm(catalog):
    for climate in catalog:
        for month in (1, 7):
            for _effective, day in _days(climate, month, count=12):
                if FEATURE_LIGHTNING in day.features:
                    assert day.precipitation_type != PRECIPITATION_NONE
