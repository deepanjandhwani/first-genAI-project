"""
Phase 5 tests: Display layer — serializer and FastAPI /recommendations/query.
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

from phase4.llm.models import (
    RecommendationMetadata,
    RecommendationResponse,
    SingleRecommendation,
    UserPreferencesEcho,
)
from phase5.display import create_app, serialize_response


def _create_fixture_db(db_path: pathlib.Path) -> None:
    """Create SQLite DB with Phase 1 schema and one restaurant."""
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
        conn.execute(
            """
            INSERT INTO restaurants VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "r1",
                "Test Restaurant",
                "123 Main St",
                "Indiranagar",
                "Bengaluru",
                '["north indian"]',
                800,
                "INR",
                4.5,
                "Excellent",
                100,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def test_serialize_response_returns_json_safe_dict():
    """Serialized response has required keys and is JSON-serializable."""
    response = RecommendationResponse(
        request_id="abc123",
        generated_at="2026-02-24T12:00:00Z",
        user_preferences=UserPreferencesEcho(location={"city": "Bengaluru"}, cuisines=["north indian"]),
        recommendations=[
            SingleRecommendation(
                rank=1,
                candidate_id="c1",
                restaurant_id="r1",
                name="Spice House",
                locality="Indiranagar",
                city="Bengaluru",
                cuisines=["north indian"],
                average_cost_for_two=700,
                currency="INR",
                aggregate_rating=4.5,
                badges=["Top Match"],
                why_recommended="Great for North Indian food.",
            ),
        ],
        metadata=RecommendationMetadata(grounded_in_candidates=True, fallback_used=False),
    )
    out = serialize_response(response)
    assert isinstance(out, dict)
    assert "request_id" in out
    assert out["request_id"] == "abc123"
    assert "recommendations" in out
    assert "user_preferences" in out
    assert "metadata" in out
    assert len(out["recommendations"]) == 1
    assert out["recommendations"][0]["name"] == "Spice House"
    assert out["recommendations"][0]["why_recommended"] == "Great for North Indian food."
    # Must be JSON-serializable
    json.dumps(out)


def test_serialize_response_empty_recommendations():
    """Empty recommendations list serializes correctly."""
    response = RecommendationResponse(recommendations=[])
    out = serialize_response(response)
    assert out["recommendations"] == []
    assert "metadata" in out


def test_api_post_query_returns_200_and_shape(tmp_path):
    """POST /recommendations/query with fixture DB returns 200 and RecommendationResponse shape."""
    db_path = tmp_path / "data" / "processed" / "restaurants.db"
    _create_fixture_db(db_path)
    app = create_app(sqlite_db_path=str(db_path), use_llm=False)
    client = TestClient(app)
    resp = client.post(
        "/recommendations/query",
        json={
            "location": {"city": "Bengaluru"},
            "price_range": {"min": 200, "max": 1000},
            "max_results": 5,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "request_id" in data
    assert "generated_at" in data
    assert "user_preferences" in data
    assert "recommendations" in data
    assert "metadata" in data
    assert data["user_preferences"]["location"]["city"] == "Bengaluru"
    assert len(data["recommendations"]) >= 1
    assert data["recommendations"][0]["name"] == "Test Restaurant"
    assert "why_recommended" in data["recommendations"][0]
    assert data["metadata"]["fallback_used"] is True


def test_api_post_query_empty_body_uses_defaults(tmp_path):
    """POST with empty body uses default preferences and returns 200."""
    db_path = tmp_path / "data" / "processed" / "restaurants.db"
    _create_fixture_db(db_path)
    app = create_app(sqlite_db_path=str(db_path), use_llm=False)
    client = TestClient(app)
    resp = client.post("/recommendations/query", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert "recommendations" in data
    assert "user_preferences" in data


def test_api_validation_error_returns_422(tmp_path):
    """Invalid request body returns 422 Unprocessable Entity."""
    db_path = tmp_path / "data" / "processed" / "restaurants.db"
    _create_fixture_db(db_path)
    app = create_app(sqlite_db_path=str(db_path), use_llm=False)
    client = TestClient(app)
    resp = client.post(
        "/recommendations/query",
        json={"max_results": 0},  # invalid: must be >= 1
    )
    assert resp.status_code == 422  # FastAPI validation error is 422 Unprocessable Entity
