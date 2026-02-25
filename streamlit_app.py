"""
Streamlit UI for the Restaurant Recommendation pipeline.
Run: streamlit run streamlit_app.py
Uses Phase 2 → 3 → 4 (validate preferences, filter+rank, LLM or fallback).
Styled to match the local Zomato AI Restaurant Recommendation Platform.
"""

import sqlite3
from pathlib import Path

import streamlit as st

# Load .env from project root so GROQ_API_KEY is set before Phase 4
try:
    from dotenv import load_dotenv
    _root = Path(__file__).resolve().parent
    load_dotenv(_root / ".env")
except ImportError:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent

# Header with INLINE styles so it always shows on Streamlit Cloud (no dependency on global CSS)
ZOMATO_HEADER = """
<div style="
  background: linear-gradient(135deg, #e23744 0%, #c42f3a 100%);
  color: white;
  padding: 1.5rem 2rem;
  text-align: center;
  box-shadow: 0 4px 14px rgba(226, 55, 68, 0.25);
  margin: -1rem -1rem 1.5rem -1rem;
  border-radius: 0;
">
  <div style="font-size: 1.85rem; font-weight: 700; letter-spacing: 0.06em;">🍴 ZOMATO</div>
  <div style="font-size: 0.875rem; margin-top: 0.35rem; font-weight: 500;">AI Restaurant Recommendation Platform</div>
</div>
"""

# Extra CSS for form card and button (applies when Streamlit allows it)
ZOMATO_CSS = """
<style>
  div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stSelectbox"]) { background: #fff; padding: 1.5rem; border-radius: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); margin-bottom: 1rem; }
  .stButton > button { background: linear-gradient(135deg, #e23744 0%, #c42f3a 100%) !important; color: white !important; border: none !important; border-radius: 999px !important; font-weight: 600 !important; }
  label { text-transform: uppercase !important; font-size: 0.7rem !important; color: #71717a !important; letter-spacing: 0.06em !important; }
</style>
"""


def get_places(db_path: Path) -> list[str]:
    """Return distinct city/locality names for dropdown."""
    if not db_path.exists():
        return []
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.execute(
            "SELECT DISTINCT city FROM restaurants WHERE TRIM(city) != '' "
            "UNION SELECT DISTINCT locality FROM restaurants WHERE TRIM(locality) != '' "
            "ORDER BY 1"
        )
        places = [row[0] for row in cur.fetchall()]
        conn.close()
        return places
    except Exception:
        return []


def run_recommendations(
    place: str,
    min_price: int,
    max_price: int,
    min_rating: float,
    cuisines: list[str],
    max_results: int,
    db_path: Path,
    use_llm: bool = True,
):
    """Build request, run Phase 2 → 3 → 4, return serialized response dict."""
    from phase2.preferences import validate_and_normalize_preferences
    from phase3.ranking import filter_and_rank
    from phase3.ranking.engine import RankerConfig
    from phase4.llm import run_phase4_recommendations
    from phase5.display.serializer import serialize_response

    raw = {
        "location": {"places": [place.strip()]} if place else {},
        "price_range": {"min": min_price, "max": max_price, "currency": "INR"},
        "min_rating": min_rating,
        "cuisines": [c.strip().lower() for c in cuisines if c.strip()],
        "max_results": max_results,
    }
    request = validate_and_normalize_preferences(raw)
    config = RankerConfig(sqlite_db_path=str(db_path))
    candidates = filter_and_rank(request, config=config)
    response = run_phase4_recommendations(request, candidates, use_llm=use_llm)
    return serialize_response(response)


