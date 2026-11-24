"""Pure, seeded weather generation for the per-channel engine.

Nothing here touches Discord, the database or the wall clock: the caller passes
an ``EffectiveMonthProfile``, a local date and a seed, and receives an immutable
snapshot. That is what makes the daily generation reproducible after a restart
and testable without a database.

The vocabularies come from the workbook (``Precipitation`` and ``Wind`` sheets);
the numeric ranges come from the operational profiles, never from the
``RANDBETWEEN`` snapshots.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from random import Random
from typing import Any, Mapping, Sequence

from systems.weather.profiles import (
    WIND_DIRECTIONS,
    EffectiveMonthProfile,
)

CATALOG_PATH = Path(__file__).with_name("climate_catalog.json")

PRECIPITATION_NONE = "none"
PRECIPITATION_RAIN = "rain"
PRECIPITATION_SNOW = "snow"
PRECIPITATION_MIXED = "mixed"
PRECIPITATION_TYPES = (
    PRECIPITATION_NONE,
    PRECIPITATION_RAIN,
    PRECIPITATION_SNOW,
    PRECIPITATION_MIXED,
)

RAIN_INTENSITY = (
    "Light mist",
    "Drizzle",
    "Steady rainfall",
    "Strong rainfall",
    "Pounding rain",
    "Downpour",
)
SNOW_INTENSITY = (
    "A few flakes",
    "Dusting of snow",
    "Flurries",
    "Moderate snowfall",
    "Heavy snowfall",
    "Blizzard",
)
# Middle intensities are more likely than the two extremes.
INTENSITY_WEIGHTS = (1.0, 2.0, 3.0, 3.0, 2.0, 1.0)

FEATURE_FOG = "Fog"
FEATURE_LIGHTNING = "Lightning"
FEATURE_HAIL = "Hail"

DEFAULT_BOUNDS = {
    "temp_outer_bound_c": 7.0,
    "temp_inner_bound_c": 2.0,
    "freezing_point_c": 0.0,
    "chance_fog_for_rain": 0.15,
    "chance_lightning_for_storm": 0.25,
    "chance_hail_for_rain": 0.10,
    "chance_hail_for_storm": 0.20,
}

# Cloud cover thresholds, used to derive the label from the number so the text
# can never contradict the value.
DRY_CLOUD_LABELS = ((25.0, "Clear"), (50.0, "A few clouds"), (100.0, "Mostly cloudy"))
WET_CLOUD_LABELS = (
    (60.0, "Gray, slightly overcast"),
    (80.0, "Gray, highly overcast"),
    (100.0, "Dark storm clouds"),
)


class WeatherInvariantError(ValueError):
    """A generated snapshot violates a documented physical invariant."""


_WIND_CLASSES: tuple[tuple[float, float, str], ...] | None = None


def wind_classes() -> tuple[tuple[float, float, str], ...]:
    """The thirteen workbook wind classes, in km/h, loaded once."""
    global _WIND_CLASSES
    if _WIND_CLASSES is None:
        payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        _WIND_CLASSES = tuple(
            (float(entry["kmh_min"]), float(entry["kmh_max"]), entry["name"])
            for entry in payload["wind"]
        )
    return _WIND_CLASSES


def wind_class_for(speed_kmh: float) -> str:
    """Return the workbook class that contains ``speed_kmh``."""
    classes = wind_classes()
    for low, high, name in classes:
        if low <= speed_kmh <= high:
            return name
    return classes[-1][2] if speed_kmh > classes[-1][1] else classes[0][2]


def derive_seed(
    *,
    world_seed: int,
    guild_id: int,
    channel_id: int,
    local_date: date,
    preset_version: int,
    revision: int,
) -> int:
    """Stable 64-bit seed from the full identity of one generated day.

    Two channels with the same preset get different seeds, and the same channel
    gets the same seed after a restart.
    """
    material = "|".join(
        (
            str(world_seed),
            str(guild_id),
            str(channel_id),
            local_date.isoformat(),
            str(preset_version),
            str(revision),
        )
    )
    digest = hashlib.blake2b(material.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big")


@dataclass(frozen=True)
class DailyConditions:
    """One immutable day of weather for one channel."""

    local_date: date
    temp_min_c: float
    temp_max_c: float
    temp_current_c: float
    precipitation_type: str
    precipitation_intensity: str
    precipitation_probability: float
    humidity_pct: float
    wind_speed_kmh: float
    wind_gust_kmh: float
    wind_direction: str
    wind_class: str
    cloud_cover_pct: float
    visibility_km: float
    pressure_hpa: float
    condition: str
    features: tuple[str, ...]
    seed: int
    preset_slug: str
    preset_version: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "local_date": self.local_date.isoformat(),
            "temp_min_c": self.temp_min_c,
            "temp_max_c": self.temp_max_c,
            "temp_current_c": self.temp_current_c,
            "precipitation_type": self.precipitation_type,
            "precipitation_intensity": self.precipitation_intensity,
            "precipitation_probability": self.precipitation_probability,
            "humidity_pct": self.humidity_pct,
            "wind_speed_kmh": self.wind_speed_kmh,
            "wind_gust_kmh": self.wind_gust_kmh,
            "wind_direction": self.wind_direction,
            "wind_class": self.wind_class,
            "cloud_cover_pct": self.cloud_cover_pct,
            "visibility_km": self.visibility_km,
            "pressure_hpa": self.pressure_hpa,
            "condition": self.condition,
            "features": list(self.features),
            "seed": self.seed,
            "preset_slug": self.preset_slug,
            "preset_version": self.preset_version,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DailyConditions":
        return cls(
            local_date=date.fromisoformat(str(payload["local_date"])),
            temp_min_c=float(payload["temp_min_c"]),
            temp_max_c=float(payload["temp_max_c"]),
            temp_current_c=float(payload["temp_current_c"]),
            precipitation_type=str(payload["precipitation_type"]),
            precipitation_intensity=str(payload["precipitation_intensity"]),
            precipitation_probability=float(payload["precipitation_probability"]),
            humidity_pct=float(payload["humidity_pct"]),
            wind_speed_kmh=float(payload["wind_speed_kmh"]),
            wind_gust_kmh=float(payload["wind_gust_kmh"]),
            wind_direction=str(payload["wind_direction"]),
            wind_class=str(payload["wind_class"]),
            cloud_cover_pct=float(payload["cloud_cover_pct"]),
            visibility_km=float(payload["visibility_km"]),
            pressure_hpa=float(payload["pressure_hpa"]),
            condition=str(payload["condition"]),
            features=tuple(payload.get("features") or ()),
            seed=int(payload["seed"]),
            preset_slug=str(payload["preset_slug"]),
            preset_version=int(payload["preset_version"]),
        )


@dataclass(frozen=True)
class IntradayConditions:
    """A partial refresh of the day, used by the intraday scheduler."""

    local_date: date
    slot_index: int
    temp_current_c: float
    precipitation_type: str
    precipitation_intensity: str
    humidity_pct: float
    wind_speed_kmh: float
    wind_gust_kmh: float
    wind_direction: str
    wind_class: str
    cloud_cover_pct: float
    visibility_km: float
    pressure_hpa: float
    condition: str
    features: tuple[str, ...]
    seed: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "local_date": self.local_date.isoformat(),
            "slot_index": self.slot_index,
            "temp_current_c": self.temp_current_c,
            "precipitation_type": self.precipitation_type,
            "precipitation_intensity": self.precipitation_intensity,
            "humidity_pct": self.humidity_pct,
            "wind_speed_kmh": self.wind_speed_kmh,
            "wind_gust_kmh": self.wind_gust_kmh,
            "wind_direction": self.wind_direction,
            "wind_class": self.wind_class,
            "cloud_cover_pct": self.cloud_cover_pct,
            "visibility_km": self.visibility_km,
            "pressure_hpa": self.pressure_hpa,
            "condition": self.condition,
            "features": list(self.features),
            "seed": self.seed,
        }


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _label_for(value: float, table: Sequence[tuple[float, str]]) -> str:
    for threshold, label in table:
        if value <= threshold:
            return label
    return table[-1][1]


def _intensity_index(rng: Random) -> int:
    return rng.choices(range(len(RAIN_INTENSITY)), weights=INTENSITY_WEIGHTS, k=1)[0]


def _config(defaults: Mapping[str, Any] | None) -> dict[str, Any]:
    merged = dict(DEFAULT_BOUNDS)
    if defaults:
        merged.update({key: value for key, value in defaults.items() if key in DEFAULT_BOUNDS})
    return merged


def _span(low: float, high: float) -> float:
    return max(0.0, high - low)


def generate_daily_weather(
    *,
    effective: EffectiveMonthProfile,
    local_date: date,
    seed: int,
    previous: DailyConditions | None = None,
    defaults: Mapping[str, Any] | None = None,
    event_modifiers: Mapping[str, Any] | None = None,
    allow_exceed: Sequence[str] = (),
) -> DailyConditions:
    """Generate one reproducible day inside the effective hard ranges.

    ``previous`` smooths the temperature reference only: it never widens a range.
    ``event_modifiers`` is applied last and is re-clamped to the hard ranges
    unless the field is listed in ``allow_exceed`` (an administrator-approved
    event that is allowed to break the envelope).
    """
    cfg = _config(defaults)
    rng = Random(seed)

    # --- temperature -----------------------------------------------------
    outer = max(1, int(round(float(cfg["temp_outer_bound_c"]))))
    inner = max(1, int(round(float(cfg["temp_inner_bound_c"]))))
    low_delta = rng.randint(min(inner, outer), max(inner, outer))
    high_delta = rng.randint(min(inner, outer), max(inner, outer))

    reference = effective.temp_avg_c
    if previous is not None:
        previous_mid = (previous.temp_min_c + previous.temp_max_c) / 2.0
        reference = 0.7 * effective.temp_avg_c + 0.3 * previous_mid

    low_anchor = _clamp(reference, effective.temp_min.min, effective.temp_min.max)
    high_anchor = _clamp(reference, effective.temp_max.min, effective.temp_max.max)
    temp_min = _clamp(low_anchor - low_delta, effective.temp_min.min, effective.temp_min.max)
    temp_max = _clamp(high_anchor + high_delta, effective.temp_max.min, effective.temp_max.max)
    if temp_min > temp_max:
        temp_min = temp_max

    # --- precipitation ---------------------------------------------------
    probability = effective.precipitation_probability
    if event_modifiers and "precipitation_probability_delta" in event_modifiers:
        probability += float(event_modifiers["precipitation_probability_delta"])
    probability = _clamp(probability, 0.0, 1.0)
    is_wet = rng.random() < probability

    cloud_low, cloud_high = effective.cloud_cover.min, effective.cloud_cover.max
    if is_wet:
        floor = min(cloud_high, max(cloud_low, 55.0))
        cloud = rng.uniform(floor, cloud_high)
    else:
        # Two draws, keep the lower one: dry days skew towards a clear sky.
        cloud = min(rng.uniform(cloud_low, cloud_high), rng.uniform(cloud_low, cloud_high))
    cloud = _clamp(cloud, cloud_low, cloud_high)

    intensity_index = 0
    if is_wet:
        mean_temp = (temp_min + temp_max) / 2.0
        freezing = float(cfg["freezing_point_c"])
        if mean_temp >= freezing + 2.0:
            precipitation_type = PRECIPITATION_RAIN
        elif mean_temp <= freezing - 2.0:
            precipitation_type = PRECIPITATION_SNOW
        else:
            precipitation_type = rng.choice(
                (PRECIPITATION_MIXED, PRECIPITATION_RAIN, PRECIPITATION_SNOW)
            )
        intensity_index = _intensity_index(rng)
        table = SNOW_INTENSITY if precipitation_type == PRECIPITATION_SNOW else RAIN_INTENSITY
        intensity = table[intensity_index]
        cloud_label = _label_for(cloud, WET_CLOUD_LABELS)
    else:
        precipitation_type = PRECIPITATION_NONE
        intensity = ""
        cloud_label = _label_for(cloud, DRY_CLOUD_LABELS)

    # --- humidity --------------------------------------------------------
    humidity_span = _span(effective.humidity.min, effective.humidity.max)
    if is_wet:
        humidity = rng.uniform(effective.humidity.min + 0.5 * humidity_span, effective.humidity.max)
    else:
        humidity = rng.uniform(effective.humidity.min, effective.humidity.min + 0.6 * humidity_span)
    humidity = _clamp(humidity, effective.humidity.min, effective.humidity.max)

    # --- wind ------------------------------------------------------------
    wind = rng.triangular(
        effective.wind_speed.min, effective.wind_speed.max, effective.wind_speed.min
    )
    wind = _clamp(wind, effective.wind_speed.min, effective.wind_speed.max)
    gust = _clamp(wind * rng.uniform(1.0, 1.6), effective.wind_gust.min, effective.wind_gust.max)
    gust = max(gust, wind)
    directions = effective.preferred_wind_directions or WIND_DIRECTIONS
    direction = rng.choice(tuple(directions))

    # --- features --------------------------------------------------------
    features: list[str] = []
    if is_wet and rng.random() < float(cfg["chance_fog_for_rain"]):
        features.append(FEATURE_FOG)
    if intensity_index >= 4 and rng.random() < float(cfg["chance_lightning_for_storm"]):
        features.append(FEATURE_LIGHTNING)
    if is_wet:
        hail_chance = (
            float(cfg["chance_hail_for_storm"])
            if intensity_index >= 4
            else float(cfg["chance_hail_for_rain"])
        )
        if rng.random() < hail_chance:
            features.append(FEATURE_HAIL)
    has_fog = FEATURE_FOG in features

    # --- visibility and pressure ----------------------------------------
    visibility = effective.visibility.max
    if is_wet:
        visibility *= 1.0 - 0.12 * (intensity_index + 1)
    if has_fog:
        visibility = min(visibility, effective.visibility.max * 0.25)
    visibility = _clamp(visibility, effective.visibility.min, effective.visibility.max)

    pressure_span = _span(effective.pressure.min, effective.pressure.max)
    if is_wet:
        pressure = rng.uniform(
            effective.pressure.min, effective.pressure.min + 0.55 * pressure_span
        )
    else:
        pressure = rng.uniform(
            effective.pressure.min + 0.45 * pressure_span, effective.pressure.max
        )
    pressure = _clamp(pressure, effective.pressure.min, effective.pressure.max)

    # --- current temperature --------------------------------------------
    middle = (temp_min + temp_max) / 2.0
    half = (temp_max - temp_min) / 2.0
    temp_current = _clamp(middle + rng.uniform(-half, half) * 0.6, temp_min, temp_max)

    conditions = DailyConditions(
        local_date=local_date,
        temp_min_c=round(temp_min, 1),
        temp_max_c=round(temp_max, 1),
        temp_current_c=round(temp_current, 1),
        precipitation_type=precipitation_type,
        precipitation_intensity=intensity,
        precipitation_probability=round(probability, 3),
        humidity_pct=round(humidity, 1),
        wind_speed_kmh=round(wind, 1),
        wind_gust_kmh=round(max(gust, wind), 1),
        wind_direction=direction,
        wind_class=wind_class_for(round(wind, 1)),
        cloud_cover_pct=round(cloud, 1),
        visibility_km=round(visibility, 1),
        pressure_hpa=round(pressure, 1),
        condition=_condition_text(cloud_label, intensity, features),
        features=tuple(features),
        seed=seed,
        preset_slug=effective.profile.slug,
        preset_version=effective.profile.version,
    )

    if event_modifiers:
        conditions = apply_event_modifiers(
            conditions,
            effective=effective,
            modifiers=event_modifiers,
            allow_exceed=allow_exceed,
        )

    validate_daily(conditions, effective, allow_exceed=allow_exceed)
    return conditions


def _condition_text(cloud_label: str, intensity: str, features: Sequence[str]) -> str:
    parts = [intensity, cloud_label] if intensity else [cloud_label]
    parts.extend(features)
    return ", ".join(parts)


def _cloud_label_for(cloud_cover_pct: float, is_wet: bool) -> str:
    table = WET_CLOUD_LABELS if is_wet else DRY_CLOUD_LABELS
    return _label_for(cloud_cover_pct, table)


EVENT_MODIFIER_KEYS = frozenset(
    {
        "temp_delta_c",
        "wind_multiplier",
        "humidity_delta_pct",
        "cloud_cover_delta_pct",
        "visibility_multiplier",
        "pressure_delta_hpa",
        "precipitation_probability_delta",
        "precipitation_override",
    }
)


def apply_event_modifiers(
    conditions: DailyConditions,
    *,
    effective: EffectiveMonthProfile,
    modifiers: Mapping[str, Any],
    allow_exceed: Sequence[str] = (),
) -> DailyConditions:
    """Apply a validated event payload to an already generated day.

    Unknown keys are rejected instead of silently ignored, so a typo in an event
    template surfaces when it is saved rather than producing a no-op event.
    """
    unknown = set(modifiers) - EVENT_MODIFIER_KEYS
    if unknown:
        raise WeatherInvariantError(f"unknown event modifier(s): {', '.join(sorted(unknown))}")

    allowed = frozenset(allow_exceed)

    def bound(field: str, value: float, low: float, high: float) -> float:
        return value if field in allowed else _clamp(value, low, high)

    temp_min = conditions.temp_min_c
    temp_max = conditions.temp_max_c
    temp_delta = float(modifiers.get("temp_delta_c", 0.0) or 0.0)
    if temp_delta:
        temp_min = bound(
            "temp_min_c", temp_min + temp_delta, effective.temp_min.min, effective.temp_min.max
        )
        temp_max = bound(
            "temp_max_c", temp_max + temp_delta, effective.temp_max.min, effective.temp_max.max
        )
    if temp_min > temp_max:
        temp_min, temp_max = temp_max, temp_min

    wind_multiplier = float(modifiers.get("wind_multiplier", 1.0) or 1.0)
    wind = bound(
        "wind_speed_kmh",
        conditions.wind_speed_kmh * wind_multiplier,
        effective.wind_speed.min,
        effective.wind_speed.max,
    )
    gust = bound(
        "wind_gust_kmh",
        conditions.wind_gust_kmh * wind_multiplier,
        effective.wind_gust.min,
        effective.wind_gust.max,
    )
    gust = max(gust, wind)

    humidity = bound(
        "humidity_pct",
        conditions.humidity_pct + float(modifiers.get("humidity_delta_pct", 0.0) or 0.0),
        effective.humidity.min,
        effective.humidity.max,
    )
    cloud = bound(
        "cloud_cover_pct",
        conditions.cloud_cover_pct + float(modifiers.get("cloud_cover_delta_pct", 0.0) or 0.0),
        effective.cloud_cover.min,
        effective.cloud_cover.max,
    )
    visibility = bound(
        "visibility_km",
        conditions.visibility_km * float(modifiers.get("visibility_multiplier", 1.0) or 1.0),
        effective.visibility.min,
        effective.visibility.max,
    )
    pressure = bound(
        "pressure_hpa",
        conditions.pressure_hpa + float(modifiers.get("pressure_delta_hpa", 0.0) or 0.0),
        effective.pressure.min,
        effective.pressure.max,
    )

    precipitation_type = conditions.precipitation_type
    intensity = conditions.precipitation_intensity
    override = modifiers.get("precipitation_override")
    if override:
        precipitation_type = str(override["type"])
        intensity = str(override.get("intensity", ""))
        if precipitation_type not in PRECIPITATION_TYPES:
            raise WeatherInvariantError(f"unknown precipitation type: {precipitation_type}")
        if precipitation_type == PRECIPITATION_NONE:
            intensity = ""

    is_wet = precipitation_type != PRECIPITATION_NONE
    cloud_label = _cloud_label_for(cloud, is_wet)

    return DailyConditions(
        local_date=conditions.local_date,
        temp_min_c=round(temp_min, 1),
        temp_max_c=round(temp_max, 1),
        temp_current_c=round(_clamp(conditions.temp_current_c, temp_min, temp_max), 1),
        precipitation_type=precipitation_type,
        precipitation_intensity=intensity,
        precipitation_probability=conditions.precipitation_probability,
        humidity_pct=round(humidity, 1),
        wind_speed_kmh=round(wind, 1),
        wind_gust_kmh=round(gust, 1),
        wind_direction=conditions.wind_direction,
        wind_class=wind_class_for(round(wind, 1)),
        cloud_cover_pct=round(cloud, 1),
        visibility_km=round(visibility, 1),
        pressure_hpa=round(pressure, 1),
        condition=_condition_text(cloud_label, intensity, conditions.features),
        features=conditions.features,
        seed=conditions.seed,
        preset_slug=conditions.preset_slug,
        preset_version=conditions.preset_version,
    )


def validate_daily(
    conditions: DailyConditions,
    effective: EffectiveMonthProfile,
    *,
    allow_exceed: Sequence[str] = (),
) -> None:
    """Raise ``WeatherInvariantError`` if a snapshot breaks a hard rule."""
    allowed = frozenset(allow_exceed)

    def check(field: str, value: float, low: float, high: float) -> None:
        if field in allowed:
            return
        if not low <= value <= high:
            raise WeatherInvariantError(f"{field}={value} outside the hard range {low}..{high}")

    if conditions.temp_min_c > conditions.temp_max_c:
        raise WeatherInvariantError("temp_min_c is greater than temp_max_c")
    check("temp_min_c", conditions.temp_min_c, effective.temp_min.min, effective.temp_min.max)
    check("temp_max_c", conditions.temp_max_c, effective.temp_max.min, effective.temp_max.max)
    if not conditions.temp_min_c <= conditions.temp_current_c <= conditions.temp_max_c:
        raise WeatherInvariantError("temp_current_c outside the daily min/max")

    check("humidity_pct", conditions.humidity_pct, effective.humidity.min, effective.humidity.max)
    check(
        "cloud_cover_pct",
        conditions.cloud_cover_pct,
        effective.cloud_cover.min,
        effective.cloud_cover.max,
    )
    check(
        "wind_speed_kmh",
        conditions.wind_speed_kmh,
        effective.wind_speed.min,
        effective.wind_speed.max,
    )
    check(
        "wind_gust_kmh",
        conditions.wind_gust_kmh,
        effective.wind_gust.min,
        effective.wind_gust.max,
    )
    check(
        "visibility_km",
        conditions.visibility_km,
        effective.visibility.min,
        effective.visibility.max,
    )
    check("pressure_hpa", conditions.pressure_hpa, effective.pressure.min, effective.pressure.max)

    if conditions.wind_gust_kmh < conditions.wind_speed_kmh:
        raise WeatherInvariantError("wind_gust_kmh is below wind_speed_kmh")
    if conditions.wind_direction not in WIND_DIRECTIONS:
        raise WeatherInvariantError(f"unknown wind direction: {conditions.wind_direction}")
    if "wind_speed_kmh" not in allowed:
        expected = wind_class_for(conditions.wind_speed_kmh)
        if conditions.wind_class != expected:
            raise WeatherInvariantError(
                f"wind_class {conditions.wind_class!r} does not match {expected!r}"
            )

    if conditions.precipitation_type not in PRECIPITATION_TYPES:
        raise WeatherInvariantError(f"unknown precipitation type: {conditions.precipitation_type}")
    if conditions.precipitation_type == PRECIPITATION_NONE:
        if conditions.precipitation_intensity:
            raise WeatherInvariantError("a dry day cannot carry a precipitation intensity")
    elif not conditions.precipitation_intensity:
        raise WeatherInvariantError("a wet day requires a precipitation intensity")


def derive_intraday_seed(day_seed: int, slot_index: int) -> int:
    """Stable seed for one intraday slot of one day."""
    material = f"{day_seed}|{slot_index}".encode("utf-8")
    return int.from_bytes(hashlib.blake2b(material, digest_size=8).digest(), "big")


def generate_intraday_update(
    *,
    daily: DailyConditions,
    effective: EffectiveMonthProfile,
    slot_index: int,
    seed: int,
    previous: IntradayConditions | None = None,
    defaults: Mapping[str, Any] | None = None,
) -> IntradayConditions:
    """Refresh part of the day without contradicting the daily snapshot.

    The precipitation *type* and the daily min/max are binding: an intraday slot
    may vary the intensity by one step, never invent rain on a dry day nor push
    the temperature outside the day envelope.
    """
    if slot_index < 0:
        raise WeatherInvariantError("slot_index cannot be negative")

    rng = Random(seed)

    anchor = previous.temp_current_c if previous is not None else daily.temp_current_c
    temp_current = _clamp(anchor + rng.uniform(-1.5, 1.5), daily.temp_min_c, daily.temp_max_c)

    precipitation_type = daily.precipitation_type
    if precipitation_type == PRECIPITATION_NONE:
        intensity = ""
        intensity_index = 0
    else:
        table = SNOW_INTENSITY if precipitation_type == PRECIPITATION_SNOW else RAIN_INTENSITY
        base = table.index(daily.precipitation_intensity)
        step = rng.choice((-1, 0, 0, 0, 1))
        intensity_index = max(0, min(len(table) - 1, base + step))
        intensity = table[intensity_index]

    wind = _clamp(
        daily.wind_speed_kmh * rng.uniform(0.75, 1.15),
        effective.wind_speed.min,
        effective.wind_speed.max,
    )
    gust = _clamp(
        daily.wind_gust_kmh * rng.uniform(0.75, 1.15),
        effective.wind_gust.min,
        effective.wind_gust.max,
    )
    gust = max(gust, wind)

    humidity = _clamp(
        daily.humidity_pct + rng.uniform(-6.0, 6.0),
        effective.humidity.min,
        effective.humidity.max,
    )
    cloud = _clamp(
        daily.cloud_cover_pct + rng.uniform(-10.0, 10.0),
        effective.cloud_cover.min,
        effective.cloud_cover.max,
    )
    pressure = _clamp(
        daily.pressure_hpa + rng.uniform(-2.0, 2.0),
        effective.pressure.min,
        effective.pressure.max,
    )

    features = [
        feature
        for feature in daily.features
        if feature != FEATURE_LIGHTNING or intensity_index >= 4
    ]
    has_fog = FEATURE_FOG in features

    visibility = effective.visibility.max
    if precipitation_type != PRECIPITATION_NONE:
        visibility *= 1.0 - 0.12 * (intensity_index + 1)
    if has_fog:
        visibility = min(visibility, effective.visibility.max * 0.25)
    visibility = _clamp(visibility, effective.visibility.min, effective.visibility.max)

    direction = daily.wind_direction
    if rng.random() < 0.2:
        index = WIND_DIRECTIONS.index(direction)
        direction = WIND_DIRECTIONS[(index + rng.choice((-1, 1))) % len(WIND_DIRECTIONS)]

    is_wet = precipitation_type != PRECIPITATION_NONE
    cloud_label = _cloud_label_for(cloud, is_wet)

    update = IntradayConditions(
        local_date=daily.local_date,
        slot_index=slot_index,
        temp_current_c=round(temp_current, 1),
        precipitation_type=precipitation_type,
        precipitation_intensity=intensity,
        humidity_pct=round(humidity, 1),
        wind_speed_kmh=round(wind, 1),
        wind_gust_kmh=round(max(gust, wind), 1),
        wind_direction=direction,
        wind_class=wind_class_for(round(wind, 1)),
        cloud_cover_pct=round(cloud, 1),
        visibility_km=round(visibility, 1),
        pressure_hpa=round(pressure, 1),
        condition=_condition_text(cloud_label, intensity, features),
        features=tuple(features),
        seed=seed,
    )

    validate_intraday(update, daily=daily, effective=effective)
    return update


def validate_intraday(
    update: IntradayConditions,
    *,
    daily: DailyConditions,
    effective: EffectiveMonthProfile,
) -> None:
    """An intraday slot must stay inside the day it belongs to."""
    if update.local_date != daily.local_date:
        raise WeatherInvariantError("intraday update belongs to a different day")
    if update.slot_index < 0:
        raise WeatherInvariantError("slot_index cannot be negative")
    if not daily.temp_min_c <= update.temp_current_c <= daily.temp_max_c:
        raise WeatherInvariantError("intraday temperature outside the daily min/max")
    if update.wind_gust_kmh < update.wind_speed_kmh:
        raise WeatherInvariantError("intraday gust is below the sustained wind")
    if update.precipitation_type != daily.precipitation_type:
        raise WeatherInvariantError("intraday update cannot change the precipitation type")
    if update.precipitation_type == PRECIPITATION_NONE:
        if update.precipitation_intensity:
            raise WeatherInvariantError("a dry slot cannot carry an intensity")
    elif not update.precipitation_intensity:
        raise WeatherInvariantError("a wet slot requires an intensity")

    for field, value, low, high in (
        ("humidity_pct", update.humidity_pct, effective.humidity.min, effective.humidity.max),
        (
            "cloud_cover_pct",
            update.cloud_cover_pct,
            effective.cloud_cover.min,
            effective.cloud_cover.max,
        ),
        (
            "wind_speed_kmh",
            update.wind_speed_kmh,
            effective.wind_speed.min,
            effective.wind_speed.max,
        ),
        ("wind_gust_kmh", update.wind_gust_kmh, effective.wind_gust.min, effective.wind_gust.max),
        ("visibility_km", update.visibility_km, effective.visibility.min, effective.visibility.max),
        ("pressure_hpa", update.pressure_hpa, effective.pressure.min, effective.pressure.max),
    ):
        if not low <= value <= high:
            raise WeatherInvariantError(f"{field}={value} outside the hard range {low}..{high}")
