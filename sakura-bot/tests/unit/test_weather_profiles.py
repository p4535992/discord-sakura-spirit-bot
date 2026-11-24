"""Regression tests for the operational climate profiles.

``climate_profiles.json`` is derived from ``climate_catalog.json`` by
``scripts/build_operational_profiles.py``. The catalog keeps the workbook's
``RANDBETWEEN`` snapshots; the profiles are the *stable* monthly ranges the
engine is allowed to use, and they declare the provenance of every field.

The tests pin the properties the engine relies on:

* twelve presets, twelve months each, resolvable by slug, id or alias;
* ``cold <= avg <= hot`` and every range ordered and physically plausible;
* the workbook digest still matches the catalog it was derived from;
* a channel override wins over the preset and is recorded as such, while an
  impossible override is rejected when it is saved.
"""

import hashlib
import json
from pathlib import Path

import pytest
from systems.weather.profiles import (
    GLOBAL_BOUNDS,
    PERCENT_FIELDS,
    ClimateProfile,
    NumericRange,
    ProfileValidationError,
    UnknownProfileError,
    load_profiles,
    resolve_effective_profile,
    validate_overrides,
)

WEATHER_DIR = Path(__file__).resolve().parents[2] / "systems" / "weather"
PROFILES_PATH = WEATHER_DIR / "climate_profiles.json"
CATALOG_PATH = WEATHER_DIR / "climate_catalog.json"

PROVENANCE_VALUES = {
    "excel_static",
    "project_default",
    "project_default_derived_from_randomized_snapshot",
}


@pytest.fixture(scope="module")
def catalog():
    return load_profiles()


@pytest.fixture(scope="module")
def raw_profiles():
    return json.loads(PROFILES_PATH.read_text(encoding="utf-8"))


def test_profiles_file_is_committed_next_to_the_catalog():
    assert PROFILES_PATH.is_file(), f"missing {PROFILES_PATH.name}"
    assert CATALOG_PATH.is_file(), f"missing {CATALOG_PATH.name}"


def test_catalog_has_twelve_climates_with_twelve_months(catalog):
    assert len(catalog) == 12

    for climate in catalog:
        assert len(climate.months) == 12
        assert [month.month for month in climate.months] == list(range(1, 13))


def test_presets_resolve_by_slug_id_and_alias(catalog):
    desert = catalog.get("desertico")

    assert isinstance(desert, ClimateProfile)
    assert catalog.get("DESERTICO") is desert
    assert catalog.get(desert.id) is desert

    for alias in desert.aliases:
        assert catalog.get(alias) is desert


def test_unknown_preset_is_rejected(catalog):
    with pytest.raises(UnknownProfileError):
        catalog.get("clima-inventato")

    with pytest.raises(UnknownProfileError):
        catalog.get("")


def test_temperature_references_are_ordered(catalog):
    for climate in catalog:
        for month in climate.months:
            assert month.temp_cold_c <= month.temp_avg_c <= month.temp_hot_c, (
                climate.slug,
                month.month,
            )


def test_every_range_is_ordered_and_physical(catalog):
    for climate in catalog:
        for month in climate.months:
            for name in ("humidity", "wind_speed", "cloud_cover", "visibility", "pressure"):
                span = getattr(month, name)
                assert isinstance(span, NumericRange)
                assert span.min <= span.max, (climate.slug, month.month, name)

            assert 0.0 <= month.precipitation_probability <= 1.0
            assert 0.0 <= month.humidity.min and month.humidity.max <= 100.0
            assert 0.0 <= month.cloud_cover.min and month.cloud_cover.max <= 100.0
            assert month.wind_speed.min >= 0.0
            assert month.wind_gust_max_kmh >= month.wind_speed.min
            assert month.visibility.min >= 0.0


def test_provenance_is_declared_for_every_field(catalog):
    for climate in catalog:
        assert climate.field_provenance
        for field, source in climate.field_provenance.items():
            assert source in PROVENANCE_VALUES, (climate.slug, field, source)


def test_precipitation_probability_is_static_workbook_data(catalog):
    """The matrix is a fixed table, not a recalculated cell."""
    for climate in catalog:
        assert climate.field_provenance["precipitation_probability"] == "excel_static", climate.slug


def test_profiles_track_the_catalog_they_were_derived_from(catalog):
    catalog_payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

    assert catalog.source_catalog_sha256 == hashlib.sha256(CATALOG_PATH.read_bytes()).hexdigest()
    assert catalog.source_workbook_sha256 == catalog_payload["source"]["sha256"]


