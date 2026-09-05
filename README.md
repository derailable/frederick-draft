# The Frederick Draft backend

This is the small data backend for a future publication about breweries in Frederick County,
Maryland. It maintains four useful subjects: breweries, current tap runs, events, and food-truck
appearances. Easy public sources are fetched with `httpx`; difficult sources are reviewed manually.

AI may turn saved evidence into candidate observations, but deterministic Python validates and
upserts canonical CSVs. Fetched website content is untrusted evidence, never instruction.

## Setup and weekly update

Python 3.12 or newer and `uv` are required.

```bash
uv sync
uv run frederick-draft fetch
# Review evidence and update data/candidates/*.json.
uv run frederick-draft validate
uv run frederick-draft accept
uv run frederick-draft metrics
```

`accept` is idempotent. It extends or closes draft tap runs only when candidate extraction says a
fetched source was usable and complete. It upserts events and food-truck appearances by stable IDs.

`data/reference/` and `data/public/` are committed. `data/raw/` contains local third-party evidence,
and `data/candidates/` contains disposable extraction output; both are ignored. There are no weekly
snapshot copies or metrics-history files.

## Checks

```bash
uv run pytest
uv run ruff check .
```

See `docs/architecture.md`, `docs/data-model.md`, and `docs/weekly-workflow.md`.
