#!/usr/bin/env python3
"""Extract the ``RPG Weather Dnd5e.xlsx`` workbook into a versioned JSON catalog.

The workbook is the historical source of the Sakura climate presets. It is a
live spreadsheet: many cells are ``RANDBETWEEN`` formulas that produce a new
value on every recalculation, so the file can neither be used as a runtime
engine nor be treated as a stable data source as a whole. This script therefore
separates two kinds of output:

* **static** values, reproducible from the workbook: the monthly precipitation
  probabilities, the thirteen wind classes, the precipitation/cloud/feature
  vocabularies and the eight compass directions;
* **randomized snapshots**, recorded as evidence of one particular
  recalculation only: the ``Cold``/``Avg``/``Hot`` temperature references and
  the observed wind/direction/feature counts of the ``Precipitation`` sheet.

Only the Python standard library is used. The project does not depend on
``openpyxl`` and adding a dependency to read a single file is not justified.

Usage::

    python scripts/extract_weather_workbook.py --source "RPG Weather Dnd5e.xlsx"
    python scripts/extract_weather_workbook.py --source <xlsx> --output <json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

MPH_TO_KMH = 1.609344

DEFAULT_OUTPUT = (
    Path(__file__).resolve().parent.parent
    / "sakura-bot"
    / "systems"
    / "weather"
    / "climate_catalog.json"
)

# Column offsets inside a six-column climate block of the ``Climates`` sheet.
TEMP_OFFSET = 1
COLD_OFFSET = 2
AVG_OFFSET = 3
HOT_OFFSET = 4
PRECIP_OFFSET = 5
FIRST_MONTH_ROW = 3
MAX_MONTHS = 24


class Cell:
    """One worksheet cell: cached value plus the formula that produced it."""

    __slots__ = ("ref", "value", "formula")

    def __init__(self, ref: str, value: object, formula: str | None) -> None:
        self.ref = ref
        self.value = value
        self.formula = formula

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Cell {self.ref}={self.value!r}>"


def column_letters(ref: str) -> str:
    return "".join(ch for ch in ref if ch.isalpha())


def column_index(ref: str) -> int:
    index = 0
    for ch in column_letters(ref):
        index = index * 26 + (ord(ch.upper()) - 64)
    return index


def row_index(ref: str) -> int:
    return int("".join(ch for ch in ref if ch.isdigit()))


def ref_for(column: int) -> str:
    """Turn a one-based column number into its spreadsheet letters."""
    letters = ""
    while column:
        column, remainder = divmod(column - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


class Workbook:
    """Minimal read-only ``.xlsx`` reader built on ``zipfile`` and ``ElementTree``."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._zip = zipfile.ZipFile(self.path)
        self._strings = self._read_shared_strings()
        self._sheet_targets = self._read_sheet_targets()

    def close(self) -> None:
        self._zip.close()

    def __enter__(self) -> "Workbook":
        return self

    def __exit__(self, *exc_info: object) -> bool:
        self.close()
        return False

    @property
    def sheet_names(self) -> list[str]:
        return list(self._sheet_targets)

    def _read_shared_strings(self) -> list[str]:
        try:
            raw = self._zip.read("xl/sharedStrings.xml")
        except KeyError:
            return []
        root = ET.fromstring(raw)
        return [
            "".join(node.text or "" for node in item.iter(f"{{{MAIN_NS}}}t"))
            for item in root.findall(f"{{{MAIN_NS}}}si")
        ]

    def _read_sheet_targets(self) -> dict[str, str]:
        workbook = ET.fromstring(self._zip.read("xl/workbook.xml"))
        rels = ET.fromstring(self._zip.read("xl/_rels/workbook.xml.rels"))
        targets = {
            rel.get("Id"): rel.get("Target")
            for rel in rels.findall(f"{{{PKG_REL_NS}}}Relationship")
        }
        sheets: dict[str, str] = {}
        for sheet in workbook.find(f"{{{MAIN_NS}}}sheets"):
            target = targets[sheet.get(f"{{{REL_NS}}}id")].lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            sheets[sheet.get("name")] = target
        return sheets

    def cells(self, sheet_name: str) -> dict[str, Cell]:
        """Return ``{cell reference: Cell}`` for a whole worksheet."""
        root = ET.fromstring(self._zip.read(self._sheet_targets[sheet_name]))
        data = root.find(f"{{{MAIN_NS}}}sheetData")
        cells: dict[str, Cell] = {}
        if data is None:
            return cells
        for row in data.findall(f"{{{MAIN_NS}}}row"):
            for cell in row.findall(f"{{{MAIN_NS}}}c"):
                ref = cell.get("r")
                if not ref:
                    continue
                cells[ref] = Cell(ref, self._cell_value(cell), self._cell_formula(cell))
        return cells

    def _cell_value(self, cell: ET.Element) -> object:
        inline = cell.find(f"{{{MAIN_NS}}}is")
        if inline is not None:
            return "".join(node.text or "" for node in inline.iter(f"{{{MAIN_NS}}}t"))
        value = cell.find(f"{{{MAIN_NS}}}v")
        if value is None or value.text is None:
            return None
        text = value.text
        if cell.get("t") == "s":
            return self._strings[int(text)]
        if cell.get("t") in ("str", "e"):
            return text
        try:
            number = float(text)
        except ValueError:
            return text
        return int(number) if number.is_integer() else number

    def _cell_formula(self, cell: ET.Element) -> str | None:
        formula = cell.find(f"{{{MAIN_NS}}}f")
        if formula is None:
            return None
        return formula.text or ""


