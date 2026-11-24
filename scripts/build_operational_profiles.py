#!/usr/bin/env python3
"""Build the operational climate profiles from the versioned catalog.

The workbook catalog (``climate_catalog.json``) mixes two kinds of data:

* static values, such as the monthly ``Precip`` probability, that survive a
  recalculation of the spreadsheet;
* cells driven by ``RANDBETWEEN`` (``Cold``/``Avg``/``Hot``), which change every
  time the workbook recalculates and are therefore recorded as snapshots.

The engine cannot use a snapshot as a climate normal. This script derives a
separate, stable, versioned profile set and records the provenance of every
field, so nothing downstream can present a randomized sample as a hard limit.

Derivation rules (all ``project_default`` unless stated otherwise):

* ``precipitation_probability`` - ``excel_static``, copied from the catalog;
* ``temp_avg_c`` - the catalog ``avg_c`` snapshot, kept as the reference;
* ``temp_cold_c``/``temp_hot_c`` - the snapshot envelope, widened only when it
  would cross the workbook inner bound (``Settings!Temp inner bound``);
* ``humidity_*`` - ``25 + 60 * p`` with a -15/+20 spread, clamped to 5..100;
* ``wind_*`` - per climate family (calm, moderate, windy, cold), gusts at 1.6x;
* ``cloud_cover_*`` - ``50 * p`` .. ``50 + 50 * p``, clamped to 0..100;
* ``visibility_*`` - ``2`` .. ``40 - 25 * p`` km;
* ``pressure_*`` - 985..1035 hPa for every climate.

Run from the repository root::

    .\\.venv\\Scripts\\python.exe scripts\\build_operational_profiles.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

SCHEMA_VERSION = 1
DEFAULT_CATALOG = Path("sakura-bot/systems/weather/climate_catalog.json")
DEFAULT_OUTPUT = Path("sakura-bot/systems/weather/climate_profiles.json")

# Public slugs and friendly aliases from the implementation brief, section 4.1.
CLIMATE_METADATA = {
    "desert": {
        "slug": "desertico",
        "display_name": "Deserto",
        "aliases": ["arid-desert", "deserto"],
        "family": "windy",
    },
    "tropical-savanna": {
        "slug": "savana-tropicale",
        "display_name": "Savana tropicale",
        "aliases": ["tropicale-secco"],
        "family": "moderate",
    },
    "steppes": {
        "slug": "steppico",
        "display_name": "Steppa",
        "aliases": ["semi-arido", "arido"],
        "family": "windy",
    },
    "equatorial": {
        "slug": "equatoriale",
        "display_name": "Equatoriale",
        "aliases": ["tropicale-umido", "tropicale"],
        "family": "calm",
    },
    "monsoon": {
        "slug": "monsonico",
        "display_name": "Monsonico",
        "aliases": ["monsone"],
        "family": "calm",
    },
    "warm-and-rainy": {
        "slug": "caldo-piovoso",
        "display_name": "Caldo e piovoso",
        "aliases": ["caldo-umido"],
        "family": "calm",
    },
    "warm-with-dry-summer": {
        "slug": "estate-secca",
        "display_name": "Estate secca",
        "aliases": ["mediterraneo"],
        "family": "moderate",
    },
    "warm-with-dry-winter": {
        "slug": "inverno-secco",
        "display_name": "Inverno secco",
        "aliases": ["subtropicale-inverno-secco"],
        "family": "moderate",
    },
    "cool-and-rainy": {
        "slug": "fresco-piovoso",
        "display_name": "Fresco e piovoso",
        "aliases": ["fresco-umido"],
        "family": "calm",
    },
    "cool-with-dry-winter": {
        "slug": "fresco-inverno-secco",
        "display_name": "Fresco con inverno secco",
        "aliases": ["inverno-secco-fresco"],
        "family": "moderate",
    },
    "tundra": {
        "slug": "tundra",
        "display_name": "Tundra",
        "aliases": ["subpolare"],
        "family": "cold",
    },
    "polar": {
        "slug": "polare",
        "display_name": "Polare",
        "aliases": ["artico"],
        "family": "cold",
    },
}
# Wind ranges in km/h per family: a project default, not an Excel value.
WIND_BY_FAMILY = {
    "calm": (5.0, 25.0),
    "moderate": (8.0, 32.0),
    "windy": (10.0, 40.0),
    "cold": (15.0, 45.0),
}

GUST_FACTOR = 1.6
PRESSURE_RANGE_HPA = (985.0, 1035.0)
VISIBILITY_MIN_KM = 2.0
VISIBILITY_MAX_BASE_KM = 40.0
VISIBILITY_WET_REDUCTION_KM = 25.0

FIELD_PROVENANCE = {
    "precipitation_probability": "excel_static",
    "temp_avg_c": "project_default_derived_from_randomized_snapshot",
    "temp_cold_c": "project_default_derived_from_randomized_snapshot",
    "temp_hot_c": "project_default_derived_from_randomized_snapshot",
    "humidity_min_pct": "project_default",
    "humidity_max_pct": "project_default",
    "wind_speed_min_kmh": "project_default",
    "wind_speed_max_kmh": "project_default",
    "wind_gust_max_kmh": "project_default",
    "cloud_cover_min_pct": "project_default",
    "cloud_cover_max_pct": "project_default",
    "visibility_min_km": "project_default",
    "visibility_max_km": "project_default",
    "pressure_min_hpa": "project_default",
    "pressure_max_hpa": "project_default",
    "preferred_wind_directions": "project_default",
}

DERIVATION_NOTES = {
    "precipitation_probability": "Climates!<month> Precip column, unchanged (static).",
    "temp_avg_c": "Catalog avg_c snapshot used as the daily reference, not as a normal.",
    "temp_cold_c": "min(cold_c, avg_c - inner_bound): the envelope never crosses the core.",
    "temp_hot_c": "max(hot_c, avg_c + inner_bound): the envelope never crosses the core.",
    "humidity_pct": "base = 25 + 60 * p; min = base - 15; max = base + 20; clamped.",
    "wind_kmh": "Family range: calm 5-25, moderate 8-32, windy 10-40, cold 15-45.",
    "wind_gust_kmh": "1.6 * wind_speed_max_kmh.",
    "cloud_cover_pct": "min = 50 * p; max = 50 + 50 * p; clamped to 0..100.",
    "visibility_km": "2 .. 40 - 25 * p, so wetter climates see less far.",
    "pressure_hpa": "985..1035 hPa for every climate (project default).",
}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def build_month(month: dict, family: str, inner_bound: float) -> dict:
    """Return one operational month profile for a climate family."""
    probability = float(month["precipitation_probability"])
    avg_c = float(month["avg_c"])
    cold_c = min(float(month["cold_c"]), avg_c - inner_bound)
    hot_c = max(float(month["hot_c"]), avg_c + inner_bound)

    humidity_base = 25.0 + 60.0 * probability
    humidity_min = _clamp(round(humidity_base - 15.0), 5.0, 95.0)
    humidity_max = _clamp(round(humidity_base + 20.0), humidity_min + 5.0, 100.0)

    wind_min, wind_max = WIND_BY_FAMILY[family]

    cloud_min = _clamp(round(50.0 * probability), 0.0, 90.0)
    cloud_max = _clamp(round(50.0 + 50.0 * probability), cloud_min + 10.0, 100.0)

    visibility_max = round(VISIBILITY_MAX_BASE_KM - VISIBILITY_WET_REDUCTION_KM * probability, 1)

    return {
        "month": int(month["month"]),
        "name": month["name"],
        "precipitation_probability": round(probability, 4),
        "temp_cold_c": round(cold_c, 1),
        "temp_avg_c": round(avg_c, 1),
        "temp_hot_c": round(hot_c, 1),
        "humidity_min_pct": int(humidity_min),
        "humidity_max_pct": int(humidity_max),
        "wind_speed_min_kmh": wind_min,
        "wind_speed_max_kmh": wind_max,
        "wind_gust_max_kmh": round(wind_max * GUST_FACTOR, 1),
        "cloud_cover_min_pct": int(cloud_min),
        "cloud_cover_max_pct": int(cloud_max),
        "visibility_min_km": VISIBILITY_MIN_KM,
        "visibility_max_km": visibility_max,
        "pressure_min_hpa": PRESSURE_RANGE_HPA[0],
        "pressure_max_hpa": PRESSURE_RANGE_HPA[1],
        "preferred_wind_directions": [],
    }
def build_profiles(catalog: dict, catalog_bytes: bytes) -> dict:
    settings = catalog["settings"]
    inner_bound = float(settings["temp_inner_bound_c"])

    climates = []
    seen_slugs = set()
    for climate in catalog["climates"]:
        climate_id = climate["id"]
        if climate_id not in CLIMATE_METADATA:
            raise SystemExit(f"unknown climate id in catalog: {climate_id}")
        metadata = CLIMATE_METADATA[climate_id]
        if metadata["slug"] in seen_slugs:
            raise SystemExit(f"duplicate slug: {metadata['slug']}")
        seen_slugs.add(metadata["slug"])

        months = [
            build_month(month, metadata["family"], inner_bound) for month in climate["months"]
        ]
        if len(months) != 12:
            raise SystemExit(f"{climate_id}: expected 12 months, found {len(months)}")

        climates.append(
            {
                "id": climate_id,
                "slug": metadata["slug"],
                "display_name": metadata["display_name"],
                "aliases": metadata["aliases"],
                "family": metadata["family"],
                "source": f"Excel:RPG Weather Dnd5e.xlsx/Climates/{climate['source_name']}",
                "hemisphere": "north",
                "version": 1,
                "field_provenance": dict(FIELD_PROVENANCE),
                "months": months,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "scripts/build_operational_profiles.py",
        "source_catalog": DEFAULT_CATALOG.as_posix(),
        "source_catalog_sha256": hashlib.sha256(catalog_bytes).hexdigest(),
        "source_workbook_sha256": catalog["source"]["sha256"],
        "defaults": {
            "temp_outer_bound_c": float(settings["temp_outer_bound_c"]),
            "temp_inner_bound_c": inner_bound,
            "freezing_point_c": float(settings["freezing_point_c"]),
            "chance_fog_for_rain": float(settings["chance_fog_for_rain"]),
            "chance_lightning_for_storm": float(settings["chance_lightning_for_storm"]),
            "chance_hail_for_rain": float(settings["chance_hail_for_rain"]),
            "chance_hail_for_storm": float(settings["chance_hail_for_storm"]),
            "hemisphere": "north",
        },
        "provenance_legend": {
            "excel_static": "Read from the workbook and unchanged by a recalculation.",
            "project_default_derived_from_randomized_snapshot": (
                "Project default inspired by a RANDBETWEEN snapshot; never a climate normal."
            ),
            "project_default": "Chosen by the project; absent from the workbook.",
            "admin_override": "Set by a guild administrator for one channel.",
        },
        "derivation": DERIVATION_NOTES,
        "climates": climates,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    catalog_bytes = args.catalog.read_bytes()
    catalog = json.loads(catalog_bytes.decode("utf-8"))

    profiles = build_profiles(catalog, catalog_bytes)
    args.output.write_text(
        json.dumps(profiles, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(
        f"wrote {args.output} ({args.output.stat().st_size} bytes, "
        f"{len(profiles['climates'])} climates x 12 months)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
