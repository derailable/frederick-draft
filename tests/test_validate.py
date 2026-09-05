import hashlib
import json
from pathlib import Path

import pytest

from frederick_draft.validate import (
    DataValidationError,
    load_breweries,
    validate_all,
    validate_reference,
)

BREWERY_HEADER = (
    "brewery_id,name,status,included,street_address,city,state,postal_code,latitude,longitude,"
    "website_url,food_service\n"
)
HOURS_HEADER = "brewery_id,day_of_week,open_time,close_time\n"


def write_reference(root: Path, brewery_rows: list[str] | None = None) -> tuple[Path, Path, Path]:
    breweries = root / "breweries.csv"
    hours = root / "hours.csv"
    sources = root / "sources.json"
    rows = brewery_rows or ["one,One,active,true,,,,,,,,none"]
    breweries.write_text(BREWERY_HEADER + "\n".join(rows) + "\n")
    hours.write_text(HOURS_HEADER)
    sources.write_text(
        json.dumps(
            {
                "version": 1,
                "breweries": [
                    {
                        "brewery_id": "one",
                        "sources": [
                            {
                                "source_id": "one-drafts",
                                "category": "drafts",
                                "url": "https://example.com/taps",
                                "fetch_type": "html",
                                "enabled": True,
                            }
                        ],
                    }
                ],
            }
        )
    )
    return breweries, hours, sources


def draft_extraction(**overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "brewery_id": "one",
        "source_id": "one-drafts",
        "source_sha256": "a" * 64,
        "complete_list": True,
        "usable": True,
        "records": [{"beer_name": "Lager", "style": "Pilsner", "abv": 5, "ibu": 20}],
    }
    result.update(overrides)
    return result


def write_candidates(root: Path, extraction: dict[str, object]) -> tuple[Path, Path, Path]:
    drafts = root / "drafts.json"
    events = root / "events.json"
    food = root / "food.json"
    drafts.write_text(
        json.dumps({"observation_date": "2026-09-04", "extractions": [extraction]})
    )
    events.write_text('{"records": []}')
    food.write_text('{"records": []}')
    return drafts, events, food


def test_duplicate_brewery_ids(tmp_path: Path) -> None:
    paths = write_reference(
        tmp_path,
        ["one,One,active,true,,,,,,,,none", "one,Duplicate,active,true,,,,,,,,none"],
    )
    with pytest.raises(DataValidationError, match="duplicate brewery_id"):
        load_breweries(paths[0])


def test_source_references_unknown_brewery(tmp_path: Path) -> None:
    breweries, hours, sources = write_reference(tmp_path)
    payload = json.loads(sources.read_text())
    payload["breweries"][0]["brewery_id"] = "missing"
    sources.write_text(json.dumps(payload))
    with pytest.raises(DataValidationError, match="unknown brewery_id missing"):
        validate_reference(breweries, hours, sources)


@pytest.mark.parametrize(
    "overrides,message",
    [
        ({"brewery_id": "missing"}, "unknown brewery_id"),
        ({"source_id": "missing-drafts"}, "unknown source_id"),
        ({"brewery_id": "two"}, "belongs to one"),
    ],
)
def test_candidate_referential_errors(
    tmp_path: Path, overrides: dict[str, object], message: str
) -> None:
    rows = None
    if overrides.get("brewery_id") == "two":
        rows = ["one,One,active,true,,,,,,,,none", "two,Two,active,true,,,,,,,,none"]
    breweries, hours, sources = write_reference(tmp_path, rows)
    drafts, events, food = write_candidates(tmp_path, draft_extraction(**overrides))
    with pytest.raises(DataValidationError, match=message):
        validate_all(breweries, hours, sources, drafts, events, food)


def test_duplicate_beer_detection(tmp_path: Path) -> None:
    breweries, hours, sources = write_reference(tmp_path)
    extraction = draft_extraction()
    extraction["records"] = [{"beer_name": "Lager"}, {"beer_name": "lager"}]
    drafts, events, food = write_candidates(tmp_path, extraction)
    with pytest.raises(DataValidationError, match="probable duplicate"):
        validate_all(breweries, hours, sources, drafts, events, food)


def test_candidate_hash_matches_local_metadata(tmp_path: Path) -> None:
    breweries, hours, sources = write_reference(tmp_path)
    drafts, events, food = write_candidates(tmp_path, draft_extraction(source_sha256="b" * 64))
    raw = tmp_path / "raw"
    evidence = raw / "one"
    evidence.mkdir(parents=True)
    expected = hashlib.sha256(b"evidence").hexdigest()
    (evidence / "one-drafts.meta.json").write_text(json.dumps({"sha256": expected}))
    with pytest.raises(DataValidationError, match="does not match local source metadata"):
        validate_all(breweries, hours, sources, drafts, events, food, raw)
