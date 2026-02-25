"""
Phase 3 — Candidate restaurant model for filter + rank output.
Matches ARCHITECTURE.md §4.3 CandidateRestaurant contract.
"""

from typing import Optional

from pydantic import BaseModel, Field


class ExplanationFeatures(BaseModel):
    """Derived features used for LLM explanation and badges."""

    matches_cuisine: bool = False
    within_budget: bool = False
    nearby: bool = False
    highly_rated: bool = False


class CandidateRestaurant(BaseModel):
    """A restaurant candidate with score and features for ranking and LLM Phase 4."""

    candidate_id: str = Field(..., description="Unique id for this candidate in the response")
    restaurant_id: str = Field(..., description="Id from restaurants table")
    name: str = Field(..., min_length=1)
    address: str = Field(default="", description="Full address for display")
    locality: str = Field(default="")
    city: str = Field(default="")
    rating_text: str = Field(default="", description="e.g. Very Good, Excellent")
    best_review: str = Field(default="", description="Single best review from reviews_list")
    popular_dishes: list[str] = Field(default_factory=list, description="From dish_liked")
    phone: str = Field(default="", description="One phone number (mobile preferred)")
    cuisines: list[str] = Field(default_factory=list)
    average_cost_for_two: int = Field(..., ge=0)
    currency: str = Field(default="INR")
    aggregate_rating: float = Field(..., ge=0.0, le=5.0)
    votes: int = Field(default=0, ge=0)
    distance_km: Optional[float] = Field(default=None, ge=0.0)
    price_bucket: str = Field(default="medium", description="low | medium | high")
    tags: list[str] = Field(default_factory=list)
    matching_score: float = Field(default=0.0, ge=0.0, le=1.0)
    explanation_features: ExplanationFeatures = Field(default_factory=ExplanationFeatures)
