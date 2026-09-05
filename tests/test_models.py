import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from frederick_draft.models import (
    Brewery,
    DraftCandidate,
    DraftExtraction,
    FetchType,
    FoodService,
    SourceDefinition,
    SourcesManifest,
)


def brewery_payload() -> dict[str, object]:
    return {
        "brewery_id": "test-brewery",
        "name": "Test Brewery",
        "status": "active",
        "included": True,
        "food_service": "none",
    }


def test_valid_brewery_registry_row() -> None:
    brewery = Brewery.model_validate(brewery_payload())
    assert brewery.brewery_id == "test-brewery"
    assert brewery.food_service is FoodService.NONE


@pytest.mark.parametrize("field,value", [("status", "unknown"), ("food_service", "food_truck")])
def test_invalid_controlled_brewery_values(field: str, value: str) -> None:
    payload = brewery_payload()
    payload[field] = value
    with pytest.raises(ValidationError):
        Brewery.model_validate(payload)


def test_draft_candidate_numbers() -> None:
    with pytest.raises(ValidationError):
        DraftCandidate(beer_name="Test Beer", abv=25.1)
    with pytest.raises(ValidationError):
        DraftCandidate(beer_name="Test Beer", ibu=201)
    assert DraftCandidate(beer_name="Test Beer", style="Pilsner", abv=5.2).abv == 5.2


def test_complete_list_requires_usable_hashed_evidence() -> None:
    with pytest.raises(ValidationError):
        DraftExtraction(
            brewery_id="test-brewery",
            source_id="test-brewery-drafts",
            complete_list=True,
            usable=True,
            records=[],
        )


def test_invalid_source_values_and_duplicate_ids() -> None:
    source = {
        "source_id": "shared-drafts",
        "category": "drafts",
        "url": "https://example.com/taps",
        "fetch_type": "html",
        "enabled": True,
    }
    with pytest.raises(ValidationError):
        SourceDefinition.model_validate({**source, "fetch_type": "browser"})
    with pytest.raises(ValidationError, match="duplicate source_id"):
        SourcesManifest.model_validate(
            {
                "version": 1,
                "breweries": [
                    {"brewery_id": "one", "sources": [source]},
                    {"brewery_id": "two", "sources": [source]},
                ],
            }
        )


def test_real_manifest_keeps_supported_types_and_liquidity_sippo() -> None:
    manifest_path = Path(__file__).parents[1] / "data/reference/sources.json"
    manifest = SourcesManifest.model_validate(json.loads(manifest_path.read_text()))
    types = {source.fetch_type for group in manifest.breweries for source in group.sources}
    assert {
        FetchType.HTML,
        FetchType.GOOGLE_DOC,
        FetchType.ICAL,
        FetchType.PDF,
        FetchType.IMAGE,
        FetchType.MANUAL,
    } <= types
    liquidity = next(
        source
        for group in manifest.breweries
        for source in group.sources
        if source.source_id == "liquidity-drafts"
    )
    assert str(liquidity.url) == "https://app.sippo.io/m/gVvWW"
    assert liquidity.enabled
