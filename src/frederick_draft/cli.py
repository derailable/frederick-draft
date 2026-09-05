"""Typer command line interface."""

from __future__ import annotations

import asyncio

import typer

from .fetch import fetch_sources, save_summary
from .metrics import calculate_metrics, write_metrics
from .normalize import write_canonical
from .paths import METRICS_PATH, ensure_local_directories
from .validate import (
    DataValidationError,
    validate_all,
    validate_reference,
)

app = typer.Typer(no_args_is_help=True, help="The Frederick Draft backend data pipeline.")


def _fail(exc: Exception) -> None:
    typer.echo(f"Validation failed:\n{exc}", err=True)
    raise typer.Exit(1)


@app.command()
def fetch() -> None:
    """Fetch enabled first-party sources into ignored local evidence storage."""
    ensure_local_directories()
    try:
        _, _, manifest = validate_reference()
    except (DataValidationError, OSError) as exc:
        _fail(exc)
    summary = asyncio.run(fetch_sources(manifest))
    save_summary(summary)
    typer.echo(f"{summary.enabled} enabled sources")
    typer.echo(
        f"{summary.succeeded} fetched; {summary.unchanged} unchanged; {summary.failed} failed"
    )
    changed_drafts = [
        item.source_id for item in summary.results if item.category == "drafts" and item.changed
    ]
    if changed_drafts:
        typer.echo("Draft sources changed: " + ", ".join(changed_drafts))
    for item in summary.results:
        if item.outcome == "failed":
            typer.echo(f"FAILED {item.source_id}: {item.error}", err=True)
    if summary.failed:
        raise typer.Exit(1)


@app.command()
def validate() -> None:
    """Validate all reference and candidate datasets."""
    try:
        data = validate_all()
    except (DataValidationError, OSError) as exc:
        _fail(exc)
    draft_count = sum(len(item.records) for item in data.drafts.extractions)
    typer.echo(f"Valid: {draft_count} drafts, {len(data.events.records)} events, "
               f"{len(data.food_trucks.records)} food trucks")


@app.command()
def accept() -> None:
    """Validate and idempotently update the canonical datasets."""
    try:
        data = validate_all()
        write_canonical(data)
    except (DataValidationError, OSError, ValueError) as exc:
        _fail(exc)
    draft_count = sum(len(item.records) for item in data.drafts.extractions)
    typer.echo(f"Accepted {draft_count} drafts, {len(data.events.records)} events, "
               f"{len(data.food_trucks.records)} food trucks")


@app.command("metrics")
def metrics_command() -> None:
    """Calculate and write deterministic publication metrics."""
    try:
        metrics = calculate_metrics()
        write_metrics(metrics)
    except (DataValidationError, OSError, ValueError) as exc:
        _fail(exc)
    typer.echo(f"Wrote {METRICS_PATH.name}: {metrics['current_beers']} current beers")
if __name__ == "__main__":
    app()
