"""Small derived metrics for the future publication."""

from __future__ import annotations

import json
import os
import statistics
import tempfile
from datetime import date
from pathlib import Path

import polars as pl

from .paths import BREWERIES_PATH, DRAFTS_PATH, EVENTS_PATH, FOOD_TRUCKS_PATH, METRICS_PATH
from .validate import load_breweries


def _read_frame(path: Path) -> pl.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pl.DataFrame()
    return pl.read_csv(path, infer_schema=False)


def calculate_metrics(
    *,
    drafts_path: Path = DRAFTS_PATH,
    events_path: Path = EVENTS_PATH,
    food_trucks_path: Path = FOOD_TRUCKS_PATH,
    breweries_path: Path = BREWERIES_PATH,
    today: date | None = None,
) -> dict[str, object]:
    """Calculate only the current counts needed by the MVP."""
    breweries = load_breweries(breweries_path)
    drafts = _read_frame(drafts_path)
    events = _read_frame(events_path)
    food_trucks = _read_frame(food_trucks_path)
    report_date = today or date.today()

    included = {item.brewery_id for item in breweries if item.included}
    current = (
        drafts.filter(pl.col("first_missing_date").is_null() | (pl.col("first_missing_date") == ""))
        if drafts.height
        else drafts
    )
    represented = set(current.get_column("brewery_id").to_list()) if current.height else set()
    abvs = (
        [float(value) for value in current.get_column("abv").to_list() if value not in {None, ""}]
        if current.height
        else []
    )
    lifecycle_dates = []
    if drafts.height:
        for column in ("last_seen_date", "first_missing_date"):
            lifecycle_dates.extend(
                value for value in drafts.get_column(column).to_list() if value not in {None, ""}
            )
    as_of_date = max(lifecycle_dates) if lifecycle_dates else None
    new_beers = (
        drafts.filter(pl.col("first_seen_date") == as_of_date).height if as_of_date else 0
    )
    date_text = report_date.isoformat()
    upcoming_events = (
        events.filter(pl.col("start_at").str.slice(0, 10) >= date_text).height
        if events.height
        else 0
    )
    upcoming_food = (
        food_trucks.filter(pl.col("start_at").str.slice(0, 10) >= date_text).height
        if food_trucks.height
        else 0
    )
    return {
        "as_of_date": as_of_date,
        "included_breweries": len(included),
        "breweries_with_draft_data": len(represented & included),
        "current_beers": current.height,
        "new_beers": new_beers,
        "median_abv": statistics.median(abvs) if abvs else None,
        "brewery_events": upcoming_events,
        "food_truck_events": upcoming_food,
    }


def write_metrics(metrics: dict[str, object], path: Path = METRICS_PATH) -> None:
    """Atomically replace the latest derived metrics object."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        temporary.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)

