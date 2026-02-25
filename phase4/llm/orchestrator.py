"""
Phase 4 — LLM Orchestrator: build prompt, call LLM, validate, fallback.
"""

import json
import logging
import time
from typing import Optional

from phase2.preferences import UserPreferenceRequest
from phase3.ranking.models import CandidateRestaurant
from phase4.llm.models import (
    HighlightedAttributes,
    RecommendationMetadata,
    RecommendationResponse,
    SingleRecommendation,
    UserPreferencesEcho,
)
from phase4.llm.providers.groq_provider import groq_chat_completion

logger = logging.getLogger(__name__)

# Instruction for grounded output
SYSTEM_PROMPT = """You are a restaurant recommendation assistant. You MUST only recommend restaurants from the candidate list provided. Do not invent any restaurants or details. Respond with a valid JSON object only, no other text."""

OUTPUT_SCHEMA_HINT = """
Respond with a JSON object of this exact shape (no markdown, no code block):
{"recommendations": [{"candidate_id": "<from list>", "reason": "one sentence why", "strengths": ["taste", "service"], "best_for": ["family dinner"]}]}
Include up to max_recommendations entries, in order of preference. candidate_id must be one of the candidate_id values from the list. Keep reasons short and specific to the candidate."""


def _build_user_prompt(request: UserPreferenceRequest, candidates: list[CandidateRestaurant], max_n: int) -> str:
    """Build user message with preferences and candidate list."""
    prefs = f"User wants: city={request.location.city}, locality={request.location.locality}, price INR {request.price_range.min}-{request.price_range.max}, min_rating={request.min_rating}, cuisines={request.cuisines}. max_recommendations={max_n}."
    candidates_json = [
        {
            "candidate_id": c.candidate_id,
            "name": c.name,
            "locality": c.locality,
            "city": c.city,
            "cuisines": c.cuisines,
            "average_cost_for_two": c.average_cost_for_two,
            "aggregate_rating": c.aggregate_rating,
            "price_bucket": c.price_bucket,
        }
        for c in candidates[:30]
    ]
    return prefs + "\n\nCandidates (only recommend from this list):\n" + json.dumps(candidates_json, ensure_ascii=False) + OUTPUT_SCHEMA_HINT.replace("max_recommendations", str(max_n))


