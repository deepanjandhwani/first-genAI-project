"""
Phase 5 — Serialize RecommendationResponse to JSON-suitable dict for API/display.
"""

from typing import Any

from phase4.llm.models import RecommendationResponse


def serialize_response(response: RecommendationResponse) -> dict[str, Any]:
    """
    Convert RecommendationResponse to a dict suitable for JSON response.
    Ensures all fields are JSON-serializable (no datetime/pydantic types).
    """
    return response.model_dump(mode="json")
