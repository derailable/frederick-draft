from datetime import date

import polars as pl

from frederick_draft.models import (
    DraftCandidate,
    DraftCandidateSet,
    DraftExtraction,
    EventCandidate,
    EventCandidateSet,
    FoodTruckCandidate,
    FoodTruckCandidateSet,
)
from frederick_draft.normalize import (
    DRAFT_COLUMNS,
    EVENT_COLUMNS,
    FOOD_TRUCK_COLUMNS,
    merge_draft_runs,
    upsert_events,
    upsert_food_trucks,
)


def empty(columns: list[str]) -> pl.DataFrame:
    return pl.DataFrame({column: pl.Series(column, [], dtype=pl.String) for column in columns})


def draft_set(
    observed: date,
    names: list[str],
    *,
    complete: bool = True,
    usable: bool = True,
) -> DraftCandidateSet:
    return DraftCandidateSet(
        observation_date=observed,
        extractions=[
            DraftExtraction(
                brewery_id="one",
                source_id="one-drafts",
                source_sha256="a" * 64 if usable else None,
                complete_list=complete,
                usable=usable,
                records=[DraftCandidate(beer_name=name, style="Lager") for name in names],
            )
        ],
    )


def test_new_and_unchanged_beer_use_one_tap_run() -> None:
    runs = merge_draft_runs(
        empty(DRAFT_COLUMNS), draft_set(date(2026, 9, 4), ["House Lager"])
    )
    runs = merge_draft_runs(runs, draft_set(date(2026, 9, 11), ["House Lager"]))
    runs = merge_draft_runs(runs, draft_set(date(2026, 9, 11), ["House Lager"]))
    assert runs.height == 1
    assert runs.get_column("first_seen_date").item() == "2026-09-04"
    assert runs.get_column("last_seen_date").item() == "2026-09-11"
    assert runs.get_column("first_missing_date").item() is None


def test_complete_list_closes_missing_run() -> None:
    runs = merge_draft_runs(empty(DRAFT_COLUMNS), draft_set(date(2026, 9, 4), ["Lager"]))
    runs = merge_draft_runs(runs, draft_set(date(2026, 9, 11), []))
    assert runs.get_column("first_missing_date").item() == "2026-09-11"


def test_incomplete_or_failed_extraction_does_not_close_run() -> None:
    runs = merge_draft_runs(empty(DRAFT_COLUMNS), draft_set(date(2026, 9, 4), ["Lager"]))
    runs = merge_draft_runs(
        runs, draft_set(date(2026, 9, 11), [], complete=False, usable=True)
    )
    runs = merge_draft_runs(
        runs, draft_set(date(2026, 9, 18), [], complete=False, usable=False)
    )
    assert runs.get_column("first_missing_date").item() is None


def test_returning_beer_creates_a_new_tap_run() -> None:
    runs = merge_draft_runs(empty(DRAFT_COLUMNS), draft_set(date(2026, 9, 4), ["Lager"]))
    runs = merge_draft_runs(runs, draft_set(date(2026, 9, 11), []))
    runs = merge_draft_runs(runs, draft_set(date(2026, 9, 18), ["Lager"]))
    assert runs.height == 2
    assert runs.get_column("first_seen_date").to_list() == ["2026-09-04", "2026-09-18"]
    assert runs.get_column("first_missing_date").to_list() == ["2026-09-11", None]


def test_repeated_event_and_food_extractions_do_not_duplicate() -> None:
    events = EventCandidateSet(
        records=[
            EventCandidate(
                brewery_id="one",
                source_id="one-events",
                event_name="Trivia",
                start_at="2026-09-10T19:00:00-04:00",
                end_at="2026-09-10T21:00:00-04:00",
            )
        ]
    )
    event_rows = upsert_events(empty(EVENT_COLUMNS), events)
    event_rows = upsert_events(event_rows, events)
    assert event_rows.height == 1

    food = FoodTruckCandidateSet(
        records=[
            FoodTruckCandidate(
                brewery_id="one",
                source_id="one-food",
                vendor_name="Taco Truck",
                start_at="2026-09-10T17:00:00-04:00",
            )
        ]
    )
    food_rows = upsert_food_trucks(empty(FOOD_TRUCK_COLUMNS), food)
    food_rows = upsert_food_trucks(food_rows, food)
    assert food_rows.height == 1
