"""
Phase 2 — Validate and normalize raw user input into UserPreferenceRequest.
- Validates shape and types (Pydantic).
- Normalizes: lowercase cuisines, stripped strings, sensible numeric defaults.
"""

import logging
from typing import Any, Dict, List, Optional, Union

from phase2.preferences.models import (
    LocationPreference,
    OptionalFilters,
    PriceRange,
    RequestContext,
    UserPreferenceRequest,
)

logger = logging.getLogger(__name__)


def _normalize_cuisines(raw: Any) -> List[str]:
    """Normalize cuisines to lowercase, non-empty list."""
    if raw is None:
        return []
    if isinstance(raw, str):
        return [c.strip().lower() for c in raw.split(",") if c.strip()]
    if isinstance(raw, list):
        return [str(c).strip().lower() for c in raw if str(c).strip()]
    return []


def _normalize_location(raw: Any) -> Dict[str, Any]:
    """Extract and normalize location fields from raw input."""
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Any] = {
        "city": (raw.get("city") or raw.get("city_name") or "").strip()[:500],
        "locality": (raw.get("locality") or raw.get("area") or "").strip()[:500],
        "latitude": _float_or_none(raw.get("latitude"), -90, 90),
        "longitude": _float_or_none(raw.get("longitude"), -180, 180),
        "radius_km": _float_in_range(raw.get("radius_km"), 0.1, 100.0, 10.0),
    }
    places_raw = raw.get("places")
    if isinstance(places_raw, list) and places_raw:
        out["places"] = [str(p).strip()[:500] for p in places_raw if str(p).strip()]
    return out


def _float_or_none(value: Any, low: float, high: float) -> Optional[float]:
    try:
        f = float(value)
        return f if low <= f <= high else None
    except (TypeError, ValueError):
        return None


def _float_in_range(value: Any, low: float, high: float, default: float) -> float:
    try:
        f = float(value)
        return max(low, min(high, f))
    except (TypeError, ValueError):
        return default


def _normalize_price_range(raw: Any) -> Dict[str, Any]:
    """Extract and normalize price range."""
    if not isinstance(raw, dict):
        return {}
    min_val = raw.get("min")
    max_val = raw.get("max")
    try:
        min_int = max(0, int(float(str(min_val or 0).replace(",", ""))))
    except (TypeError, ValueError):
        min_int = 0
    try:
        max_int = max(0, min(1_000_000, int(float(str(max_val or 5000).replace(",", "")))))
    except (TypeError, ValueError):
        max_int = 5000
    if min_int > max_int:
        min_int, max_int = max_int, min_int
    return {
        "min": min_int,
        "max": max_int,
        "currency": (raw.get("currency") or "INR").strip()[:10] or "INR",
    }


def _normalize_optional_filters(raw: Any) -> Dict[str, bool]:
    """Extract optional filters as booleans."""
    if not isinstance(raw, dict):
        return {}
    return {
        "vegetarian_only": bool(raw.get("vegetarian_only", False)),
        "delivery_only": bool(raw.get("delivery_only", False)),
        "open_now": bool(raw.get("open_now", False)),
    }


def _normalize_request_context(raw: Any) -> Dict[str, str]:
    """Extract request context with defaults."""
    if not isinstance(raw, dict):
        return {}
    return {
        "locale": (raw.get("locale") or "en-IN").strip()[:20] or "en-IN",
        "device_type": (raw.get("device_type") or "web").strip()[:32] or "web",
    }


def _build_normalized_payload(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Turn raw user input into a dict suitable for UserPreferenceRequest validation."""
    location = _normalize_location(raw.get("location") or raw.get("location_preference") or {})
    price_range = _normalize_price_range(raw.get("price_range") or raw.get("price") or {})
    optional_filters = _normalize_optional_filters(raw.get("optional_filters") or raw.get("filters") or {})
    request_context = _normalize_request_context(raw.get("request_context") or {})

    min_rating = _float_in_range(raw.get("min_rating") or raw.get("minimum_rating"), 0.0, 5.0, 0.0)
    max_results_val = raw.get("max_results") or raw.get("limit") or 10
    try:
        max_results = max(1, min(50, int(max_results_val)))
    except (TypeError, ValueError):
        max_results = 10

    sort_raw = (raw.get("sort_preference") or raw.get("sort") or "best_match").strip().lower()
    sort_allowed = ("best_match", "rating", "price_low", "price_high", "distance")
    sort_preference = sort_raw if sort_raw in sort_allowed else "best_match"

    user_id = raw.get("user_id")
    if user_id is not None and user_id != "":
        user_id = str(user_id).strip() or None
    else:
        user_id = None

    return {
        "user_id": user_id,
        "location": location,
        "price_range": price_range,
        "min_rating": min_rating,
        "cuisines": _normalize_cuisines(raw.get("cuisines") or raw.get("cuisine")),
        "max_results": max_results,
        "optional_filters": optional_filters,
        "sort_preference": sort_preference,
        "request_context": request_context,
    }


def validate_and_normalize_preferences(
    raw: Union[Dict[str, Any], UserPreferenceRequest],
) -> UserPreferenceRequest:
    """
    Validate and normalize raw user input into a structured UserPreferenceRequest.
    - Accepts a dict (e.g. from JSON body) or an existing UserPreferenceRequest (returned as-is).
    - Normalizes: lowercase cuisines, stripped strings, numeric ranges, defaults.
    - Raises pydantic.ValidationError if required constraints are violated after normalization.
    """
    if isinstance(raw, UserPreferenceRequest):
        return raw

    if not isinstance(raw, dict):
        raise TypeError("raw must be a dict or UserPreferenceRequest")

    payload = _build_normalized_payload(raw)
    request = UserPreferenceRequest.model_validate(payload)
    logger.debug("Normalized UserPreferenceRequest: location=%s cuisines=%s", request.location, request.cuisines)
    return request
