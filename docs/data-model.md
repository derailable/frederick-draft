# Data model

Blank optional values mean “not established.” Dates use `YYYY-MM-DD`; event timestamps are
timezone-aware ISO 8601. Maintained datasets contain no free-text notes fields.

## Reference data

`breweries.csv` has: `brewery_id`, `name`, `status`, `included`, `street_address`, `city`, `state`,
`postal_code`, `latitude`, `longitude`, `website_url`, `food_service`.

- `status`: `active`, `seasonal`, `temporarily_closed`, or `closed`.
- `food_service`: `none`, `limited`, `full_kitchen`, `resident_vendor`, or `unknown`.
- `included` controls current publication membership. Closed records are retained but excluded.

`hours.csv` has one current recurring interval per row: `brewery_id`, `day_of_week`, `open_time`,
`close_time`. Days are lowercase Monday through Sunday and times are local 24-hour `HH:MM`. Both
times are blank for a normally closed day.

`sources.json` groups sources by `brewery_id`. A source has `source_id`, `category`, `url`,
`fetch_type`, and `enabled`. Categories are `drafts`, `events`, `food_trucks`, `hours`,
and `general`. Fetch types are `html`, `json`, `ical`, `google_doc`, `pdf`, `image`, and `manual`.
Manual sources are disabled and never fetched.

## Candidate observations

Draft candidates contain an `observation_date` and source-level `extractions`. Each extraction has
`brewery_id`, `source_id`, `source_sha256`, `usable`, `complete_list`, and positive `records` with
`beer_name`, `style`, `abv`, and `ibu`. The hash is an ignored-workflow safeguard: for a complete
list it must match local fetch metadata. Only usable complete lists may close absent tap runs.

Event candidates contain `brewery_id`, `event_name`, `start_at`, optional `end_at`, and `source_id`.
Food candidates contain `brewery_id`, `vendor_name`, `start_at`, optional `end_at`, and `source_id`.
Python creates stable IDs; candidates never decide lifecycle changes.

## Public data

`drafts.csv` has: `draft_id`, `brewery_id`, `beer_name`, `style`, `abv`, `ibu`, `first_seen_date`,
`last_seen_date`, `first_missing_date`, `source_id`. A blank `first_missing_date` means currently on
tap. A returning beer starts a new tap run. Names match conservatively by brewery plus normalized
case and punctuation; displayed spelling is preserved.

`events.csv` has: `event_id`, `brewery_id`, `event_name`, `start_at`, `end_at`, `source_id`.

`food-trucks.csv` has: `food_truck_event_id`, `brewery_id`, `vendor_name`, `start_at`, `end_at`,
`source_id`.

Event identity is brewery + normalized title + start time. Food identity is brewery + normalized
vendor + start value. Repeated extraction updates rather than duplicates the occurrence.

`metrics.json` is the latest derived object: `as_of_date`, `included_breweries`,
`breweries_with_draft_data`, `current_beers`, `new_beers`, `median_abv`, `brewery_events`, and
`food_truck_events`. Event and food counts include occurrences on or after the calculation date.
