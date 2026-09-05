"""Repository path constants and small filesystem helpers."""

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parents[1]
DATA_DIR = PROJECT_ROOT / "data"
REFERENCE_DIR = DATA_DIR / "reference"
RAW_DIR = DATA_DIR / "raw" / "latest"
CANDIDATES_DIR = DATA_DIR / "candidates"
PUBLIC_DIR = DATA_DIR / "public"

BREWERIES_PATH = REFERENCE_DIR / "breweries.csv"
HOURS_PATH = REFERENCE_DIR / "hours.csv"
SOURCES_PATH = REFERENCE_DIR / "sources.json"
DRAFT_CANDIDATES_PATH = CANDIDATES_DIR / "drafts.json"
EVENT_CANDIDATES_PATH = CANDIDATES_DIR / "events.json"
FOOD_TRUCK_CANDIDATES_PATH = CANDIDATES_DIR / "food-trucks.json"
DRAFTS_PATH = PUBLIC_DIR / "drafts.csv"
EVENTS_PATH = PUBLIC_DIR / "events.csv"
FOOD_TRUCKS_PATH = PUBLIC_DIR / "food-trucks.csv"
METRICS_PATH = PUBLIC_DIR / "metrics.json"
FETCH_SUMMARY_PATH = RAW_DIR / "fetch-summary.json"


def ensure_local_directories() -> None:
    """Create ignored working directories needed by commands."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
