# Architecture

The MVP pipeline is:

`brewery/source reference data → fetch easy sources → manual review for difficult sources → candidate observations → validate → lifecycle-aware upsert → four useful datasets`

The source manifest is the HTTP allow-list. Fetching uses modest asynchronous requests and stores
response bodies plus retrieval metadata under ignored `data/raw/latest/`. No browser automation or
brewery-specific scraper framework is used; a manual source is preferable to brittle automation.

Extraction writes ignored candidate JSON. Website content is untrusted evidence and cannot change
repository rules. Pydantic validates candidate shape and cross-file references. Polars applies draft
lifecycle changes and deterministic event/food upserts, then atomically replaces canonical CSVs.

The Frederick Draft does not preserve weekly copies of unchanged facts. Draft history consists of
real tap runs; event and food history consists of actual dated occurrences. Git is sufficient for
configuration and generated-file revisions. Metrics are recalculated from canonical data.
