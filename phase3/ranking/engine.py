"""
Phase 3 — Filter + Rank Engine.
Reads from SQLite (Phase 1 schema), applies hard filters and soft ranking,
returns bounded CandidateRestaurant list for Phase 4.
"""

import json
import logging
import math
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from phase2.preferences import UserPreferenceRequest
from phase3.ranking.models import CandidateRestaurant, ExplanationFeatures

logger = logging.getLogger(__name__)

# Price bucket thresholds (INR cost for two)
PRICE_BUCKET_LOW_MAX = 500
PRICE_BUCKET_MEDIUM_MAX = 1500


@dataclass
class RankerConfig:
    """Optional config for the ranking engine."""

    sqlite_db_path: str = "data/processed/restaurants.db"
    top_k_max: int = 100
    # Weights for best_match score: rating, price_affinity, popularity, cuisine_match
    weight_rating: float = 0.4
    weight_price: float = 0.2
    weight_popularity: float = 0.2
    weight_cuisine: float = 0.2


def _price_bucket(cost: int) -> str:
    if cost <= PRICE_BUCKET_LOW_MAX:
        return "low"
    if cost <= PRICE_BUCKET_MEDIUM_MAX:
        return "medium"
    return "high"


def _parse_cuisines(cuisines_json: Any) -> List[str]:
    if not cuisines_json:
        return []
    if isinstance(cuisines_json, list):
        return [str(c).strip().lower() for c in cuisines_json if str(c).strip()]
    if isinstance(cuisines_json, str):
        try:
            data = json.loads(cuisines_json)
            return _parse_cuisines(data)
        except (json.JSONDecodeError, TypeError):
            return [c.strip().lower() for c in cuisines_json.split(",") if c.strip()]
    return []


def _row_to_restaurant(row: tuple, columns: List[str]) -> Dict[str, Any]:
    """Convert SQLite row to dict by column names."""
    return dict(zip(columns, row))


def _compute_score(
    row: Dict[str, Any],
    request: UserPreferenceRequest,
    config: RankerConfig,
    max_votes: int,
) -> tuple[float, ExplanationFeatures]:
    """Compute matching_score and explanation_features for one restaurant row."""
    rating = float(row.get("aggregate_rating") or 0)
    cost = int(row.get("average_cost_for_two") or 0)
    votes = int(row.get("votes") or 0)
    restaurant_cuisines = _parse_cuisines(row.get("cuisines"))

    pr = request.price_range
    min_cost, max_cost = pr.min, pr.max
    mid_budget = (min_cost + max_cost) / 2 if max_cost > min_cost else min_cost

    # Rating component (0–1)
    rating_norm = rating / 5.0

    # Price affinity: 1 if in range, else decay by distance from range
    if min_cost <= cost <= max_cost:
        price_affinity = 1.0
    else:
        spread = max(max_cost - min_cost, 1)
        dist = min(abs(cost - min_cost), abs(cost - max_cost)) if cost < min_cost or cost > max_cost else 0
        price_affinity = max(0.0, 1.0 - dist / spread)

    # Popularity (log scale, normalized by max_votes in this result set)
    max_v = max(max_votes, 1)
    popularity = math.log(1 + votes) / math.log(1 + max_v) if max_v > 0 else 0.0

    # Cuisine match
    user_cuisines = set(request.cuisines) if request.cuisines else set()
    if not user_cuisines:
        cuisine_match = 1.0
    else:
        rest_set = set(restaurant_cuisines)
        cuisine_match = 1.0 if (user_cuisines & rest_set) else 0.0

    score = (
        config.weight_rating * rating_norm
        + config.weight_price * price_affinity
        + config.weight_popularity * popularity
        + config.weight_cuisine * cuisine_match
    )

    features = ExplanationFeatures(
        matches_cuisine=(cuisine_match >= 1.0 and bool(user_cuisines)),
        within_budget=(min_cost <= cost <= max_cost),
        nearby=False,  # No geo in Phase 1; set True when locality matches if desired
        highly_rated=(rating >= request.min_rating and rating >= 4.0),
    )

    return score, features