def _parse_llm_response(raw: str, valid_candidate_ids: set[str]) -> list[dict]:
    """Parse LLM JSON response; return list of validated recommendation dicts (candidate_id, reason, strengths, best_for)."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    recs = data.get("recommendations") if isinstance(data, dict) else []
    if not isinstance(recs, list):
        return []
    result = []
    for r in recs:
        if not isinstance(r, dict):
            continue
        cid = r.get("candidate_id")
        if cid not in valid_candidate_ids:
            continue
        result.append({
            "candidate_id": cid,
            "reason": str(r.get("reason") or "").strip() or "Recommended for you.",
            "strengths": r.get("strengths") if isinstance(r.get("strengths"), list) else [],
            "best_for": r.get("best_for") if isinstance(r.get("best_for"), list) else [],
        })
    return result


def _candidate_by_id(candidates: list[CandidateRestaurant]) -> dict[str, CandidateRestaurant]:
    return {c.candidate_id: c for c in candidates}


def _canonical_place_key(name: str, locality: str, city: str) -> str:
    """Normalized key for dedup: same name+locality+city (case/space normalized) = same place."""
    def norm(s: str) -> str:
        return " ".join((s or "").strip().split()).lower()
    return f"{norm(name)}|{norm(locality)}|{norm(city)}"


def _fallback_badges(c: CandidateRestaurant) -> list[str]:
    badges = []
    if c.explanation_features.matches_cuisine:
        badges.append("Top Match")
    if c.explanation_features.highly_rated:
        badges.append("Highly Rated")
    if c.explanation_features.within_budget and c.price_bucket == "low":
        badges.append("Budget Friendly")
    return badges or ["Recommended"]


def _fallback_why_recommended(c: CandidateRestaurant) -> str:
    parts = []
    if c.explanation_features.matches_cuisine:
        parts.append("Matches your cuisine preferences")
    if c.explanation_features.within_budget:
        parts.append("within your budget")
    if c.explanation_features.highly_rated:
        parts.append("highly rated")
    if c.locality or c.city:
        parts.append(f"in {c.locality or c.city}")
    return ". ".join(parts) + "." if parts else "Recommended based on your filters."


def _build_single_recommendation(
    rank: int,
    c: CandidateRestaurant,
    reason: str = "",
    strengths: list[str] | None = None,
    best_for: list[str] | None = None,
) -> SingleRecommendation:
    badges = _fallback_badges(c)
    why = reason or _fallback_why_recommended(c)
    best_rev = getattr(c, "best_review", "") or ""
    top_reviews = [best_rev] if best_rev else ([c.rating_text] if c.rating_text else [])
    return SingleRecommendation(
        rank=rank,
        candidate_id=c.candidate_id,
        restaurant_id=c.restaurant_id,
        name=c.name,
        address=c.address,
        phone=getattr(c, "phone", "") or "",
        locality=c.locality,
        city=c.city,
        best_review=best_rev,
        rating_text=c.rating_text or "",
        popular_dishes=getattr(c, "popular_dishes", []) or [],
        top_reviews=top_reviews,
        cuisines=c.cuisines,
        average_cost_for_two=c.average_cost_for_two,
        currency=c.currency,
        aggregate_rating=c.aggregate_rating,
        votes=c.votes,
        distance_km=c.distance_km,
        badges=badges,
        why_recommended=why,
        highlighted_attributes=HighlightedAttributes(
            strengths=strengths or [],
            best_for=best_for or [],
        ),
    )


def _echo_preferences(request: UserPreferenceRequest) -> UserPreferencesEcho:
    return UserPreferencesEcho(
        location={"city": request.location.city, "locality": request.location.locality},
        price_range={"min": request.price_range.min, "max": request.price_range.max, "currency": request.price_range.currency},
        min_rating=request.min_rating,
        cuisines=list(request.cuisines),
    )


def run_phase4_recommendations(
    request: UserPreferenceRequest,
    candidates: list[CandidateRestaurant],
    *,
    max_recommendations: Optional[int] = None,
    llm_model: str = "llama-3.3-70b-versatile",
    use_llm: bool = True,
) -> RecommendationResponse:
    """
    Produce RecommendationResponse from Phase 3 candidates using LLM (Groq).
    If LLM is disabled, fails, or returns invalid data, falls back to top-N with template explanations.
    """
    max_n = max_recommendations or min(request.max_results, len(candidates), 10)
    if not candidates:
        return RecommendationResponse(
            user_preferences=_echo_preferences(request),
            recommendations=[],
            metadata=RecommendationMetadata(llm_used="", fallback_used=True),
        )

    candidate_map = _candidate_by_id(candidates)
    valid_ids = set(candidate_map.keys())
    start_total = time.perf_counter()

    if use_llm:
        logger.info("Phase 4: calling Groq LLM (model=%s)", llm_model)
        try:
            user_prompt = _build_user_prompt(request, candidates, max_n)
            content, llm_ms = groq_chat_completion(SYSTEM_PROMPT, user_prompt, model=llm_model)
            logger.info("Phase 4: Groq LLM completed in %s ms", llm_ms)
            parsed = _parse_llm_response(content, valid_ids)
            if parsed:
                # Build recommendations in LLM order; deduplicate by candidate_id and restaurant_id (first occurrence wins)
                recs: list[SingleRecommendation] = []
                seen_ids: set[str] = set()
                seen_restaurant_ids: set[str] = set()
                for rank, p in enumerate(parsed[:max_n], 1):
                    cid = p.get("candidate_id")
                    if not cid or cid in seen_ids:
                        continue
                    c = candidate_map.get(cid)
                    if not c:
                        continue
                    dedup_key = _canonical_place_key(c.name, c.locality, c.city)
                    if dedup_key in seen_restaurant_ids:
                        continue
                    seen_ids.add(cid)
                    seen_restaurant_ids.add(dedup_key)
                    recs.append(_build_single_recommendation(
                        rank, c,
                        reason=p.get("reason", ""),
                        strengths=p.get("strengths"),
                        best_for=p.get("best_for"),
                    ))
                if recs:
                    total_ms = int((time.perf_counter() - start_total) * 1000)
                    return RecommendationResponse(
                        user_preferences=_echo_preferences(request),
                        recommendations=recs,
                        metadata=RecommendationMetadata(
                            grounded_in_candidates=True,
                            llm_used=llm_model,
                            llm_latency_ms=llm_ms,
                            total_latency_ms=total_ms,
                            fallback_used=False,
                        ),
                    )
        except Exception as e:
            logger.warning("Phase 4 LLM failed, using fallback: %s", e)

    # Fallback: top-N by existing order; deduplicate by canonical (name, locality, city)
    seen_keys: set[str] = set()
    unique_candidates: list[CandidateRestaurant] = []
    for c in candidates:
        key = _canonical_place_key(c.name, c.locality, c.city)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique_candidates.append(c)
    recs = []
    for rank, c in enumerate(unique_candidates[:max_n], 1):
        recs.append(_build_single_recommendation(rank, c))
    total_ms = int((time.perf_counter() - start_total) * 1000)
    return RecommendationResponse(
        user_preferences=_echo_preferences(request),
        recommendations=recs,
        metadata=RecommendationMetadata(
            grounded_in_candidates=True,
            llm_used="",
            total_latency_ms=total_ms,
            fallback_used=True,
        ),
    )
