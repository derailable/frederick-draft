"""Pydantic models for reference, acquisition, and candidate data."""

from __future__ import annotations

import re
from datetime import date, datetime, time
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class BreweryStatus(StrEnum):
    ACTIVE = "active"
    SEASONAL = "seasonal"
    TEMPORARILY_CLOSED = "temporarily_closed"
    CLOSED = "closed"


class FoodService(StrEnum):
    NONE = "none"
    LIMITED = "limited"
    FULL_KITCHEN = "full_kitchen"
    RESIDENT_VENDOR = "resident_vendor"
    UNKNOWN = "unknown"


class DayOfWeek(StrEnum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class SourceCategory(StrEnum):
    DRAFTS = "drafts"
    EVENTS = "events"
    FOOD_TRUCKS = "food_trucks"
    HOURS = "hours"
    GENERAL = "general"


class FetchType(StrEnum):
    HTML = "html"
    JSON = "json"
    ICAL = "ical"
    GOOGLE_DOC = "google_doc"
    PDF = "pdf"
    IMAGE = "image"
    MANUAL = "manual"


class Brewery(StrictModel):
    brewery_id: str = Field(pattern=KEBAB_RE.pattern)
    name: str = Field(min_length=1)
    status: BreweryStatus
    included: bool
    street_address: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    website_url: HttpUrl | None = None
    food_service: FoodService

    @model_validator(mode="after")
    def check_relationships(self) -> Brewery:
        if self.status == BreweryStatus.CLOSED and self.included:
            raise ValueError("closed breweries cannot be included")
        return self


class HoursRow(StrictModel):
    brewery_id: str = Field(pattern=KEBAB_RE.pattern)
    day_of_week: DayOfWeek
    open_time: time | None = None
    close_time: time | None = None

    @model_validator(mode="after")
    def paired_times(self) -> HoursRow:
        if (self.open_time is None) != (self.close_time is None):
            raise ValueError("open_time and close_time must both be present or blank")
        return self


class SourceDefinition(StrictModel):
    source_id: str = Field(pattern=KEBAB_RE.pattern)
    category: SourceCategory
    url: HttpUrl
    fetch_type: FetchType
    enabled: bool

    @model_validator(mode="after")
    def manual_disabled(self) -> SourceDefinition:
        if self.fetch_type == FetchType.MANUAL and self.enabled:
            raise ValueError("manual sources must be disabled")
        return self


class BrewerySources(StrictModel):
    brewery_id: str = Field(pattern=KEBAB_RE.pattern)
    sources: list[SourceDefinition]


class SourcesManifest(StrictModel):
    version: int = Field(ge=1)
    breweries: list[BrewerySources]

    @model_validator(mode="after")
    def globally_unique(self) -> SourcesManifest:
        brewery_ids = [item.brewery_id for item in self.breweries]
        if len(brewery_ids) != len(set(brewery_ids)):
            raise ValueError("duplicate brewery_id in source manifest")
        source_ids = [source.source_id for item in self.breweries for source in item.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("duplicate source_id in source manifest")
        return self


class RetrievalMetadata(StrictModel):
    brewery_id: str
    source_id: str
    category: SourceCategory
    requested_url: HttpUrl
    final_url: HttpUrl
    retrieved_at: datetime
    status_code: int
    content_type: str | None
    content_length: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    etag: str | None = None
    last_modified: str | None = None
    changed: bool

    @model_validator(mode="after")
    def aware_timestamp(self) -> RetrievalMetadata:
        if self.retrieved_at.tzinfo is None:
            raise ValueError("retrieved_at must be timezone-aware")
        return self


class CandidateSource(StrictModel):
    brewery_id: str = Field(pattern=KEBAB_RE.pattern)
    source_id: str = Field(pattern=KEBAB_RE.pattern)


class DraftCandidate(StrictModel):
    beer_name: str = Field(min_length=1)
    style: str | None = None
    abv: float | None = Field(default=None, ge=0, le=25)
    ibu: float | None = Field(default=None, ge=0, le=200)


class DraftExtraction(CandidateSource):
    source_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    complete_list: bool
    usable: bool
    records: list[DraftCandidate]

    @model_validator(mode="after")
    def usable_extraction(self) -> DraftExtraction:
        if not self.usable and self.complete_list:
            raise ValueError("an unusable extraction cannot be a complete list")
        if not self.usable and self.records:
            raise ValueError("an unusable extraction cannot contain observations")
        if self.complete_list and self.source_sha256 is None:
            raise ValueError("a complete list requires fetched evidence with a SHA-256")
        return self


class EventCandidate(CandidateSource):
    event_name: str = Field(min_length=1)
    start_at: datetime
    end_at: datetime | None = None

    @model_validator(mode="after")
    def event_times(self) -> EventCandidate:
        if self.start_at.tzinfo is None:
            raise ValueError("start_at must be timezone-aware")
        if self.end_at is not None:
            if self.end_at.tzinfo is None:
                raise ValueError("end_at must be timezone-aware")
            if self.end_at < self.start_at:
                raise ValueError("end_at must not precede start_at")
        return self


class FoodTruckCandidate(CandidateSource):
    vendor_name: str = Field(min_length=1)
    start_at: datetime | date
    end_at: datetime | date | None = None

    @model_validator(mode="after")
    def food_truck_times(self) -> FoodTruckCandidate:
        for value in (self.start_at, self.end_at):
            if isinstance(value, datetime) and value.tzinfo is None:
                raise ValueError("food truck datetimes must be timezone-aware")
        if self.end_at is not None and self.end_at < self.start_at:
            raise ValueError("end_at must not precede start_at")
        return self


class DraftCandidateSet(StrictModel):
    observation_date: date
    extractions: list[DraftExtraction]


class EventCandidateSet(StrictModel):
    records: list[EventCandidate]


class FoodTruckCandidateSet(StrictModel):
    records: list[FoodTruckCandidate]
