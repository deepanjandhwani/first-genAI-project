"""
End-to-end test: all phases connected (2 -> 3 -> 4 -> 5) with fixture DB.
Phase 1 is independent (populates DB); this test uses a fixture DB to verify the rest of the pipeline.
"""

import json
import pathlib
import sqlite3
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient


def _create_fixture_db(db_path: pathlib.Path) -> None:
    """Create SQLite DB with Phase 1 schema (same as phase1 ingestion output)."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE restaurants (
                restaurant_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                address TEXT NOT NULL,
                locality TEXT NOT NULL,
                city TEXT NOT NULL,
                cuisines TEXT NOT NULL,
                average_cost_for_two INTEGER NOT NULL,
                currency TEXT NOT NULL,
                aggregate_rating REAL NOT NULL,
                rating_text TEXT,
                votes INTEGER NOT NULL
            )
            """
        )
        for row in [
            ("r1", "E2E Restaurant One", "1 Main St", "Indiranagar", "Bengaluru", '["north indian","chinese"]', 700, "INR", 4.5, "Excellent", 200),
            ("r2", "E2E Restaurant Two", "2 Side Rd", "Koramangala", "Bengaluru", '["south indian"]', 400, "INR", 4.0, "Good", 100),
        ]:
            conn.execute(
                "INSERT INTO restaurants VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                row,
            )
        conn.commit()
    finally:
        conn.close()


def test_e2e_all_phases_connected_in_code(tmp_path):
    """Run Phase 2 -> 3 -> 4 -> 5 in code; assert data flows through."""
    db_path = tmp_path / "data" / "processed" / "restaurants.db"
    _create_fixture_db(db_path)

    from phase2.preferences import validate_and_normalize_preferences
    from phase3.ranking import filter_and_rank
    from phase3.ranking.engine import RankerConfig
    from phase4.llm import run_phase4_recommendations
    from phase5.display.serializer import serialize_response

    raw = {
        "location": {"city": "Bengaluru", "locality": "Indiranagar"},
        "price_range": {"min": 300, "max": 1000},
        "min_rating": 4.0,
        "cuisines": ["north indian"],
        "max_results": 5,
    }
    request = validate_and_normalize_preferences(raw)
    config = RankerConfig(sqlite_db_path=str(db_path))
    candidates = filter_and_rank(request, config=config)
    response = run_phase4_recommendations(request, candidates, use_llm=False)
    out = serialize_response(response)

    assert request.location.city == "Bengaluru"
    assert len(candidates) == 1
    assert candidates[0].name == "E2E Restaurant One"
    assert len(response.recommendations) == 1
    assert response.recommendations[0].name == "E2E Restaurant One"
    assert response.recommendations[0].why_recommended
    assert out["request_id"]
    assert out["recommendations"][0]["name"] == "E2E Restaurant One"
    assert "why_recommended" in out["recommendations"][0]
    json.dumps(out)


def test_e2e_api_returns_same_pipeline_result(tmp_path):
    """POST /recommendations/query runs Phase 2->3->4->5 and returns consistent JSON."""
    db_path = tmp_path / "data" / "processed" / "restaurants.db"
    _create_fixture_db(db_path)

    from phase5.display import create_app
    app = create_app(sqlite_db_path=str(db_path), use_llm=False)
    client = TestClient(app)

    resp = client.post(
        "/recommendations/query",
        json={
            "location": {"city": "Bengaluru"},
            "price_range": {"min": 200, "max": 1500},
            "cuisines": ["north indian", "chinese"],
            "max_results": 3,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "recommendations" in data
    assert len(data["recommendations"]) >= 1
    names = [r["name"] for r in data["recommendations"]]
    assert "E2E Restaurant One" in names
    assert all("why_recommended" in r for r in data["recommendations"])
    assert data["user_preferences"]["location"]["city"] == "Bengaluru"
    assert data["metadata"]["grounded_in_candidates"] is True