def as_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except ValueError:
        return None


def as_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def fahrenheit_to_celsius(value: float) -> float:
    return (value - 32.0) * 5.0 / 9.0


def _to_celsius(value: float | None) -> float | None:
    """Convert a Fahrenheit reference to one-decimal Celsius, tolerating ``None``."""
    if value is None:
        return None
    return round(fahrenheit_to_celsius(value), 1)


def parse_mph_range(label: str) -> tuple[float, float]:
    """Turn ``"<1"``, ``"1–3"`` or ``"73–136"`` into a numeric range."""
    text = label.strip().replace("\u2013", "-").replace("\u2014", "-")
    match = re.fullmatch(r"<\s*(\d+(?:\.\d+)?)", text)
    if match:
        return 0.0, float(match.group(1)) - 0.01
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)", text)
    if match:
        return float(match.group(1)), float(match.group(2))
    raise ValueError(f"Unrecognised mph range: {label!r}")


def read_settings(cells: dict[str, Cell]) -> dict[str, object]:
    """Read the ``Settings`` sheet, asserting the labels so a shifted sheet fails loudly."""
    expected = {
        "D17": "Temperature Units",
        "D19": "Temp outer bound:",
        "D20": "Temp inner bound:",
        "D22": "Chance of fog for rain:",
        "D23": "Chance of lightning for storm:",
        "D24": "Chance of hail for rain:",
        "D25": "Chance of hail for storm:",
    }
    for ref, label in expected.items():
        actual = as_text(cells[ref].value) if ref in cells else None
        if actual != label:
            raise ValueError(f"Settings!{ref} expected {label!r}, found {actual!r}")

    month_lengths: dict[str, int] = {}
    for offset in range(MAX_MONTHS):
        row = 2 + offset
        name = as_text(cells[f"A{row}"].value) if f"A{row}" in cells else None
        if name is None:
            break
        month_lengths[name] = int(as_float(cells[f"B{row}"].value) or 0)

    return {
        "temperature_units": as_text(cells["D18"].value),
        "freezing_point_c": as_float(cells["E18"].value),
        "temp_outer_bound_c": as_float(cells["E19"].value),
        "temp_inner_bound_c": as_float(cells["E20"].value),
        "chance_fog_for_rain": as_float(cells["E22"].value),
        "chance_lightning_for_storm": as_float(cells["E23"].value),
        "chance_hail_for_rain": as_float(cells["E24"].value),
        "chance_hail_for_storm": as_float(cells["E25"].value),
        "latitude": as_float(cells["E2"].value) if "E2" in cells else None,
        "selected_climate": as_text(cells["D2"].value) if "D2" in cells else None,
        "month_lengths": month_lengths,
        "notes": as_text(cells["L3"].value) if "L3" in cells else None,
    }


