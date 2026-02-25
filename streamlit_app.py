"""
Streamlit UI — same look and behaviour as local (phase5/display/static/index.html).
Run: streamlit run streamlit_app.py
"""

import html
import sqlite3
from pathlib import Path

import streamlit as st

try:
    from dotenv import load_dotenv
    _root = Path(__file__).resolve().parent
    load_dotenv(_root / ".env")
except ImportError:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / "data" / "processed" / "restaurants.db"

# Same cuisine options as local index.html
CUISINE_OPTIONS = [
    "North Indian", "Chinese", "South Indian", "Italian", "Cafe", "Bakery",
    "Fast Food", "Biryani", "Desserts", "Continental", "Mughlai", "Thai",
    "Japanese", "Mexican", "Street Food", "Seafood", "Healthy Food", "Beverages",
]


def get_places(db_path: Path) -> list[str]:
    if not db_path.exists():
        return []
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.execute(
            "SELECT DISTINCT city FROM restaurants WHERE TRIM(city) != '' "
            "UNION SELECT DISTINCT locality FROM restaurants WHERE TRIM(locality) != '' "
            "ORDER BY 1"
        )
        out = [row[0] for row in cur.fetchall()]
        conn.close()
        return out
    except Exception:
        return []


def run_recommendations(
    places: list[str],
    min_price: int,
    max_price: int,
    min_rating: float,
    cuisines: list[str],
    max_results: int,
    db_path: Path,
    use_llm: bool = True,
):
    from phase2.preferences import validate_and_normalize_preferences
    from phase3.ranking import filter_and_rank
    from phase3.ranking.engine import RankerConfig
    from phase4.llm import run_phase4_recommendations
    from phase5.display.serializer import serialize_response

    raw = {
        "price_range": {"min": min_price, "max": max_price, "currency": "INR"},
        "min_rating": min_rating,
        "cuisines": [c.strip().lower() for c in cuisines if c.strip()],
        "max_results": max_results,
    }
    if places:
        raw["location"] = {"places": [p.strip() for p in places if p.strip()]}
    request = validate_and_normalize_preferences(raw)
    config = RankerConfig(sqlite_db_path=str(db_path))
    candidates = filter_and_rank(request, config=config)
    response = run_phase4_recommendations(request, candidates, use_llm=use_llm)
    return serialize_response(response)


def badge_class(b: str) -> str:
    lower = (b or "").lower()
    if "highly rated" in lower:
        return "badge-highly-rated"
    if "budget" in lower:
        return "badge-budget"
    if "top match" in lower:
        return "badge-top-match"
    return "badge-default"


def render_card_html(r: dict) -> str:
    """Same structure and classes as local index.html render()."""
    loc_parts = [r.get("locality"), r.get("city")]
    seen = set()
    unique_loc = []
    for p in loc_parts:
        if not p:
            continue
        k = (p or "").strip().lower()
        if k not in seen:
            seen.add(k)
            unique_loc.append(p)
    loc = " · ".join(unique_loc)
    name = html.escape(r.get("name") or "—")
    badges = (r.get("badges") or [])
    badge_html = "".join(
        f'<span class="badge {badge_class(b)}">{html.escape(b)}</span>' for b in badges
    )
    cuisines = (r.get("cuisines") or [])[:5]
    cuisine_html = "".join(
        f'<span class="badge badge-cuisine">{html.escape(c)}</span>' for c in cuisines
    )
    dishes = (r.get("popular_dishes") or [])[:8]
    dish_colors = ["rec-dish-0", "rec-dish-1", "rec-dish-2", "rec-dish-3", "rec-dish-4", "rec-dish-5"]
    dishes_html = ""
    if dishes:
        chips = "".join(
            f'<span class="rec-dish-chip {dish_colors[i % len(dish_colors)]}">{html.escape(d)}</span>'
            for i, d in enumerate(dishes)
        )
        dishes_html = f'<div class="rec-dishes-title">Popular dishes</div><div class="rec-dish-chips">{chips}</div>'
    cost = r.get("average_cost_for_two") or 0
    rating = r.get("aggregate_rating") or ""
    address = (r.get("address") or "").strip()
    left = (
        f'<div class="rec-card-left">'
        f'<div class="rec-name">{name}</div>'
        f'<div class="rec-top">'
        f'<span class="pin">📍</span><span class="loc">{html.escape(loc)}</span>'
        f'<span class="sep"> · </span><span class="price">₹ {cost} for two</span>'
        f'<span class="sep"> · </span><span class="rating">★ {rating}</span>'
        f'</div>'
        f'{"<div class=\"rec-badges\">" + badge_html + "</div>" if badge_html else ""}'
        f'{"<div class=\"rec-badges\">" + cuisine_html + "</div>" if cuisine_html else ""}'
        f'{dishes_html}'
        f'</div>'
    )
    right = (
        '<div class="rec-card-right">'
        + (f'<div class="rec-label">Address</div><div class="rec-address">' + html.escape(address) + '</div>' if address else '')
        + '<a href="#" class="rec-book-btn">Book a table</a>'
        + '</div>'
    )
    return f'<div class="rec-card"><div class="rec-card-inner">{left}{right}</div></div>'


