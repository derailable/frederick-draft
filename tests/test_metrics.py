import json
from datetime import date
from pathlib import Path

from frederick_draft.metrics import calculate_metrics, write_metrics

BREWERY_HEADER = (
    "brewery_id,name,status,included,street_address,city,state,postal_code,latitude,longitude,"
    "website_url,food_service\n"
)
DRAFT_HEADER = (
    "draft_id,brewery_id,beer_name,style,abv,ibu,first_seen_date,last_seen_date,"
    "first_missing_date,source_id\n"
)


def test_small_lifecycle_metrics(tmp_path: Path) -> None:
    breweries = tmp_path / "breweries.csv"
    breweries.write_text(
        BREWERY_HEADER
        + "one,One,active,true,,,,,,,,none\n"
        + "two,Two,seasonal,true,,,,,,,,none\n"
        + "closed,Closed,closed,false,,,,,,,,none\n"
    )
    drafts = tmp_path / "drafts.csv"
    drafts.write_text(
        DRAFT_HEADER
        + "draft-1,one,Current Lager,Lager,4.0,,2026-09-04,2026-09-04,,one-drafts\n"
        + "draft-2,one,Old Stout,Stout,8.0,,2026-08-20,2026-08-27,2026-09-04,one-drafts\n"
    )
    events = tmp_path / "events.csv"
    events.write_text(
        "event_id,brewery_id,event_name,start_at,end_at,source_id\n"
        "event-1,one,Trivia,2026-09-05T19:00:00-04:00,,one-events\n"
    )
    food = tmp_path / "food.csv"
    food.write_text(
        "food_truck_event_id,brewery_id,vendor_name,start_at,end_at,source_id\n"
        "food-1,one,Tacos,2026-09-03T17:00:00-04:00,,one-food\n"
    )
    metrics = calculate_metrics(
        drafts_path=drafts,
        events_path=events,
        food_trucks_path=food,
        breweries_path=breweries,
        today=date(2026, 9, 4),
    )
    assert metrics == {
        "as_of_date": "2026-09-04",
        "included_breweries": 2,
        "breweries_with_draft_data": 1,
        "current_beers": 1,
        "new_beers": 1,
        "median_abv": 4.0,
        "brewery_events": 1,
        "food_truck_events": 0,
    }


def test_write_metrics_replaces_latest_object(tmp_path: Path) -> None:
    path = tmp_path / "metrics.json"
    write_metrics({"current_beers": 1}, path)
    write_metrics({"current_beers": 2}, path)
    assert json.loads(path.read_text()) == {"current_beers": 2}