def test_effective_profile_falls_back_to_the_preset(catalog):
    climate = catalog.get("desertico")
    month = climate.month(1)
    effective = resolve_effective_profile(climate, 1)

    assert effective.temp_min == NumericRange(month.temp_cold_c, month.temp_avg_c)
    assert effective.temp_max == NumericRange(month.temp_avg_c, month.temp_hot_c)
    assert effective.humidity == month.humidity
    assert effective.wind_gust == NumericRange(month.wind_speed.min, month.wind_gust_max_kmh)
    assert effective.precipitation_probability == month.precipitation_probability
    assert effective.overrides_applied == ()
    assert "admin_override" not in effective.provenance.values()


def test_override_wins_and_is_recorded(catalog):
    climate = catalog.get("desertico")
    effective = resolve_effective_profile(climate, 1, {"humidity_pct": {"min": 7, "max": 28}})

    assert effective.humidity == NumericRange(7.0, 28.0)
    assert effective.overrides_applied == ("humidity_pct",)
    assert effective.provenance["humidity_pct"] == "admin_override"
    assert effective.provenance["temp_min_c"] != "admin_override"


def test_override_can_widen_a_range_within_the_physical_bounds(catalog):
    climate = catalog.get("polare")
    month = climate.month(1)
    effective = resolve_effective_profile(climate, 1, {"temp_max_c": {"min": -60.0, "max": 10.0}})

    assert effective.temp_max.min < month.temp_avg_c
    assert effective.temp_max.max > month.temp_hot_c
    assert effective.temp_max.max <= GLOBAL_BOUNDS["temp_max_c"][1]


def test_precipitation_override_is_clamped_not_sampled(catalog):
    """The override narrows the month's probability; it is not a random draw."""
    wet = catalog.get("monsonico")
    dry = catalog.get("desertico")

    narrowed = resolve_effective_profile(
        wet, 7, {"precipitation_probability_pct": {"min": 0, "max": 5}}
    )
    assert narrowed.precipitation_probability == pytest.approx(0.05)

    raised = resolve_effective_profile(
        dry, 1, {"precipitation_probability_pct": {"min": 40, "max": 60}}
    )
    assert raised.precipitation_probability == pytest.approx(0.40)


def test_override_rejects_an_inverted_range():
    with pytest.raises(ProfileValidationError):
        validate_overrides({"humidity_pct": {"min": 80, "max": 20}})


def test_override_rejects_an_unknown_parameter():
    with pytest.raises(ProfileValidationError):
        validate_overrides({"temperature": {"min": 1, "max": 2}})


def test_override_rejects_values_outside_the_physical_bounds():
    low, high = GLOBAL_BOUNDS["pressure_hpa"]

    with pytest.raises(ProfileValidationError):
        validate_overrides({"pressure_hpa": {"min": low - 10, "max": high}})

    for field in PERCENT_FIELDS:
        with pytest.raises(ProfileValidationError):
            validate_overrides({field: {"min": 0, "max": 101}})


def test_override_rejects_a_gust_below_the_sustained_wind():
    with pytest.raises(ProfileValidationError):
        validate_overrides(
            {
                "wind_speed_kmh": {"min": 0, "max": 60},
                "wind_gust_kmh": {"min": 0, "max": 40},
            }
        )


def test_override_rejects_a_temperature_envelope_that_cannot_close():
    with pytest.raises(ProfileValidationError):
        validate_overrides(
            {
                "temp_min_c": {"min": 30, "max": 40},
                "temp_max_c": {"min": 0, "max": 10},
            }
        )


def test_effective_profile_serialises_every_field(catalog):
    payload = resolve_effective_profile(catalog.get("tundra"), 12).to_dict()

    for key in (
        "preset",
        "preset_version",
        "month",
        "precipitation_probability",
        "temp_min_c",
        "temp_max_c",
        "humidity_pct",
        "wind_speed_kmh",
        "wind_gust_kmh",
        "cloud_cover_pct",
        "visibility_km",
        "pressure_hpa",
        "preferred_wind_directions",
        "overrides_applied",
        "provenance",
    ):
        assert key in payload

    assert payload["month"] == 12
    assert payload["preset"] == "tundra"


def test_loader_rejects_an_unsupported_schema(tmp_path, raw_profiles):
    broken = tmp_path / "profiles.json"
    broken.write_text(json.dumps({**raw_profiles, "schema_version": 2}), encoding="utf-8")

    with pytest.raises(ProfileValidationError):
        load_profiles(broken)


def test_loader_rejects_an_incomplete_catalog(tmp_path, raw_profiles):
    broken = tmp_path / "profiles.json"
    broken.write_text(
        json.dumps({**raw_profiles, "climates": raw_profiles["climates"][:-1]}),
        encoding="utf-8",
    )

    with pytest.raises(ProfileValidationError):
        load_profiles(broken)