# ---------- Page config ----------
st.set_page_config(
    page_title="Zomato AI · Restaurant Recommendations",
    page_icon="🍴",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ---------- Header (same as local) ----------
st.markdown("""
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
""", unsafe_allow_html=True)

# ---------- Card CSS (same as local) ----------
st.markdown("""
<style>
  .rec-card { background: #fff; border-radius: 14px; padding: 0; margin-bottom: 1rem; border: 1px solid rgba(0,0,0,0.04); box-shadow: 0 1px 3px rgba(0,0,0,0.05), 0 6px 24px -8px rgba(0,0,0,0.08); overflow: hidden; }
  .rec-card-inner { display: grid; grid-template-columns: 1.4fr 1fr; gap: 0; min-height: 0; }
  .rec-card-left { padding: 1.5rem 1.75rem 1.5rem 1.5rem; }
  .rec-card-right { padding: 1.5rem 1.5rem 1.5rem 1.75rem; background: linear-gradient(135deg, #fafafa 0%, #f4f4f5 100%); border-left: 1px solid rgba(0,0,0,0.04); }
  .rec-label { font-size: 0.65rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: #a1a1aa; margin-bottom: 0.35rem; }
  .rec-address { font-size: 0.9rem; color: #3f3f46; line-height: 1.5; margin-bottom: 1rem; }
  .rec-book-btn { display: inline-block; margin-top: 0.75rem; padding: 0.6rem 1.25rem; font-size: 0.9rem; font-weight: 600; color: #fff; background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%); border: none; border-radius: 8px; cursor: pointer; text-decoration: none; box-shadow: 0 2px 8px rgba(220, 38, 38, 0.3); }
  .rec-dishes-title { font-size: 0.65rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: #a1a1aa; margin: 1rem 0 0.5rem 0; }
  .rec-dish-chips { display: flex; flex-wrap: wrap; gap: 0.4rem; }
  .rec-dish-chip { display: inline-block; padding: 0.3rem 0.6rem; border-radius: 999px; font-size: 0.75rem; font-weight: 500; }
  .rec-dish-0 { background: #dbeafe; color: #1d4ed8; } .rec-dish-1 { background: #fce7f3; color: #be185d; } .rec-dish-2 { background: #d1fae5; color: #047857; }
  .rec-dish-3 { background: #fef3c7; color: #b45309; } .rec-dish-4 { background: #ede9fe; color: #6d28d9; } .rec-dish-5 { background: #cffafe; color: #0e7490; }
  .rec-name { font-size: 1.25rem; font-weight: 700; color: #18181b; margin-bottom: 0.5rem; }
  .rec-top { display: flex; flex-wrap: wrap; align-items: center; gap: 0.4rem; font-size: 0.9rem; color: #71717a; margin-bottom: 0.6rem; }
  .rec-top .rating { color: #18181b; font-weight: 600; }
  .rec-badges { margin-bottom: 0.5rem; display: flex; flex-wrap: wrap; gap: 0.4rem; }
  .badge { display: inline-block; padding: 0.3rem 0.65rem; border-radius: 8px; font-size: 0.75rem; font-weight: 600; }
  .badge-highly-rated { background: #10b981; color: white; } .badge-budget { background: #f59e0b; color: white; }
  .badge-top-match { background: #e23744; color: white; } .badge-default { background: #e4e4e7; color: #3f3f46; }
  .badge-cuisine { background: #f4f4f5; color: #52525b; font-size: 0.7rem; font-weight: 500; }
  .rec-card.empty { color: #71717a; text-align: center; padding: 2.5rem; font-weight: 500; }
  label { text-transform: uppercase !important; font-size: 0.7rem !important; color: #71717a !important; letter-spacing: 0.06em !important; }
  .stButton > button { width: 100%; max-width: 300px; margin: 1rem auto 0; padding: 0.95rem 1.75rem; background: linear-gradient(135deg, #e23744 0%, #c42f3a 100%) !important; color: white !important; border: none !important; border-radius: 999px !important; font-weight: 600 !important; }
</style>
""", unsafe_allow_html=True)

# ---------- DB missing: same form area + build button ----------
if not DB_PATH.exists():
    st.warning("Database not found. Build it once (downloads from Hugging Face, ~2–5 min) to get recommendations.")
    if st.button("Build database now"):
        with st.spinner("Downloading data and building database…"):
            try:
                from phase1.ingestion.phase1_ingestion import run_phase1_ingestion
                run_phase1_ingestion(sqlite_path=str(DB_PATH))
                st.success("Database ready. Reload the page to select a location and get recommendations.")
                st.rerun()
            except Exception as e:
                st.exception(e)
    st.stop()

# ---------- Form (same layout and labels as local) ----------
places_list = get_places(DB_PATH)
place_options = places_list or ["(No places in DB)"]

selected_places = st.multiselect(
    "PLACE",
    options=place_options,
    default=[],
    placeholder="Select areas",
)

col1, col2 = st.columns(2)
with col1:
    max_price_raw = st.number_input("MAX PRICE (INR)", min_value=0, value=0, step=500, placeholder="No max")
max_price = 999999 if (max_price_raw == 0) else max_price_raw

with col2:
    min_rating = st.number_input("MIN RATING", min_value=0.0, max_value=5.0, value=4.0, step=0.1, format="%.1f")

selected_cuisines = st.multiselect(
    "CUISINES",
    options=CUISINE_OPTIONS,
    default=[],
    placeholder="Select cuisines",
)

max_results = st.number_input("MAX RESULTS", min_value=1, max_value=50, value=10)

submitted = st.button("Get AI Recommendations")

if submitted:
    if not selected_places and places_list:
        st.error("Please select a location.")
    else:
        with st.spinner("Finding recommendations…"):
            try:
                data = run_recommendations(
                    places=selected_places or (places_list[:1] if places_list else []),
                    min_price=0,
                    max_price=max_price,
                    min_rating=min_rating,
                    cuisines=selected_cuisines,
                    max_results=max_results,
                    db_path=DB_PATH,
                    use_llm=True,
                )
            except Exception as e:
                st.exception(e)
                st.stop()

        recs = (data.get("recommendations") or [])[:]
        recs.sort(key=lambda x: (float(x.get("aggregate_rating") or 0)), reverse=True)

        if not recs:
            st.markdown(
                '<div class="rec-card empty">No recommendations found. Try more areas or relax filters.</div>',
                unsafe_allow_html=True,
            )
        else:
            for r in recs:
                st.markdown(render_card_html(r), unsafe_allow_html=True)
