"""Regression tests for the versioned climate catalog.

The catalog in ``systems/weather`` is generated from the historical
``RPG Weather Dnd5e.xlsx`` workbook, which is committed in
``docs/xlsx/RPG Weather Dnd5e.xlsx``. The tests validate the committed catalog
artifact and, through ``source.sha256``, the provenance of the workbook:

* the monthly precipitation matrix is the 12x12 table documented in
  ``docs/WEATHER_SOURCE_MAPPING.md`` and read from ``Climates``;
* the thirteen wind classes are ordered, non-overlapping and converted to km/h;
* the temperature references keep ``cold <= avg <= hot`` and convert from
  Fahrenheit with the documented formula;
* the fields the workbook randomizes on every recalculation are declared as
  snapshots, so nothing downstream can mistake them for canonical normals.
"""

import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest

CATALOG_PATH = (
    Path(__file__).resolve().parents[2] / "systems" / "weather" / "climate_catalog.json"
)
# The extractor lives outside the application package. The Docker test runner
# mounts the clone (or the ``scripts`` folder) under ``SAKURA_REPOSITORY_ROOT``,
# so the same expression resolves on the host and inside the container instead
# of pointing at a non-existent ``/scripts`` path.
REPOSITORY_ROOT = Path(
    os.environ.get("SAKURA_REPOSITORY_ROOT") or Path(__file__).resolve().parents[3]
)
EXTRACTOR_PATH = REPOSITORY_ROOT / "scripts" / "extract_weather_workbook.py"
WORKBOOK_PATH = REPOSITORY_ROOT / "docs" / "xlsx" / "RPG Weather Dnd5e.xlsx"

# ``Climates!I3:I14`` and the equivalent ``Precip`` column of the other eleven
# climate blocks, expressed as percentages for readability.
EXPECTED_PRECIPITATION_PCT = {
    "desert": [5] * 12,
    "tropical-savanna": [10, 10, 10, 35, 85, 85, 85, 85, 85, 35, 10, 10],
    "steppes": [20, 20, 20, 20, 20, 20, 5, 5, 5, 20, 20, 20],
    "equatorial": [30, 30, 50, 50, 50, 40, 40, 40, 40, 40, 40, 40],
    "monsoon": [15, 15, 15, 15, 15, 90, 90, 90, 90, 90, 15, 15],
    "warm-and-rainy": [40] * 12,
    "warm-with-dry-summer": [30, 30, 30, 30, 30, 10, 10, 10, 30, 30, 30, 30],
    "warm-with-dry-winter": [15, 15, 15, 15, 15, 15, 45, 45, 15, 15, 15, 15],
    "cool-and-rainy": [35] * 12,
    "cool-with-dry-winter": [10, 10, 10, 10, 20, 20, 35, 35, 35, 20, 10, 10],
    "tundra": [10] * 12,
    "polar": [10] * 12,
}

EXPECTED_RAIN_INTENSITY = [
    "Light mist",
    "Drizzle",
    "Steady rainfall",
    "Strong rainfall",
    "Pounding rain",
    "Downpour",
]
EXPECTED_SNOW_INTENSITY = [
    "A few flakes",
    "Dusting of snow",
    "Flurries",
    "Moderate snowfall",
    "Heavy snowfall",
    "Blizzard",
]
EXPECTED_CLOUD_COVER = [
    "A few clouds",
    "Mostly cloudy",
    "Gray, slightly overcast",
    "Gray, highly overcast",
    "Dark storm clouds",
]
EXPECTED_DIRECTIONS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


@pytest.fixture(scope="module")
def catalog():
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def climates_by_id(catalog):
    return {climate["id"]: climate for climate in catalog["climates"]}


def test_catalog_declares_its_source(catalog):
    assert catalog["schema_version"] == 1
    assert catalog["source"]["workbook"] == "RPG Weather Dnd5e.xlsx"
    assert len(catalog["source"]["sha256"]) == 64
    assert catalog["source"]["sheets"] == [
        "Year of Weather",
        "Settings",
        "Climates",
        "Precipitation",
        "Wind",
    ]


def test_twelve_climates_with_twelve_months(catalog, climates_by_id):
    assert len(catalog["climates"]) == 12
    assert set(climates_by_id) == set(EXPECTED_PRECIPITATION_PCT)

    for climate_id, climate in climates_by_id.items():
        months = climate["months"]
        assert [month["month"] for month in months] == list(range(1, 13)), climate_id
        assert months[0]["name"] == "January", climate_id
        assert months[11]["name"] == "December", climate_id


def test_precipitation_matrix_matches_the_workbook(climates_by_id):
    for climate_id, expected in EXPECTED_PRECIPITATION_PCT.items():
        actual = [
            month["precipitation_probability_pct"]
            for month in climates_by_id[climate_id]["months"]
        ]
        assert actual == [float(value) for value in expected], climate_id


def test_precipitation_probability_is_also_stored_as_a_fraction(climates_by_id):
    for climate in climates_by_id.values():
        for month in climate["months"]:
            assert month["precipitation_probability"] == pytest.approx(
                month["precipitation_probability_pct"] / 100
            )
            assert 0.0 <= month["precipitation_probability"] <= 1.0