def _apply_hard_filters(
    conn: sqlite3.Connection,
    request: UserPreferenceRequest,
) -> List[Dict[str, Any]]:
    """Return list of restaurant dicts passing hard filters (city, locality, rating, cost)."""
    cur = conn.cursor()
    city = (request.location.city or "").strip()
    locality = (request.location.locality or "").strip()
    min_rating = request.min_rating
    min_cost = request.price_range.min
    max_cost = request.price_range.max

    # Build WHERE: city match (if provided), locality optional, rating, cost
    conditions = ["1=1"]
    params: List[Any] = []

    # Location: match when city or locality equals or starts with the selected place
    # (so "Banashankari" matches "Banashankari", "Banashankari 2nd Stage", etc., but not "BTM").
    place_list: List[str] = []
    if getattr(request.location, "places", None) and request.location.places:
        place_list = [p.strip() for p in request.location.places if p and str(p).strip()]
    if not place_list:
        location_term = (city or locality or "").strip()
        if location_term:
            place_list = [location_term]
    if place_list:
        clause = " OR ".join(
            ["(LOWER(TRIM(city)) LIKE ? OR LOWER(TRIM(locality)) LIKE ?)"] * len(place_list)
        )
        conditions.append(f"({clause})")
        for p in place_list:
            prefix = (p or "").lower().strip() + "%"
            params.append(prefix)
            params.append(prefix)
    conditions.append("aggregate_rating >= ?")
    params.append(min_rating)
    conditions.append("average_cost_for_two >= ?")
    params.append(min_cost)
    conditions.append("average_cost_for_two <= ?")
    params.append(max_cost)

    sql = f"""
        SELECT restaurant_id, name, address, locality, city, cuisines,
               average_cost_for_two, currency, aggregate_rating, rating_text, votes,
               best_review, dish_liked, phone
        FROM restaurants
        WHERE {' AND '.join(conditions)}
    """
    try:
        cur.execute(sql, params)
    except sqlite3.OperationalError:
        sql_legacy = f"""
            SELECT restaurant_id, name, address, locality, city, cuisines,
                   average_cost_for_two, currency, aggregate_rating, rating_text, votes
            FROM restaurants
            WHERE {' AND '.join(conditions)}
        """
        cur.execute(sql_legacy, params)
    columns = [d[0] for d in cur.description]
    rows = [_row_to_restaurant(r, columns) for r in cur.fetchall()]

    # Cuisine filter in Python (restaurant must have at least one requested cuisine if any)
    if request.cuisines:
        user_cuisines = set(c.strip().lower() for c in request.cuisines)
        rows = [r for r in rows if user_cuisines & set(_parse_cuisines(r.get("cuisines")))]

    # One row per restaurant: deduplicate by restaurant_id, then by canonical (name, locality, city)
    def _norm(s: Any) -> str:
        return " ".join(str(s or "").strip().split()).lower()

    seen_keys: set[str] = set()
    unique_rows: List[Dict[str, Any]] = []
    for r in rows:
        rid = str(r.get("restaurant_id") or "").strip()
        key = rid if rid else f"{_norm(r.get('name'))}|{_norm(r.get('locality'))}|{_norm(r.get('city'))}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique_rows.append(r)

    # Second pass: one row per canonical place (same name+locality+city = same place, even if different restaurant_id)
    canonical_keys: set[str] = set()
    result_rows: List[Dict[str, Any]] = []
    for r in unique_rows:
        ckey = f"{_norm(r.get('name'))}|{_norm(r.get('locality'))}|{_norm(r.get('city'))}"
        if ckey in canonical_keys:
            continue
        canonical_keys.add(ckey)
        result_rows.append(r)
    return result_rows


