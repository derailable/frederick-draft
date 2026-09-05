"""Async HTTP acquisition and local evidence metadata."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from .models import FetchType, RetrievalMetadata, SourceDefinition, SourcesManifest
from .paths import FETCH_SUMMARY_PATH, RAW_DIR, ensure_local_directories

USER_AGENT = "FrederickDraft/0.1 (+https://derailable.com/frederick-draft/)"
TIMEOUT = httpx.Timeout(20.0, connect=10.0)


@dataclass(frozen=True)
class FetchResult:
    brewery_id: str
    source_id: str
    category: str
    outcome: str
    retrieved_at: str | None = None
    status_code: int | None = None
    sha256: str | None = None
    changed: bool | None = None
    error: str | None = None


@dataclass(frozen=True)
class FetchSummary:
    retrieved_at: str
    configured: int
    enabled: int
    results: list[FetchResult]

    @property
    def succeeded(self) -> int:
        return sum(result.outcome == "fetched" for result in self.results)

    @property
    def failed(self) -> int:
        return sum(result.outcome == "failed" for result in self.results)

    @property
    def changed(self) -> int:
        return sum(result.changed is True for result in self.results)

    @property
    def unchanged(self) -> int:
        return sum(result.changed is False for result in self.results)


def _extension(source: SourceDefinition, content_type: str | None) -> str:
    media_type = (content_type or "").split(";", 1)[0].strip().lower()
    if source.fetch_type == FetchType.JSON or media_type.endswith("/json") or "+json" in media_type:
        return ".json"
    if source.fetch_type == FetchType.ICAL or "text/calendar" in media_type:
        return ".ics"
    if source.fetch_type == FetchType.HTML or "html" in media_type:
        return ".html"
    if source.fetch_type == FetchType.PDF or media_type == "application/pdf":
        return ".pdf"
    if source.fetch_type == FetchType.IMAGE or media_type.startswith("image/"):
        return {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
        }.get(media_type, ".img")
    return ".txt"


def _old_hash(directory: Path, source_id: str) -> str | None:
    meta_path = directory / f"{source_id}.meta.json"
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8")).get("sha256")
    except (json.JSONDecodeError, OSError):
        return None


async def _fetch_one(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    brewery_id: str,
    source: SourceDefinition,
    raw_dir: Path,
) -> FetchResult:
    try:
        async with semaphore:
            response = await client.get(str(source.url))
    except httpx.HTTPError as exc:
        return FetchResult(
            brewery_id=brewery_id,
            source_id=source.source_id,
            category=source.category,
            outcome="failed",
            retrieved_at=datetime.now(ZoneInfo("America/New_York")).isoformat(),
            error=str(exc),
        )

    if response.status_code >= 400:
        return FetchResult(
            brewery_id=brewery_id,
            source_id=source.source_id,
            category=source.category,
            outcome="failed",
            retrieved_at=datetime.now(ZoneInfo("America/New_York")).isoformat(),
            status_code=response.status_code,
            error=f"HTTP {response.status_code}",
        )

    body = response.content
    digest = hashlib.sha256(body).hexdigest()
    target_dir = raw_dir / brewery_id
    target_dir.mkdir(parents=True, exist_ok=True)
    previous = _old_hash(target_dir, source.source_id)
    changed = previous != digest
    content_type = response.headers.get("content-type")
    body_path = target_dir / f"{source.source_id}{_extension(source, content_type)}"
    body_path.write_bytes(body)
    retrieved_at = datetime.now(ZoneInfo("America/New_York"))
    metadata = RetrievalMetadata(
        brewery_id=brewery_id,
        source_id=source.source_id,
        category=source.category,
        requested_url=source.url,
        final_url=str(response.url),
        retrieved_at=retrieved_at,
        status_code=response.status_code,
        content_type=content_type,
        content_length=len(body),
        sha256=digest,
        etag=response.headers.get("etag"),
        last_modified=response.headers.get("last-modified"),
        changed=changed,
    )
    (target_dir / f"{source.source_id}.meta.json").write_text(
        metadata.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    return FetchResult(
        brewery_id=brewery_id,
        source_id=source.source_id,
        category=source.category,
        outcome="fetched",
        retrieved_at=retrieved_at.isoformat(),
        status_code=response.status_code,
        sha256=digest,
        changed=changed,
    )


async def fetch_sources(
    manifest: SourcesManifest,
    raw_dir: Path = RAW_DIR,
    *,
    client: httpx.AsyncClient | None = None,
    concurrency: int = 4,
) -> FetchSummary:
    """Fetch enabled non-manual sources, allowing individual failures."""
    configured = sum(len(group.sources) for group in manifest.breweries)
    selected = [
        (group.brewery_id, source)
        for group in manifest.breweries
        for source in group.sources
        if source.enabled and source.fetch_type != FetchType.MANUAL
    ]
    semaphore = asyncio.Semaphore(concurrency)
    owns_client = client is None
    active_client = client or httpx.AsyncClient(
        follow_redirects=True,
        timeout=TIMEOUT,
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
    )
    try:
        results = await asyncio.gather(
            *(
                _fetch_one(active_client, semaphore, brewery_id, source, raw_dir)
                for brewery_id, source in selected
            )
        )
    finally:
        if owns_client:
            await active_client.aclose()
    return FetchSummary(
        retrieved_at=datetime.now(ZoneInfo("America/New_York")).isoformat(),
        configured=configured,
        enabled=len(selected),
        results=list(results),
    )


def save_summary(summary: FetchSummary, path: Path = FETCH_SUMMARY_PATH) -> None:
    ensure_local_directories()
    payload = asdict(summary)
    payload.update(
        succeeded=summary.succeeded,
        failed=summary.failed,
        changed=summary.changed,
        unchanged=summary.unchanged,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

