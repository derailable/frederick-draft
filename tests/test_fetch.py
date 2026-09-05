import asyncio
import hashlib
import json
from pathlib import Path

import httpx
import pytest
import respx

from frederick_draft.fetch import fetch_sources
from frederick_draft.models import SourcesManifest


def manifest(*sources: dict[str, object]) -> SourcesManifest:
    return SourcesManifest.model_validate(
        {"version": 1, "breweries": [{"brewery_id": "test", "sources": list(sources)}]}
    )


def source(source_id: str, url: str, fetch_type: str = "html") -> dict[str, object]:
    return {
        "source_id": source_id,
        "category": "drafts",
        "url": url,
        "fetch_type": fetch_type,
        "enabled": True,
    }


@respx.mock
def test_success_metadata_sha_and_extension(tmp_path: Path) -> None:
    body = b'{"beer":"lager"}'
    respx.get("https://example.com/api").mock(
        return_value=httpx.Response(200, content=body, headers={"Content-Type": "application/json"})
    )
    sources = manifest(
        source("test-drafts", "https://example.com/api", "json"),
        {
            "source_id": "test-events",
            "category": "events",
            "url": "https://example.com/social",
            "fetch_type": "manual",
            "enabled": False,
        },
    )
    summary = asyncio.run(fetch_sources(sources, tmp_path))
    assert summary.succeeded == 1
    assert (tmp_path / "test" / "test-drafts.json").read_bytes() == body
    metadata = json.loads((tmp_path / "test" / "test-drafts.meta.json").read_text())
    assert metadata["sha256"] == hashlib.sha256(body).hexdigest()
    assert metadata["content_length"] == len(body)
    assert metadata["retrieved_at"].endswith("-04:00")
    assert len(respx.calls) == 1


@respx.mock
def test_manual_sources_are_never_fetched(tmp_path: Path) -> None:
    sources = manifest(
        {
            "source_id": "test-manual",
            "category": "drafts",
            "url": "https://example.com/manual",
            "fetch_type": "manual",
            "enabled": False,
        }
    )
    summary = asyncio.run(fetch_sources(sources, tmp_path))
    assert summary.enabled == 0
    assert not respx.calls


@pytest.mark.parametrize(
    ("fetch_type", "content_type", "extension"),
    [
        ("pdf", "application/pdf", ".pdf"),
        ("image", "image/png", ".png"),
        ("image", "image/jpeg", ".jpg"),
    ],
)
@respx.mock
def test_binary_source_extensions(
    tmp_path: Path, fetch_type: str, content_type: str, extension: str
) -> None:
    body = b"binary evidence"
    respx.get("https://example.com/evidence").mock(
        return_value=httpx.Response(200, content=body, headers={"Content-Type": content_type})
    )
    summary = asyncio.run(
        fetch_sources(
            manifest(source("test-evidence", "https://example.com/evidence", fetch_type)),
            tmp_path,
        )
    )
    assert summary.succeeded == 1
    assert (tmp_path / "test" / f"test-evidence{extension}").read_bytes() == body


@respx.mock
def test_redirect_is_followed(tmp_path: Path) -> None:
    respx.get("https://example.com/old").mock(
        return_value=httpx.Response(302, headers={"Location": "https://example.com/new"})
    )
    respx.get("https://example.com/new").mock(return_value=httpx.Response(200, text="ok"))
    summary = asyncio.run(
        fetch_sources(manifest(source("test-drafts", "https://example.com/old")), tmp_path)
    )
    assert summary.succeeded == 1
    metadata = json.loads((tmp_path / "test" / "test-drafts.meta.json").read_text())
    assert metadata["final_url"] == "https://example.com/new"


@pytest.mark.parametrize("status", [404, 403, 429])
@respx.mock
def test_http_failures_are_reported(tmp_path: Path, status: int) -> None:
    respx.get("https://example.com/fail").mock(return_value=httpx.Response(status))
    summary = asyncio.run(
        fetch_sources(manifest(source("test-drafts", "https://example.com/fail")), tmp_path)
    )
    assert summary.failed == 1
    assert summary.results[0].status_code == status
    assert not (tmp_path / "test" / "test-drafts.html").exists()


@respx.mock
def test_timeout_is_reported(tmp_path: Path) -> None:
    respx.get("https://example.com/slow").mock(side_effect=httpx.ConnectTimeout("timed out"))
    summary = asyncio.run(
        fetch_sources(manifest(source("test-drafts", "https://example.com/slow")), tmp_path)
    )
    assert summary.failed == 1
    assert "timed out" in (summary.results[0].error or "")


@respx.mock
def test_continues_after_one_failure_and_detects_unchanged(tmp_path: Path) -> None:
    respx.get("https://example.com/good").mock(return_value=httpx.Response(200, text="same"))
    respx.get("https://example.com/bad").mock(return_value=httpx.Response(500))
    data = manifest(
        source("test-good", "https://example.com/good"),
        source("test-bad", "https://example.com/bad"),
    )
    first = asyncio.run(fetch_sources(data, tmp_path))
    second = asyncio.run(fetch_sources(data, tmp_path))
    assert first.succeeded == second.succeeded == 1
    assert second.failed == 1
    assert second.unchanged == 1