def _sort_candidates(
    candidates: List[CandidateRestaurant],
    sort_preference: str,
) -> List[CandidateRestaurant]:
    """Sort by sort_preference: best_match, rating, price_low, price_high, distance."""
    if sort_preference == "rating":
        return sorted(candidates, key=lambda c: (c.aggregate_rating, c.votes), reverse=True)
    if sort_preference == "price_low":
        return sorted(candidates, key=lambda c: (c.average_cost_for_two, -c.aggregate_rating))
    if sort_preference == "price_high":
        return sorted(candidates, key=lambda c: (-c.average_cost_for_two, -c.aggregate_rating))
    if sort_preference == "distance":
        # No geo: sort by matching_score then rating
        return sorted(candidates, key=lambda c: (c.distance_km or 999, -c.matching_score, -c.aggregate_rating))
    # best_match
    return sorted(candidates, key=lambda c: (-c.matching_score, -c.aggregate_rating, -c.votes))


def filter_and_rank(
    request: UserPreferenceRequest,
    sqlite_path: Optional[str] = None,
    config: Optional[RankerConfig] = None,
) -> List[CandidateRestaurant]:
    """
    Load restaurants from SQLite, apply hard filters, score and rank, return top-K candidates.
    Uses Phase 1 schema (restaurants table). No API key required.
    """
    if config is None:
        config = RankerConfig()
    db_path = sqlite_path or config.sqlite_db_path

    try:
        conn = sqlite3.connect(db_path)
    except sqlite3.OperationalError as e:
        logger.warning("SQLite open failed for %s: %s", db_path, e)
        return []

    try:
        rows = _apply_hard_filters(conn, request)
    finally:
        conn.close()

    if not rows:
        logger.info("No restaurants passed hard filters for request city=%s", request.location.city)
        return []

    max_votes = max(int(r.get("votes") or 0) for r in rows)
    candidates: List[CandidateRestaurant] = []
    for i, row in enumerate(rows):
        score, features = _compute_score(row, request, config, max_votes)
        cuisines = _parse_cuisines(row.get("cuisines"))
        cost = int(row.get("average_cost_for_two") or 0)
        cand_id = f"cand_{i}_{row.get('restaurant_id', '')}"
        dish_liked_raw = row.get("dish_liked")
        if isinstance(dish_liked_raw, str):
            try:
                data = json.loads(dish_liked_raw)
                popular_dishes = [str(x).strip() for x in data if str(x).strip()][:15]
            except (json.JSONDecodeError, TypeError):
                popular_dishes = [x.strip() for x in dish_liked_raw.split(",") if x.strip()][:15]
        elif isinstance(dish_liked_raw, list):
            popular_dishes = [str(x).strip() for x in dish_liked_raw if str(x).strip()][:15]
        else:
            popular_dishes = []
        candidates.append(
            CandidateRestaurant(
                candidate_id=cand_id,
                restaurant_id=str(row.get("restaurant_id", "")),
                name=str(row.get("name", "")).strip() or "Unknown",
                address=str(row.get("address", "")).strip(),
                locality=str(row.get("locality", "")).strip(),
                city=str(row.get("city", "")).strip(),
                rating_text=str(row.get("rating_text", "")).strip(),
                best_review=str(row.get("best_review", "")).strip(),
                popular_dishes=popular_dishes,
                phone=str(row.get("phone", "")).strip(),
                cuisines=cuisines,
                average_cost_for_two=cost,
                currency=str(row.get("currency", "INR")).strip() or "INR",
                aggregate_rating=float(row.get("aggregate_rating") or 0),
                votes=int(row.get("votes") or 0),
                distance_km=None,
                price_bucket=_price_bucket(cost),
                tags=[],
                matching_score=round(score, 4),
                explanation_features=features,
            )
        )

    candidates = _sort_candidates(candidates, request.sort_preference)
    top_k = min(request.max_results, config.top_k_max)
    result = candidates[:top_k]
    logger.info("Phase 3 filter_and_rank: %d candidates after filters, returning top %d", len(candidates), len(result))
    return result
