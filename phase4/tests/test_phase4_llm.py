"""
Phase 4 tests: LLM orchestrator (unit + integration).
Unit tests use fallback or mock; integration test calls Groq when GROQ_API_KEY is set.
"""

import json
import pathlib
import sys
from unittest.mock import patch

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phase2.preferences.models import LocationPreference, PriceRange, UserPreferenceRequest
from phase3.ranking.models import CandidateRestaurant, ExplanationFeatures
from phase4.llm.models import RecommendationResponse, SingleRecommendation
from phase4.llm.orchestrator import run_phase4_recommendations


def _make_candidate(cid: str, name: str, city: str = "Bengaluru", rating: float = 4.2, cost: int = 800) -> CandidateRestaurant:
    return CandidateRestaurant(
        candidate_id=cid,
        restaurant_id=f"r_{cid}",
        name=name,
        locality="Indiranagar",
        city=city,
        cuisines=["north indian", "chinese"],
        average_cost_for_two=cost,
        currency="INR",
        aggregate_rating=rating,
        votes=100,
        matching_score=0.85,
        explanation_features=ExplanationFeatures(matches_cuisine=True, within_budget=True, highly_rated=True),
    )


def test_phase4_empty_candidates_returns_empty_recommendations():
    """No candidates -> empty recommendations, fallback_used=True."""
    request = UserPreferenceRequest(
        location=LocationPreference(city="Bengaluru"),
        price_range=PriceRange(min=200, max=1000),
        max_results=10,
    )
    resp = run_phase4_recommendations(request, [], use_llm=False)
    assert isinstance(resp, RecommendationResponse)
    assert resp.recommendations == []
    assert resp.metadata.fallback_used is True


def test_phase4_fallback_produces_template_explanations():
    """With use_llm=False, fallback produces top-N with template why_recommended and badges."""
    request = UserPreferenceRequest(
        location=LocationPreference(city="Bengaluru"),
        price_range=PriceRange(min=200, max=1000),
        max_results=10,
    )
    candidates = [
        _make_candidate("c1", "Spice House"),
        _make_candidate("c2", "Chinese Wok", rating=4.0, cost=600),
    ]
    resp = run_phase4_recommendations(request, candidates, use_llm=False)
    assert len(resp.recommendations) == 2
    assert resp.metadata.fallback_used is True
    assert resp.recommendations[0].rank == 1
    assert resp.recommendations[0].name == "Spice House"
    assert resp.recommendations[0].why_recommended
    assert resp.recommendations[0].badges
    assert resp.recommendations[1].rank == 2
    assert resp.user_preferences.location.get("city") == "Bengaluru"


def test_phase4_respects_max_recommendations():
    """Output length is capped by max_recommendations."""
    request = UserPreferenceRequest(
        location=LocationPreference(city="Mumbai"),
        price_range=PriceRange(min=0, max=5000),
        max_results=10,
    )
    candidates = [_make_candidate(f"c{i}", f"Restaurant {i}") for i in range(15)]
    resp = run_phase4_recommendations(request, candidates, max_recommendations=3, use_llm=False)
    assert len(resp.recommendations) == 3
    assert resp.recommendations[0].rank == 1
    assert resp.recommendations[2].rank == 3


def test_phase4_llm_failure_uses_fallback():
    """When LLM raises, fallback is used."""
    request = UserPreferenceRequest(
        location=LocationPreference(city="Delhi"),
        price_range=PriceRange(min=300, max=1500),
        max_results=5,
    )
    candidates = [_make_candidate("c1", "Test Restaurant")]
    with patch("phase4.llm.orchestrator.groq_chat_completion") as mock_groq:
        mock_groq.side_effect = ValueError("API error")
        resp = run_phase4_recommendations(request, candidates, use_llm=True)
    assert resp.metadata.fallback_used is True
    assert len(resp.recommendations) == 1
    assert resp.recommendations[0].name == "Test Restaurant"


def test_phase4_llm_invalid_json_uses_fallback():
    """When LLM returns non-JSON or invalid structure, fallback is used."""
    request = UserPreferenceRequest(
        location=LocationPreference(city="Pune"),
        price_range=PriceRange(min=0, max=2000),
        max_results=5,
    )
    candidates = [_make_candidate("c1", "Only One")]
    with patch("phase4.llm.orchestrator.groq_chat_completion") as mock_groq:
        mock_groq.return_value = ("not valid json at all", 100)
        resp = run_phase4_recommendations(request, candidates, use_llm=True)
    assert resp.metadata.fallback_used is True
    assert len(resp.recommendations) == 1


def test_phase4_llm_valid_json_uses_llm_response():
    """When LLM returns valid JSON with valid candidate_ids, use LLM order and reasons."""
    request = UserPreferenceRequest(
        location=LocationPreference(city="Bengaluru"),
        price_range=PriceRange(min=200, max=1000),
        max_results=5,
    )
    candidates = [
        _make_candidate("cand_0_r2", "Second"),
        _make_candidate("cand_1_r1", "First"),
    ]
    llm_body = json.dumps({
        "recommendations": [
            {"candidate_id": "cand_1_r1", "reason": "Best for North Indian.", "strengths": ["taste"], "best_for": ["dinner"]},
            {"candidate_id": "cand_0_r2", "reason": "Great value.", "strengths": [], "best_for": []},
        ]
    })
    with patch("phase4.llm.orchestrator.groq_chat_completion") as mock_groq:
        mock_groq.return_value = (llm_body, 250)
        resp = run_phase4_recommendations(request, candidates, use_llm=True)
    assert resp.metadata.fallback_used is False
    assert resp.metadata.llm_used
    assert len(resp.recommendations) == 2
    assert resp.recommendations[0].name == "First"
    assert resp.recommendations[0].why_recommended == "Best for North Indian."
    assert resp.recommendations[1].name == "Second"
    assert resp.recommendations[1].why_recommended == "Great value."


@pytest.mark.skipif(
    not __import__("os").environ.get("GROQ_API_KEY"),
    reason="Set GROQ_API_KEY in .env to run Groq integration test",
)
def test_phase4_integration_groq_live():
    """Integration: call real Groq API with 1–2 candidates; assert response shape."""
    request = UserPreferenceRequest(
        location=LocationPreference(city="Bengaluru"),
        price_range=PriceRange(min=300, max=1500),
        min_rating=4.0,
        cuisines=["north indian"],
        max_results=3,
    )
    candidates = [
        _make_candidate("cand_0_1", "Sample Restaurant", rating=4.5, cost=700),
    ]
    resp = run_phase4_recommendations(request, candidates, max_recommendations=3, use_llm=True)
    assert isinstance(resp, RecommendationResponse)
    assert len(resp.recommendations) >= 1
    assert resp.recommendations[0].candidate_id == "cand_0_1"
    assert resp.recommendations[0].name == "Sample Restaurant"
    assert resp.request_id
    assert resp.generated_at
    # If LLM succeeded, we have custom reason; if fallback, we have template
    assert resp.recommendations[0].why_recommended
