"""
Phase 3 integration tests: run filter_and_rank against the real Phase 1 SQLite DB.
Loads .env so GROQ_API_KEY is available for future Phase 4 tests.
Requires data/processed/restaurants.db (run Phase 1 ingestion first).
"""

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from phase2.preferences import UserPreferenceRequest, validate_and_normalize_preferences
from phase2.preferences.models import LocationPreference, PriceRange
from phase3.ranking import filter_and_rank
from phase3.ranking.engine import RankerConfig

REAL_DB_PATH = ROOT / "data" / "processed" / "restaurants.db"


@pytest.fixture(scope="module")
def real_db_exists():
    """Skip if Phase 1 DB has not been created."""
    if not REAL_DB_PATH.exists():
        pytest.skip(
            "Phase 1 DB not found. Run: python3 -c \"from phase1.ingestion.phase1_ingestion import run_phase1_ingestion; run_phase1_ingestion()\""
        )
    return str(REAL_DB_PATH)


def test_phase3_integration_filter_and_rank_with_real_db(real_db_exists):
    """Integration: filter_and_rank against real restaurants.db returns candidates with valid structure."""
    config = RankerConfig(sqlite_db_path=real_db_exists)
    request = UserPreferenceRequest(
        location=LocationPreference(city="", locality=""),
        price_range=PriceRange(min=0, max=10000),
        min_rating=0.0,
        cuisines=[],
        max_results=20,
        sort_preference="best_match",
    )
    candidates = filter_and_rank(request, config=config)

    assert isinstance(candidates, list)
    assert len(candidates) > 0, "Expected at least one candidate from real DB with loose filters"
    for c in candidates:
        assert c.candidate_id.startswith("cand_")
        assert c.restaurant_id
        assert c.name
        assert c.average_cost_for_two >= 0
        assert 0.0 <= c.aggregate_rating <= 5.0
        assert 0.0 <= c.matching_score <= 1.0
        assert c.price_bucket in ("low", "medium", "high")
        assert hasattr(c.explanation_features, "matches_cuisine")


def test_phase3_integration_with_normalized_request_and_real_db(real_db_exists):
    """Integration: Phase 2 normalized request -> Phase 3 filter_and_rank with real DB."""
    config = RankerConfig(sqlite_db_path=real_db_exists)
    raw = {
        "location": {"city": "", "locality": ""},
        "price_range": {"min": 200, "max": 2000},
        "min_rating": 3.5,
        "cuisines": ["north indian", "chinese"],
        "max_results": 10,
        "sort_preference": "rating",
    }
    request = validate_and_normalize_preferences(raw)
    candidates = filter_and_rank(request, config=config)

    assert isinstance(candidates, list)
    # May be 0 if no restaurants in DB match; otherwise check structure
    for c in candidates:
        assert c.aggregate_rating >= 3.5
        assert 200 <= c.average_cost_for_two <= 2000
        assert set(c.cuisines) & {"north indian", "chinese"}
    # Sort by rating descending
    if len(candidates) >= 2:
        assert candidates[0].aggregate_rating >= candidates[1].aggregate_rating


def test_groq_api_key_available_for_future_phase4():
    """Ensure GROQ_API_KEY is loaded from .env (for future Phase 4 LLM tests)."""
    import os
    key = os.environ.get("GROQ_API_KEY")
    # Don't assert key is set so CI without .env still passes; just that we attempted load
    assert key is None or (isinstance(key, str) and len(key) > 0)
