"""
Tests for Phase 2 — User preference capture and normalization.
"""

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pydantic import ValidationError

from phase2.preferences import (
    UserPreferenceRequest,
    validate_and_normalize_preferences,
)
from phase2.preferences.models import (
    LocationPreference,
    OptionalFilters,
    PriceRange,
    RequestContext,
)


def test_validate_and_normalize_preferences_happy_path():
    """Full valid payload produces correct UserPreferenceRequest."""
    raw = {
        "user_id": "user_123",
        "location": {
            "city": "Bengaluru",
            "locality": "Indiranagar",
            "latitude": 12.9716,
            "longitude": 77.5946,
            "radius_km": 5.0,
        },
        "price_range": {"min": 200, "max": 1000, "currency": "INR"},
        "min_rating": 4.0,
        "cuisines": ["North Indian", "Chinese"],
        "max_results": 10,
        "optional_filters": {"vegetarian_only": False, "delivery_only": False, "open_now": False},
        "sort_preference": "best_match",
        "request_context": {"locale": "en-IN", "device_type": "web"},
    }
    result = validate_and_normalize_preferences(raw)

    assert isinstance(result, UserPreferenceRequest)
    assert result.user_id == "user_123"
    assert result.location.city == "Bengaluru"
    assert result.location.locality == "Indiranagar"
    assert result.location.latitude == 12.9716
    assert result.location.longitude == 77.5946
    assert result.location.radius_km == 5.0
    assert result.price_range.min == 200
    assert result.price_range.max == 1000
    assert result.price_range.currency == "INR"
    assert result.min_rating == 4.0
    assert result.cuisines == ["north indian", "chinese"]
    assert result.max_results == 10
    assert result.optional_filters.vegetarian_only is False
    assert result.sort_preference == "best_match"
    assert result.request_context.locale == "en-IN"
    assert result.request_context.device_type == "web"


def test_validate_and_normalize_preferences_normalizes_cuisines():
    """Cuisines are lowercased and split from comma string."""
    raw = {
        "location": {"city": "Mumbai", "locality": ""},
        "cuisines": "South Indian,  Chinese , Bakery",
    }
    result = validate_and_normalize_preferences(raw)
    assert result.cuisines == ["south indian", "chinese", "bakery"]


def test_validate_and_normalize_preferences_minimal_payload():
    """Minimal payload uses defaults for optional fields."""
    raw = {}
    result = validate_and_normalize_preferences(raw)
    assert result.user_id is None
    assert result.location.city == ""
    assert result.location.locality == ""
    assert result.location.radius_km == 10.0
    assert result.price_range.min == 0
    assert result.price_range.max == 5000
    assert result.price_range.currency == "INR"
    assert result.min_rating == 0.0
    assert result.cuisines == []
    assert result.max_results == 10
    assert result.sort_preference == "best_match"
    assert result.request_context.locale == "en-IN"
    assert result.request_context.device_type == "web"


def test_validate_and_normalize_preferences_alternate_field_names():
    """Alternate field names (e.g. from different frontends) are accepted."""
    raw = {
        "location_preference": {"city_name": "Delhi", "area": "Connaught Place"},
        "price": {"min": 500, "max": 2000},
        "minimum_rating": 4.5,
        "cuisine": "North Indian",
        "limit": 20,
        "sort": "rating",
    }
    result = validate_and_normalize_preferences(raw)
    assert result.location.city == "Delhi"
    assert result.location.locality == "Connaught Place"
    assert result.price_range.min == 500
    assert result.price_range.max == 2000
    assert result.min_rating == 4.5
    assert result.cuisines == ["north indian"]
    assert result.max_results == 20
    assert result.sort_preference == "rating"


def test_validate_and_normalize_preferences_passthrough_model():
    """If raw is already UserPreferenceRequest, return as-is."""
    req = UserPreferenceRequest(
        location=LocationPreference(city="Pune", locality="Koregaon Park"),
        price_range=PriceRange(min=300, max=1500),
        cuisines=["italian"],
        max_results=5,
    )
    result = validate_and_normalize_preferences(req)
    assert result is req
    assert result.location.city == "Pune"
    assert result.cuisines == ["italian"]


def test_validate_and_normalize_preferences_invalid_type_raises():
    """Non-dict and non-UserPreferenceRequest raises TypeError."""
    with pytest.raises(TypeError, match="raw must be a dict or UserPreferenceRequest"):
        validate_and_normalize_preferences("not a dict")
    with pytest.raises(TypeError, match="raw must be a dict or UserPreferenceRequest"):
        validate_and_normalize_preferences(123)


def test_validate_and_normalize_preferences_invalid_sort_falls_back_to_best_match():
    """Invalid sort_preference falls back to best_match."""
    raw = {"sort_preference": "invalid_sort", "location": {}}
    result = validate_and_normalize_preferences(raw)
    assert result.sort_preference == "best_match"


def test_validate_and_normalize_preferences_price_swap():
    """If min > max, they are swapped."""
    raw = {"price_range": {"min": 3000, "max": 500}, "location": {}}
    result = validate_and_normalize_preferences(raw)
    assert result.price_range.min == 500
    assert result.price_range.max == 3000


def test_user_preference_request_model_validation():
    """UserPreferenceRequest model rejects invalid values."""
    with pytest.raises(ValidationError):
        UserPreferenceRequest(
            min_rating=10.0,  # max is 5.0
        )
    with pytest.raises(ValidationError):
        UserPreferenceRequest(
            max_results=0,  # min is 1
        )
    with pytest.raises(ValidationError):
        UserPreferenceRequest(
            sort_preference="invalid",
        )


def test_user_preference_request_model_accepts_valid_sort_values():
    """All allowed sort_preference values are accepted."""
    for sort in ("best_match", "rating", "price_low", "price_high", "distance"):
        req = UserPreferenceRequest(sort_preference=sort)
        assert req.sort_preference == sort
