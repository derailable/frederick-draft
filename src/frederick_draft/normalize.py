"""Lifecycle-aware canonical CSV updates."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from datetime import date, datetime
from pathlib import Path

import polars as pl

from .models import DraftCandidateSet, EventCandidateSet, FoodTruckCandidateSet
from .paths import DRAFTS_PATH, EVENTS_PATH, FOOD_TRUCKS_PATH, PUBLIC_DIR
from .validate import ValidatedData

DRAFT_COLUMNS = [
    "draft_id",
    "brewery_id",
    "beer_name",
    "style",
    "abv",
    "ibu",
    "first_seen_date",
    "last_seen_date",
    "first_missing_date",
    "source_id",
]
EVENT_COLUMNS = ["event_id", "brewery_id", "event_name", "start_at", "end_at", "source_id"]
FOOD_TRUCK_COLUMNS = [
    "food_truck_event_id",
    "brewery_id",
    "vendor_name",
    "start_at",
    "end_at",
    "source_id",
]


def normalized_name(value: str) -> str:
    """Return a conservative identity key without changing displayed names."""
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _stable_id(prefix: str, *parts: object) -> str:
    canonical = "\x1f".join(normalized_name(str(part)) for part in parts)
    return f"{prefix}-{hashlib.sha256(canonical.encode()).hexdigest()[:20]}"


def _serialize(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _frame(rows: list[dict[str, object]], columns: list[str]) -> pl.DataFrame:
    if not rows:
        return pl.DataFrame({column: pl.Series(column, [], dtype=pl.String) for column in columns})
    return pl.DataFrame(rows).select(columns).with_columns(pl.all().cast(pl.String))


def _read_existing(path: Path, columns: list[str]) -> pl.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return _frame([], columns)
    frame = pl.read_csv(path, infer_schema=False)
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{path.name} is missing required columns: {', '.join(missing)}")
    return frame.select(columns)


def merge_draft_runs(existing: pl.DataFrame, candidates: DraftCandidateSet) -> pl.DataFrame:
    """Apply positive observations and safe complete-list closures to tap runs."""
    rows = existing.to_dicts()
    active: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        if not row.get("first_missing_date"):
            key = (str(row["brewery_id"]), normalized_name(str(row["beer_name"])))
            if key in active:
                raise ValueError(f"multiple active draft runs for {key[0]} / {key[1]}")
            active[key] = row

    observed: dict[str, set[str]] = {}
    complete_sources: dict[str, str] = {}
    seen_candidates: set[tuple[str, str]] = set()
    observation_date = candidates.observation_date.isoformat()

    for extraction in candidates.extractions:
        if not extraction.usable:
            continue
        brewery_observed = observed.setdefault(extraction.brewery_id, set())
        if extraction.complete_list:
            complete_sources.setdefault(extraction.brewery_id, extraction.source_id)
        for item in extraction.records:
            name_key = normalized_name(item.beer_name)
            key = (extraction.brewery_id, name_key)
            if key in seen_candidates:
                raise ValueError(f"duplicate draft observation for {key[0]} / {item.beer_name}")
            seen_candidates.add(key)
            brewery_observed.add(name_key)
            row = active.get(key)
            if row is None:
                row = {
                    "draft_id": _stable_id(
                        "draft", extraction.brewery_id, name_key, observation_date
                    ),
                    "brewery_id": extraction.brewery_id,
                    "beer_name": item.beer_name,
                    "style": item.style,
                    "abv": item.abv,
                    "ibu": item.ibu,
                    "first_seen_date": observation_date,
                    "last_seen_date": observation_date,
                    "first_missing_date": None,
                    "source_id": extraction.source_id,
                }
                rows.append(row)
                active[key] = row
                continue
            if observation_date < str(row["last_seen_date"]):
                raise ValueError("draft observations cannot move last_seen_date backwards")
            row["beer_name"] = item.beer_name
            for field in ("style", "abv", "ibu"):
                value = getattr(item, field)
                if value is not None:
                    row[field] = value
            row["last_seen_date"] = observation_date
            row["source_id"] = extraction.source_id

    for brewery_id, source_id in complete_sources.items():
        present = observed.get(brewery_id, set())
        for (active_brewery, name_key), row in list(active.items()):
            if active_brewery != brewery_id or name_key in present:
                continue
            if observation_date < str(row["last_seen_date"]):
                raise ValueError("draft observations cannot close a newer tap run")
            row["first_missing_date"] = observation_date
            row["source_id"] = source_id
            del active[(active_brewery, name_key)]

    return _frame(rows, DRAFT_COLUMNS).sort(
        ["first_seen_date", "brewery_id", "beer_name", "draft_id"]
    )


def _event_rows(candidates: EventCandidateSet) -> list[dict[str, object]]:
    return [
        {
            "event_id": _stable_id("event", item.brewery_id, item.event_name, item.start_at),
            "brewery_id": item.brewery_id,
            "event_name": item.event_name,
            "start_at": item.start_at.isoformat(),
            "end_at": item.end_at.isoformat() if item.end_at else None,
            "source_id": item.source_id,
        }
        for item in candidates.records
    ]


def _food_rows(candidates: FoodTruckCandidateSet) -> list[dict[str, object]]:
    return [
        {
            "food_truck_event_id": _stable_id(
                "food", item.brewery_id, item.vendor_name, item.start_at
            ),
            "brewery_id": item.brewery_id,
            "vendor_name": item.vendor_name,
            "start_at": _serialize(item.start_at),
            "end_at": _serialize(item.end_at),
            "source_id": item.source_id,
        }
        for item in candidates.records
    ]


def upsert_events(existing: pl.DataFrame, candidates: EventCandidateSet) -> pl.DataFrame:
    """Upsert events by stable ID, with a conservative title-correction fallback."""
    rows = existing.to_dicts()
    by_id = {str(row["event_id"]): row for row in rows}
    by_start: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        by_start.setdefault((str(row["brewery_id"]), str(row["start_at"])), []).append(row)
    for candidate in _event_rows(candidates):
        row = by_id.get(str(candidate["event_id"]))
        if row is None:
            matches = by_start.get(
                (str(candidate["brewery_id"]), str(candidate["start_at"])), []
            )
            row = matches[0] if len(matches) == 1 else None
        if row is None:
            rows.append(candidate)
            by_id[str(candidate["event_id"])] = candidate
        else:
            event_id = row["event_id"]
            row.update(candidate)
            row["event_id"] = event_id
    return _frame(rows, EVENT_COLUMNS).sort(["start_at", "brewery_id", "event_id"])


def upsert_food_trucks(
    existing: pl.DataFrame, candidates: FoodTruckCandidateSet
) -> pl.DataFrame:
    """Upsert appearances, treating a same-day time correction as the same occurrence."""
    rows = existing.to_dicts()
    by_id = {str(row["food_truck_event_id"]): row for row in rows}
    by_day: dict[tuple[str, str, str], list[dict[str, object]]] = {}
    for row in rows:
        key = (
            str(row["brewery_id"]),
            normalized_name(str(row["vendor_name"])),
            str(row["start_at"])[:10],
        )
        by_day.setdefault(key, []).append(row)
    for candidate in _food_rows(candidates):
        row = by_id.get(str(candidate["food_truck_event_id"]))
        if row is None:
            key = (
                str(candidate["brewery_id"]),
                normalized_name(str(candidate["vendor_name"])),
                str(candidate["start_at"])[:10],
            )
            matches = by_day.get(key, [])
            row = matches[0] if len(matches) == 1 else None
        if row is None:
            rows.append(candidate)
            by_id[str(candidate["food_truck_event_id"])] = candidate
        else:
            event_id = row["food_truck_event_id"]
            row.update(candidate)
            row["food_truck_event_id"] = event_id
    return _frame(rows, FOOD_TRUCK_COLUMNS).sort(
        ["start_at", "brewery_id", "food_truck_event_id"]
    )


def _stage_csv(frame: pl.DataFrame, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    os.close(descriptor)
    staged = Path(name)
    frame.write_csv(staged)
    return staged


def write_canonical(data: ValidatedData, public_dir: Path = PUBLIC_DIR) -> None:
    """Apply idempotent lifecycle/upsert rules and atomically replace canonical CSVs."""
    destinations = [
        public_dir / DRAFTS_PATH.name,
        public_dir / EVENTS_PATH.name,
        public_dir / FOOD_TRUCKS_PATH.name,
    ]
    merged = [
        merge_draft_runs(_read_existing(destinations[0], DRAFT_COLUMNS), data.drafts),
        upsert_events(_read_existing(destinations[1], EVENT_COLUMNS), data.events),
        upsert_food_trucks(
            _read_existing(destinations[2], FOOD_TRUCK_COLUMNS), data.food_trucks
        ),
    ]
    staged: list[Path] = []
    try:
        staged = [_stage_csv(frame, path) for frame, path in zip(merged, destinations, strict=True)]
        for temporary, destination in zip(staged, destinations, strict=True):
            temporary.replace(destination)
    finally:
        for temporary in staged:
            temporary.unlink(missing_ok=True)