st.set_page_config(
    page_title="Zomato AI · Restaurant Recommendations",
    page_icon="🍴",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Header first (inline styles = always visible on Cloud)
st.markdown(ZOMATO_HEADER, unsafe_allow_html=True)
st.markdown(ZOMATO_CSS, unsafe_allow_html=True)

# If you see "ZOMATO" in red above and form below (no sidebar), this is the new UI.
db_path = PROJECT_ROOT / "data" / "processed" / "restaurants.db" / "data" / "processed" / "restaurants.db"
places_list = get_places(db_path) if db_path.exists() else []
place_options = [""] + (places_list if places_list else (["(Run Phase 1 ingestion first)"] if not db_path.exists() else []))

# Form in main area (same order as local UI: PLACE, MAX PRICE, MIN RATING, CUISINES, MAX RESULTS)
place = st.selectbox(
    "PLACE",
    options=place_options,
    index=0,
    placeholder="Select areas",
    help="Select city or locality",
)

col1, col2 = st.columns(2)
with col1:
    max_price_val = st.number_input(
        "MAX PRICE (INR)",
        min_value=0,
        value=0,
        step=500,
        placeholder="No max",
        help="Leave 0 for no maximum",
    )
max_price = 999999 if max_price_val == 0 else max_price_val

with col2:
    min_rating = st.number_input(
        "MIN RATING",
        min_value=0.0,
        max_value=5.0,
        value=4.0,
        step=0.1,
        format="%.1f",
    )

cuisines_text = st.text_input(
    "CUISINES",
    placeholder="Select cuisines (e.g. North Indian, Chinese)",
)
cuisines = [c.strip() for c in (cuisines_text or "").split(",") if c.strip()]

max_results = st.number_input("MAX RESULTS", min_value=1, max_value=50, value=10)

use_llm = st.checkbox("Use LLM (Groq) for explanations", value=True, help="Uncheck for template-only explanations")

submitted = st.button("Get AI Recommendations")

if submitted:
    if not db_path.exists():
        st.error("Database not found. Run Phase 1 ingestion first: `data/processed/restaurants.db`")
    elif not place and places_list:
        st.error("Please select a location.")
    else:
        with st.spinner("Finding recommendations…"):
            try:
                data = run_recommendations(
                    place=place or (places_list[0] if places_list else ""),
                    min_price=0,
                    max_price=max_price,
                    min_rating=min_rating,
                    cuisines=cuisines,
                    max_results=max_results,
                    db_path=db_path,
                    use_llm=use_llm,
                )
            except Exception as e:
                st.exception(e)
                st.stop()

        recs = (data.get("recommendations") or [])[:]
        recs.sort(key=lambda r: (float(r.get("aggregate_rating") or 0)), reverse=True)

        if not recs:
            st.info("No recommendations found. Try relaxing location or filters.")
        else:
            st.success(f"Found {len(recs)} recommendation(s). Sorted by rating.")
            for r in recs:
                name = r.get("name") or "—"
                loc_parts = [r.get("locality"), r.get("city")]
                loc = " · ".join(p for p in loc_parts if p)
                cost = r.get("average_cost_for_two") or 0
                rating = r.get("aggregate_rating") or 0
                badges = r.get("badges") or []
                why = r.get("why_recommended") or ""
                cuisines_display = r.get("cuisines") or []
                dishes = r.get("popular_dishes") or []
                address = (r.get("address") or "").strip()

                with st.container():
                    st.markdown(f"### {name}")
                    st.caption(f"📍 {loc}" if loc else "—")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.metric("₹ for two", cost)
                    with c2:
                        st.metric("Rating", f"★ {rating}")
                    with c3:
                        st.markdown(" ".join(f"`{b}`" for b in badges) if badges else "—")
                    if cuisines_display:
                        st.markdown("**Cuisines:** " + ", ".join(cuisines_display[:6]))
                    if why:
                        st.markdown(f"*{why}*")
                    if dishes:
                        st.markdown("**Popular dishes:** " + ", ".join(dishes[:8]))
                    if address:
                        st.markdown(f"**Address:** {address}")
                    st.button("Book a table", key=f"book_{r.get('candidate_id', id(r))}")
                    st.divider()
