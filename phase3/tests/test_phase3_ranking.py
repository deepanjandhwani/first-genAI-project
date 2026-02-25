"""
Tests for Phase 3 — Filter + Rank Engine.
Uses in-memory/fixture SQLite only; no external API keys required.

Future: Once Groq (or other LLM) API key is connected, add Phase 4 integration tests
that call the LLM orchestrator with Phase 3 candidates and assert on recommendation output.
"""

import json
import pathlib
import sqlite3
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phase2.preferences import UserPreferenceRequest, validate_and_normalize_preferences
from phase2.preferences.models import LocationPreference, PriceRange
from phase3.ranking import filter_and_rank, CandidateRestaurant
from phase3.ranking.engine import RankerConfig


def _create_fixture_db(db_path: pathlib.Path, rows: list[dict]) -> None:
    """Create SQLite DB with Phase 1 schema and insert rows."""
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
        for r in rows:
            conn.execute(
                """
                INSERT INTO restaurants (
                    restaurant_id, name, address, locality, city, cuisines,
                    average_cost_for_two, currency, aggregate_rating, rating_text, votes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    r["restaurant_id"],
                    r["name"],
                    r["address"],
                    r["locality"],
                    r["city"],
                    json.dumps(r["cuisines"]) if isinstance(r["cuisines"], list) else r["cuisines"],
                    r["average_cost_for_two"],
                    r.get("currency", "INR"),
                    r["aggregate_rating"],
                    r.get("rating_text", ""),
                    r.get("votes", 0),
                ),
            )
        conn.commit()
    finally:
        conn.close()


FIXTURE_RESTAURANTS = [
    {
        "restaurant_id": "r1",
        "name": "North Indian Kitchen",
        "address": "123 MG Road",
        "locality": "Indiranagar",
        "city": "Bengaluru",
        "cuisines": ["north indian", "mughlai"],
        "average_cost_for_two": 800,
        "currency": "INR",
        "aggregate_rating": 4.5,
        "rating_text": "Excellent",
        "votes": 500,
    },
    {
        "restaurant_id": "r2",
        "name": "Chinese Wok",
        "address": "456 Brigade Road",
        "locality": "Indiranagar",
        "city": "Bengaluru",
        "cuisines": ["chinese", "asian"],
        "average_cost_for_two": 600,
        "currency": "INR",
        "aggregate_rating": 4.2,
        "rating_text": "Very Good",
        "votes": 300,
    },
    {
        "restaurant_id": "r3",
        "name": "South Indian Delight",
        "address": "789 Koramangala",
        "locality": "Koramangala",
        "city": "Bengaluru",
        "cuisines": ["south indian", "breakfast"],
        "average_cost_for_two": 400,
        "currency": "INR",
        "aggregate_rating": 4.0,
        "rating_text": "Good",
        "votes": 200,
    },
    {
        "restaurant_id": "r4",
        "name": "Expensive Fine Dine",
        "address": "100 Whitefield",
        "locality": "Whitefield",
        "city": "Bengaluru",
        "cuisines": ["north indian", "continental"],
        "average_cost_for_two": 2500,
        "currency": "INR",
        "aggregate_rating": 4.8,
        "rating_text": "Excellent",
        "votes": 1000,
    },
]


def test_filter_and_rank_returns_candidates_for_matching_city_and_cuisine(tmp_path):
    """With city + cuisine filter, only matching restaurants are returned."""
    db_path = tmp_path / "restaurants.db"
    _create_fixture_db(db_path, FIXTURE_RESTAURANTS)

    request = UserPreferenceRequest(
        location=LocationPreference(city="Bengaluru", locality=""),
        price_range=PriceRange(min=300, max=1000),
        min_rating=3.5,
        cuisines=["north indian"],
        max_results=10,
        sort_preference="best_match",
    )
    config = RankerConfig(sqlite_db_path=str(db_path))
    result = filter_and_rank(request, config=config)

    assert len(result) >= 1
    assert all(c.city == "Bengaluru" for c in result)
    assert all("north indian" in c.cuisines for c in result)
    assert all(c.average_cost_for_two <= 1000 and c.average_cost_for_two >= 300 for c in result)
    assert all(c.aggregate_rating >= 3.5 for c in result)
    # r1 and r4 have north indian; r4 is over 1000 so excluded
    assert len(result) == 1
    assert result[0].restaurant_id == "r1"
    assert result[0].name == "North Indian Kitchen"
    assert 0 <= result[0].matching_score <= 1
    assert result[0].explanation_features.matches_cuisine is True
    assert result[0].explanation_features.within_budget is True


def test_filter_and_rank_respects_max_results(tmp_path):
    """Returned list length is at most max_results."""
    db_path = tmp_path / "restaurants.db"
    _create_fixture_db(db_path, FIXTURE_RESTAURANTS)

    request = UserPreferenceRequest(
        location=LocationPreference(city="Bengaluru"),
        price_range=PriceRange(min=0, max=3000),
        min_rating=0.0,
        cuisines=[],
        max_results=2,
        sort_preference="rating",
    )
    config = RankerConfig(sqlite_db_path=str(db_path))
    result = filter_and_rank(request, config=config)

    assert len(result) == 2
    assert result[0].aggregate_rating >= result[1].aggregate_rating


def test_filter_and_rank_sort_by_rating(tmp_path):
    """sort_preference=rating returns highest rating first."""
    db_path = tmp_path / "restaurants.db"
    _create_fixture_db(db_path, FIXTURE_RESTAURANTS)

    request = UserPreferenceRequest(
        location=LocationPreference(city="Bengaluru"),
        price_range=PriceRange(min=0, max=3000),
        min_rating=0.0,
        cuisines=[],
        max_results=10,
        sort_preference="rating",
    )
    config = RankerConfig(sqlite_db_path=str(db_path))
    result = filter_and_rank(request, config=config)

    assert len(result) == 4
    ratings = [c.aggregate_rating for c in result]
    assert ratings == sorted(ratings, reverse=True)
    assert result[0].name == "Expensive Fine Dine"
    assert result[0].aggregate_rating == 4.8


def test_filter_and_rank_sort_by_price_low(tmp_path):
    """sort_preference=price_low returns cheapest first."""
    db_path = tmp_path / "restaurants.db"
    _create_fixture_db(db_path, FIXTURE_RESTAURANTS)

    request = UserPreferenceRequest(
        location=LocationPreference(city="Bengaluru"),
        price_range=PriceRange(min=0, max=3000),
        min_rating=0.0,
        cuisines=[],
        max_results=10,
        sort_preference="price_low",
    )
    config = RankerConfig(sqlite_db_path=str(db_path))
    result = filter_and_rank(request, config=config)

    assert len(result) == 4
    costs = [c.average_cost_for_two for c in result]
    assert costs == sorted(costs)
    assert result[0].name == "South Indian Delight"
    assert result[0].average_cost_for_two == 400


def test_filter_and_rank_empty_db_returns_empty_list(tmp_path):
    """When no restaurants match or DB is empty, return []."""
    db_path = tmp_path / "restaurants.db"
    _create_fixture_db(db_path, [])

    request = UserPreferenceRequest(
        location=LocationPreference(city="Bengaluru"),
        price_range=PriceRange(min=0, max=5000),
        min_rating=0.0,
        cuisines=[],
        max_results=10,
    )
    config = RankerConfig(sqlite_db_path=str(db_path))
    result = filter_and_rank(request, config=config)
    assert result == []


def test_filter_and_rank_no_match_city_returns_empty(tmp_path):
    """Request for city with no data returns []."""
    db_path = tmp_path / "restaurants.db"
    _create_fixture_db(db_path, FIXTURE_RESTAURANTS)

    request = UserPreferenceRequest(
        location=LocationPreference(city="Mumbai"),
        price_range=PriceRange(min=0, max=5000),
        min_rating=0.0,
        cuisines=[],
        max_results=10,
    )
    config = RankerConfig(sqlite_db_path=str(db_path))
    result = filter_and_rank(request, config=config)
    assert result == []


def test_filter_and_rank_candidate_has_required_fields(tmp_path):
    """Each candidate has candidate_id, restaurant_id, matching_score, explanation_features."""
    db_path = tmp_path / "restaurants.db"
    _create_fixture_db(db_path, FIXTURE_RESTAURANTS[:1])

    request = UserPreferenceRequest(
        location=LocationPreference(city="Bengaluru"),
        price_range=PriceRange(min=0, max=1000),
        min_rating=0.0,
        cuisines=[],
        max_results=10,
    )
    config = RankerConfig(sqlite_db_path=str(db_path))
    result = filter_and_rank(request, config=config)
    assert len(result) == 1
    c = result[0]
    assert c.candidate_id.startswith("cand_")
    assert c.restaurant_id == "r1"
    assert isinstance(c.matching_score, float)
    assert hasattr(c.explanation_features, "matches_cuisine")
    assert c.price_bucket in ("low", "medium", "high")


def test_filter_and_rank_with_normalized_request(tmp_path):
    """filter_and_rank accepts request produced by Phase 2 validate_and_normalize_preferences."""
    db_path = tmp_path / "restaurants.db"
    _create_fixture_db(db_path, FIXTURE_RESTAURANTS)

    raw = {
        "location": {"city": "Bengaluru", "locality": "Indiranagar"},
        "price_range": {"min": 500, "max": 1500},
        "min_rating": 4.0,
        "cuisines": ["chinese"],
        "max_results": 5,
    }
    request = validate_and_normalize_preferences(raw)
    config = RankerConfig(sqlite_db_path=str(db_path))
    result = filter_and_rank(request, config=config)

    assert len(result) == 1
    assert result[0].restaurant_id == "r2"
    assert result[0].name == "Chinese Wok"
    assert "chinese" in result[0].cuisines
    assert result[0].locality == "Indiranagar"