def read_climate_blocks(cells: dict[str, Cell]) -> list[tuple[int, str]]:
    """Return ``[(first column index, climate name)]`` read from row 1."""
    starts: list[tuple[int, str]] = []
    for ref, cell in cells.items():
        if row_index(ref) != 1:
            continue
        # Row 1 also holds a numeric COUNTA formula in column B: only the
        # repeated text labels mark the beginning of a climate block.
        if not isinstance(cell.value, str):
            continue
        name = as_text(cell.value)
        if name is None:
            continue
        index = column_index(ref)
        if starts and starts[-1][1] == name:
            continue
        starts.append((index, name))
    starts.sort()
    return starts


def read_climates(cells: dict[str, Cell]) -> list[dict[str, object]]:
    climates: list[dict[str, object]] = []
    expected_headers = {
        TEMP_OFFSET: "Temp",
        COLD_OFFSET: "Cold",
        AVG_OFFSET: "Avg",
        HOT_OFFSET: "Hot",
        PRECIP_OFFSET: "Precip",
    }
    for start, name in read_climate_blocks(cells):
        for offset, header in expected_headers.items():
            ref = f"{ref_for(start + offset)}2"
            actual = as_text(cells[ref].value) if ref in cells else None
            if actual != header:
                raise ValueError(
                    f"Climates!{ref} expected {header!r} for {name!r}, found {actual!r}"
                )

        months: list[dict[str, object]] = []
        for offset in range(MAX_MONTHS):
            row = FIRST_MONTH_ROW + offset
            month_number = as_float(cells[f"B{row}"].value) if f"B{row}" in cells else None
            if month_number is None:
                break
            month_name = as_text(cells[f"C{row}"].value) if f"C{row}" in cells else None
            temp_f = as_float(cells[f"{ref_for(start + TEMP_OFFSET)}{row}"].value)
            cold_f = as_float(cells[f"{ref_for(start + COLD_OFFSET)}{row}"].value)
            avg_f = as_float(cells[f"{ref_for(start + AVG_OFFSET)}{row}"].value)
            hot_f = as_float(cells[f"{ref_for(start + HOT_OFFSET)}{row}"].value)
            precip = as_float(cells[f"{ref_for(start + PRECIP_OFFSET)}{row}"].value)
            months.append(
                {
                    "month": int(month_number),
                    "name": month_name,
                    "temp_f": temp_f,
                    "cold_f": cold_f,
                    "avg_f": avg_f,
                    "hot_f": hot_f,
                    "cold_c": _to_celsius(cold_f),
                    "avg_c": _to_celsius(avg_f),
                    "hot_c": _to_celsius(hot_f),
                    "precipitation_probability": round(precip, 6) if precip is not None else None,
                    "precipitation_probability_pct": (
                        round(precip * 100, 4) if precip is not None else None
                    ),
                }
            )
        climates.append(
            {
                "id": slugify(name),
                "source_name": name,
                "source_cells": {
                    "name": f"Climates!{ref_for(start)}1",
                    "months": (
                        f"Climates!{ref_for(start + COLD_OFFSET)}{FIRST_MONTH_ROW}:"
                        f"{ref_for(start + PRECIP_OFFSET)}{FIRST_MONTH_ROW + len(months) - 1}"
                    ),
                },
                "months": months,
            }
        )
    return climates


def read_wind(cells: dict[str, Cell]) -> list[dict[str, object]]:
    wind: list[dict[str, object]] = []
    for offset in range(MAX_MONTHS):
        row = 2 + offset
        name = as_text(cells[f"B{row}"].value) if f"B{row}" in cells else None
        if name is None:
            break
        label = as_text(cells[f"C{row}"].value) or ""
        mph_min, mph_max = parse_mph_range(label)
        wind.append(
            {
                "index": offset + 1,
                "name": name,
                "mph_label": label,
                "mph_min": mph_min,
                "mph_max": mph_max,
                "kmh_min": round(mph_min * MPH_TO_KMH, 1),
                "kmh_max": round(mph_max * MPH_TO_KMH, 1),
                "description": as_text(cells[f"D{row}"].value),
                "lookup_threshold": as_float(cells[f"A{row}"].value),
            }
        )
    return wind


