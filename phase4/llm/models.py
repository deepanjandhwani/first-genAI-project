"""
Phase 4 — Recommendation response models.
Matches ARCHITECTURE.md §4.5 RecommendationResponse contract.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


class UserPreferencesEcho(BaseModel):
    """Echo of user preferences in the response."""

    location: dict[str, str] = Field(default_factory=lambda: {"city": "", "locality": ""})
    price_range: dict[str, Any] = Field(default_factory=lambda: {"min": 0, "max": 5000, "currency": "INR"})
    min_rating: float = 0.0
    cuisines: list[str] = Field(default_factory=list)


class HighlightedAttributes(BaseModel):
    """LLM-generated highlights for a recommendation."""

    strengths: list[str] = Field(default_factory=list)
    best_for: list[str] = Field(default_factory=list)


class SingleRecommendation(BaseModel):
    """One recommended restaurant with explanation and metadata."""

    rank: int = Field(..., ge=1)
    candidate_id: str = Field(...)
    restaurant_id: str = Field(...)
    name: str = Field(...)
    address: str = Field(default="")
    phone: str = Field(default="")
    locality: str = Field(default="")
    city: str = Field(default="")
    best_review: str = Field(default="", description="Single best review from reviews_list")
    rating_text: str = Field(default="", description="e.g. Very Good, Excellent — fallback for review line")
    popular_dishes: list[str] = Field(default_factory=list, description="From dish_liked")
    top_reviews: list[str] = Field(default_factory=list, description="Deprecated: use best_review")
    cuisines: list[str] = Field(default_factory=list)
    average_cost_for_two: int = Field(..., ge=0)
    currency: str = Field(default="INR")
    aggregate_rating: float = Field(..., ge=0.0, le=5.0)
    votes: int = Field(default=0, ge=0)
    distance_km: Optional[float] = None
    badges: list[str] = Field(default_factory=list)
    why_recommended: str = Field(default="")
    highlighted_attributes: HighlightedAttributes = Field(default_factory=HighlightedAttributes)


class RecommendationMetadata(BaseModel):
    """Metadata about how the response was generated."""

    grounded_in_candidates: bool = True
    llm_used: str = Field(default="")
    llm_latency_ms: Optional[int] = None
    total_latency_ms: Optional[int] = None
    fallback_used: bool = False


class RecommendationResponse(BaseModel):
    """Full recommendation response for Phase 5 display."""

    request_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    user_preferences: UserPreferencesEcho = Field(default_factory=UserPreferencesEcho)
    recommendations: list[SingleRecommendation] = Field(default_factory=list)
    metadata: RecommendationMetadata = Field(default_factory=RecommendationMetadata)