def test_temperature_references_are_ordered(climates_by_id):
    for climate_id, climate in climates_by_id.items():
        for month in climate["months"]:
            label = f"{climate_id} month {month['month']}"
            assert month["cold_f"] <= month["avg_f"] <= month["hot_f"], label
            assert month["cold_c"] <= month["avg_c"] <= month["hot_c"], label


def test_temperature_references_convert_from_fahrenheit(climates_by_id):
    for climate in climates_by_id.values():
        for month in climate["months"]:
            for scale in ("cold", "avg", "hot"):
                expected = (month[f"{scale}_f"] - 32.0) * 5.0 / 9.0
                assert month[f"{scale}_c"] == pytest.approx(expected, abs=0.05)


def test_wind_classes_are_ordered_and_do_not_overlap(catalog):
    wind = catalog["wind"]

    assert len(wind) == 13
    assert [entry["index"] for entry in wind] == list(range(1, 14))
    assert wind[0]["name"] == "Calm"
    assert wind[-1]["name"] == "Hurricane"

    for entry in wind:
        assert entry["mph_min"] <= entry["mph_max"], entry["name"]

    for previous, current in zip(wind, wind[1:]):
        assert current["mph_min"] > previous["mph_max"], (previous["name"], current["name"])


def test_wind_classes_convert_to_kmh(catalog):
    for entry in catalog["wind"]:
        assert entry["kmh_min"] == pytest.approx(entry["mph_min"] * 1.609344, abs=0.1)
        assert entry["kmh_max"] == pytest.approx(entry["mph_max"] * 1.609344, abs=0.1)


def test_wind_lookup_thresholds_are_not_probabilities(catalog):
    """``Wind!Chance`` is a VLOOKUP threshold, never a 0-100 percentage."""
    thresholds = [entry["lookup_threshold"] for entry in catalog["wind"]]

    assert thresholds == sorted(thresholds)
    assert max(thresholds) > 100


def test_precipitation_vocabularies(catalog):
    precipitation = catalog["precipitation"]

    assert precipitation["rain_intensity"] == EXPECTED_RAIN_INTENSITY
    assert precipitation["snow_intensity"] == EXPECTED_SNOW_INTENSITY
    assert precipitation["cloud_cover"] == EXPECTED_CLOUD_COVER
    assert precipitation["directions"] == EXPECTED_DIRECTIONS
    assert sorted(precipitation["features"]) == ["Fog", "Hail", "Lightning", "Lightning, hail"]


def test_precipitation_sheet_shape(catalog):
    precipitation = catalog["precipitation"]
    counts = precipitation["observed_counts"]

    assert precipitation["observed_row_count"] == 996
    assert [counts["rain_intensity"][label] for label in EXPECTED_RAIN_INTENSITY] == [166] * 6
    assert [counts["snow_intensity"][label] for label in EXPECTED_SNOW_INTENSITY] == [166] * 6


def test_settings_match_the_workbook(catalog):
    settings = catalog["settings"]

    assert settings["temperature_units"] == "Celsius"
    assert settings["freezing_point_c"] == 0.0
    assert settings["temp_outer_bound_c"] == 7.0
    assert settings["temp_inner_bound_c"] == 2.0
    assert settings["chance_fog_for_rain"] == pytest.approx(0.15)
    assert settings["chance_lightning_for_storm"] == pytest.approx(0.25)
    assert settings["chance_hail_for_rain"] == pytest.approx(0.10)
    assert settings["chance_hail_for_storm"] == pytest.approx(0.20)
    assert settings["month_lengths"]["February"] == 28
    assert len(settings["month_lengths"]) == 12


def test_clear_sky_distribution_is_recovered(catalog):
    choices = [entry["label"] for entry in catalog["settings"]["clear_sky_choices"]]

    assert choices == ["Clear", "Clear", "A few clouds", "Mostly cloudy"]


def test_randomized_fields_are_declared_as_snapshots(catalog):
    """The workbook recalculates these cells, so they must never be treated as normals."""
    randomized = catalog["stability"]["randomized_snapshot"]

    assert "climates[].months[].cold_f" in randomized
    assert "climates[].months[].avg_f" in randomized
    assert "climates[].months[].hot_f" in randomized
    assert "climates[].months[].precipitation_probability" not in randomized


def test_extractor_is_available_where_the_tests_run():
    """The Docker runner must mount ``scripts/``: a missing path is a failure."""
    assert EXTRACTOR_PATH.is_file(), f"extractor not found at {EXTRACTOR_PATH}"


def test_committed_workbook_matches_the_catalog_digest(catalog):
    """The workbook is versioned: its bytes must still match ``source.sha256``."""
    assert WORKBOOK_PATH.is_file(), f"workbook not found at {WORKBOOK_PATH}"

    digest = hashlib.sha256(WORKBOOK_PATH.read_bytes()).hexdigest()

    assert digest == catalog["source"]["sha256"]
    assert WORKBOOK_PATH.stat().st_size == catalog["source"]["size_bytes"]


def test_extractor_parses_open_ended_mph_ranges():
    """The extractor reads the workbook's en-dash ranges, including ``<1``."""
    spec = importlib.util.spec_from_file_location("extract_weather_workbook", EXTRACTOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.parse_mph_range("<1") == (0.0, 0.99)
    assert module.parse_mph_range("1\u20133") == (1.0, 3.0)
    assert module.parse_mph_range("73\u2013136") == (73.0, 136.0)

    with pytest.raises(ValueError):
        module.parse_mph_range("strong")