CANONICAL_DIRECTIONS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def read_precipitation(cells: dict[str, Cell]) -> dict[str, object]:
    """Read the label vocabularies and the observed counts of one recalculation."""
    columns = {
        "A": "rain_intensity",
        "B": "snow_intensity",
        "C": "cloud_cover",
        "D": "features",
        "E": "wind",
        "G": "directions",
    }
    counts: dict[str, dict[str, int]] = {}
    observed_rows = 0
    for letters, key in columns.items():
        counter: dict[str, int] = {}
        for offset in range(2000):
            row = 2 + offset
            cell = cells.get(f"{letters}{row}")
            if cell is None:
                continue
            text = as_text(cell.value)
            if text is None:
                continue
            counter[text] = counter.get(text, 0) + 1
            if letters == "A":
                observed_rows += 1
        counts[key] = counter

    # Rain and snow intensities keep their first-appearance order because it is
    # also their ascending severity; the other vocabularies are sorted so the
    # catalog does not depend on the order of one particular recalculation.
    directions = [name for name in CANONICAL_DIRECTIONS if name in counts["directions"]]
    directions.extend(sorted(set(counts["directions"]) - set(CANONICAL_DIRECTIONS)))
    return {
        "observed_row_count": observed_rows,
        "rain_intensity": list(counts["rain_intensity"]),
        "snow_intensity": list(counts["snow_intensity"]),
        "cloud_cover": list(counts["cloud_cover"]),
        "features": sorted(counts["features"]),
        "directions": directions,
        "observed_counts": counts,
    }


def read_clear_sky_choices(cells: dict[str, Cell]) -> list[str]:
    """Recover the ``CHOOSE(RANDBETWEEN(1,4), ...)`` arguments used for a dry day."""
    cell = cells.get("F2")
    if cell is None or not cell.formula:
        return []
    match = re.search(r"CHOOSE\(RANDBETWEEN\(1,(\d+)\),", cell.formula)
    if not match:
        return []
    return re.findall(r'"([^"]*)"', cell.formula[match.end():])


def build_catalog(path: Path) -> dict[str, object]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with Workbook(path) as workbook:
        settings = read_settings(workbook.cells("Settings"))
        climates = read_climates(workbook.cells("Climates"))
        wind = read_wind(workbook.cells("Wind"))
        precipitation = read_precipitation(workbook.cells("Precipitation"))
        clear_sky = read_clear_sky_choices(workbook.cells("Year of Weather"))
        sheet_names = workbook.sheet_names

    settings["clear_sky_choices"] = [
        {"label": label, "weight": 1} for label in clear_sky
    ]
    return {
        "schema_version": 1,
        "generated_by": "scripts/extract_weather_workbook.py",
        "source": {
            "workbook": path.name,
            "sha256": digest,
            "size_bytes": path.stat().st_size,
            "sheets": sheet_names,
        },
        "stability": {
            "static": [
                "settings",
                "climates[].months[].precipitation_probability",
                "wind",
                "precipitation.rain_intensity",
                "precipitation.snow_intensity",
                "precipitation.cloud_cover",
                "precipitation.features",
                "precipitation.directions",
            ],
            "randomized_snapshot": [
                "climates[].months[].temp_f",
                "climates[].months[].cold_f",
                "climates[].months[].avg_f",
                "climates[].months[].hot_f",
                "precipitation.observed_counts.wind",
                "precipitation.observed_counts.directions",
                "precipitation.observed_counts.features",
            ],
        },
        "settings": settings,
        "climates": climates,
        "wind": wind,
        "precipitation": precipitation,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", required=True, type=Path, help="path to the .xlsx workbook")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"catalog destination (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args(argv)

    if not args.source.is_file():
        print(f"error: workbook not found: {args.source}", file=sys.stderr)
        return 2

    catalog = build_catalog(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    months = sum(len(climate["months"]) for climate in catalog["climates"])
    print(f"climates: {len(catalog['climates'])} ({months} month profiles)")
    print(f"wind classes: {len(catalog['wind'])}")
    print(f"precipitation rows: {catalog['precipitation']['observed_row_count']}")
    print(f"catalog written to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



