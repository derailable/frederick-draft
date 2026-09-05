"""Loaders and cross-file validation for reference and candidate data."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ValidationError

from .models import (
    Brewery,
    DraftCandidateSet,
    EventCandidateSet,
    FoodTruckCandidateSet,
    HoursRow,
    SourceCategory,
    SourceDefinition,
    SourcesManifest,
)
from .paths import (
    BREWERIES_PATH,
    DRAFT_CANDIDATES_PATH,
    EVENT_CANDIDATES_PATH,
    FOOD_TRUCK_CANDIDATES_PATH,
    HOURS_PATH,
    RAW_DIR,
    SOURCES_PATH,
)


class DataValidationError(ValueError):
    """A user-facing collection of deterministic validation problems."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


@dataclass(frozen=True)
class ValidatedData:
    breweries: list[Brewery]
    hours: list[HoursRow]
    manifest: SourcesManifest
    drafts: DraftCandidateSet
    events: EventCandidateSet
    food_trucks: FoodTruckCandidateSet


def _blank_to_none(row: dict[str, str]) -> dict[str, str | None]:
    return {key: (value if value != "" else None) for key, value in row.items()}


def load_csv_models[ModelT: BaseModel](path: Path, model: type[ModelT]) -> list[ModelT]:
    errors: list[str] = []
    records: list[ModelT] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for line_number, row in enumerate(csv.DictReader(handle), start=2):
            try:
                records.append(model.model_validate(_blank_to_none(row)))
            except ValidationError as exc:
                errors.append(f"{path}:{line_number}: {exc}")
    if errors:
        raise DataValidationError(errors)
    return records


def load_breweries(path: Path = BREWERIES_PATH) -> list[Brewery]:
    breweries = load_csv_models(path, Brewery)
    ids = [item.brewery_id for item in breweries]
    errors = []
    if len(ids) != len(set(ids)):
        errors.append("breweries.csv: duplicate brewery_id")
    if errors:
        raise DataValidationError(errors)
    return breweries


def load_hours(path: Path = HOURS_PATH) -> list[HoursRow]:
    return load_csv_models(path, HoursRow)


def load_manifest(path: Path = SOURCES_PATH) -> SourcesManifest:
    try:
        return SourcesManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        raise DataValidationError([f"{path}: {exc}"]) from exc


def _load_candidate[ModelT: BaseModel](path: Path, model: type[ModelT]) -> ModelT:
    try:
        return model.model_validate_json(path.read_text(encoding="utf-8"))
    except (ValidationError, json.JSONDecodeError) as exc:
        raise DataValidationError([f"{path}: {exc}"]) from exc


def validate_reference(
    breweries_path: Path = BREWERIES_PATH,
    hours_path: Path = HOURS_PATH,
    sources_path: Path = SOURCES_PATH,
) -> tuple[list[Brewery], list[HoursRow], SourcesManifest]:
    breweries = load_breweries(breweries_path)
    hours = load_hours(hours_path)
    manifest = load_manifest(sources_path)
    known = {item.brewery_id for item in breweries}
    errors: list[str] = []
    for row in hours:
        if row.brewery_id not in known:
            errors.append(f"hours.csv: unknown brewery_id {row.brewery_id}")
    for group in manifest.breweries:
        if group.brewery_id not in known:
            errors.append(f"sources.json: unknown brewery_id {group.brewery_id}")
    if errors:
        raise DataValidationError(errors)
    return breweries, hours, manifest


def _source_index(manifest: SourcesManifest) -> dict[str, tuple[str, SourceDefinition]]:
    return {
        source.source_id: (group.brewery_id, source)
        for group in manifest.breweries
        for source in group.sources
    }


def _evidence_errors(
    label: str,
    index: int,
    record: BaseModel,
    expected_category: SourceCategory,
    brewery_ids: set[str],
    sources: dict[str, tuple[str, SourceDefinition]],
    raw_dir: Path,
    *,
    check_hash: bool = True,
) -> list[str]:
    errors: list[str] = []
    brewery_id = record.brewery_id  # type: ignore[attr-defined]
    source_id = record.source_id  # type: ignore[attr-defined]
    if brewery_id not in brewery_ids:
        errors.append(f"{label}[{index}]: unknown brewery_id {brewery_id}")
    source = sources.get(source_id)
    if source is None:
        errors.append(f"{label}[{index}]: unknown source_id {source_id}")
    elif source[0] != brewery_id:
        errors.append(f"{label}[{index}]: source {source_id} belongs to {source[0]}")
    elif source[1].category != expected_category:
        errors.append(
            f"{label}[{index}]: source {source_id} has category {source[1].category}"
        )
    metadata_path = raw_dir / brewery_id / f"{source_id}.meta.json"
    if check_hash and metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"{label}[{index}]: unreadable source metadata: {exc}")
        else:
            expected_hash = metadata.get("sha256")
            candidate_hash = getattr(record, "source_sha256", None)
            if candidate_hash is None:
                errors.append(
                    f"{label}[{index}]: source_sha256 is required when local evidence exists"
                )
            elif candidate_hash != expected_hash:
                errors.append(
                    f"{label}[{index}]: source_sha256 does not match local source metadata"
                )
    return errors


def validate_all(
    breweries_path: Path = BREWERIES_PATH,
    hours_path: Path = HOURS_PATH,
    sources_path: Path = SOURCES_PATH,
    drafts_path: Path = DRAFT_CANDIDATES_PATH,
    events_path: Path = EVENT_CANDIDATES_PATH,
    food_trucks_path: Path = FOOD_TRUCK_CANDIDATES_PATH,
    raw_dir: Path = RAW_DIR,
) -> ValidatedData:
    breweries, hours, manifest = validate_reference(breweries_path, hours_path, sources_path)
    drafts = _load_candidate(drafts_path, DraftCandidateSet)
    events = _load_candidate(events_path, EventCandidateSet)
    food_trucks = _load_candidate(food_trucks_path, FoodTruckCandidateSet)
    errors: list[str] = []
    brewery_ids = {item.brewery_id for item in breweries}
    sources = _source_index(manifest)
    seen_drafts: set[tuple[str, str]] = set()
    for index, extraction in enumerate(drafts.extractions):
        errors.extend(
            _evidence_errors(
                "drafts",
                index,
                extraction,
                SourceCategory.DRAFTS,
                brewery_ids,
                sources,
                raw_dir,
                check_hash=extraction.usable,
            )
        )
        for item in extraction.records:
            identity = (extraction.brewery_id, item.beer_name.casefold())
            if identity in seen_drafts:
                errors.append(f"drafts[{index}]: probable duplicate {item.beer_name!r}")
            seen_drafts.add(identity)

    for label, records, category, name_field in (
        ("events", events.records, SourceCategory.EVENTS, "event_name"),
        ("food trucks", food_trucks.records, SourceCategory.FOOD_TRUCKS, "vendor_name"),
    ):
        seen: set[tuple[object, ...]] = set()
        for index, record in enumerate(records):
            errors.extend(
                _evidence_errors(
                    label,
                    index,
                    record,
                    category,
                    brewery_ids,
                    sources,
                    raw_dir,
                    check_hash=False,
                )
            )
            identity = (
                record.brewery_id,
                getattr(record, name_field).casefold(),
                record.start_at,
            )
            if identity in seen:
                errors.append(
                    f"{label}[{index}]: probable duplicate {getattr(record, name_field)!r}"
                )
            seen.add(identity)
    if errors:
        raise DataValidationError(errors)
    return ValidatedData(breweries, hours, manifest, drafts, events, food_trucks)
