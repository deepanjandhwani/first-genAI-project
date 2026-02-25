"""
Pydantic models for Phase 2 — User preference capture.
Matches ARCHITECTURE.md §4.1 UserPreferenceRequest contract.
"""

from typing import Any, Literal, List, Optional

from pydantic import BaseModel, Field


class LocationPreference(BaseModel):
    """User location: city/locality, optional multiple places, and optional coordinates + radius."""

    city: str = Field(default="", min_length=0, description="City name")
    locality: str = Field(default="", min_length=0, description="Locality or area")
    places: Optional[List[str]] = Field(default=None, description="Multiple area names (overrides city/locality when set)")
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    radius_km: float = Field(default=10.0, ge=0.1, le=100.0, description="Search radius in km when lat/long provided")


class PriceRange(BaseModel):
    """Min/max cost for two people."""

    min: int = Field(default=0, ge=0, description="Minimum cost for two")
    max: int = Field(default=5000, ge=0, le=1_000_000, description="Maximum cost for two")
    currency: str = Field(default="INR", min_length=1, max_length=10)


class OptionalFilters(BaseModel):
    """Optional filters (vegetarian, delivery, open now)."""

    vegetarian_only: bool = False
    delivery_only: bool = False
    open_now: bool = False


class RequestContext(BaseModel):
    """Request metadata (locale, device)."""

    locale: str = Field(default="en-IN", min_length=1, max_length=20)
    device_type: str = Field(default="web", min_length=1, max_length=32)


class UserPreferenceRequest(BaseModel):
    """
    Normalized user preference request for downstream Phase 3 (filter + rank).
    Produced by Phase 2 from raw user inputs.
    """

    user_id: Optional[str] = None
    location: LocationPreference = Field(default_factory=LocationPreference)
    price_range: PriceRange = Field(default_factory=PriceRange)
    min_rating: float = Field(default=0.0, ge=0.0, le=5.0)
    cuisines: list[str] = Field(default_factory=list, min_length=0, max_length=50)
    max_results: int = Field(default=10, ge=1, le=50)
    optional_filters: OptionalFilters = Field(default_factory=OptionalFilters)
    sort_preference: Literal["best_match", "rating", "price_low", "price_high", "distance"] = "best_match"
    request_context: RequestContext = Field(default_factory=RequestContext)

    model_config = {"extra": "forbid"}
