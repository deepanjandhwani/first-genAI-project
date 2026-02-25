"""
Phase 5 — FastAPI response layer: POST /recommendations/query.
Runs Phase 2 → 3 → 4 and returns serialized RecommendationResponse.
"""

import logging
import os
from pathlib import Path
from typing import Any, Optional

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parents[2] / ".env"  # project root
    load_dotenv(_env_path)
except ImportError:
    _env_path = None

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Log once at import so server startup shows whether LLM key is available
if _env_path is not None:
    logger.info("Env loaded from %s; GROQ_API_KEY=%s", _env_path, "set" if os.environ.get("GROQ_API_KEY") else "NOT SET")
else:
    logger.info("python-dotenv not installed; GROQ_API_KEY=%s", "set" if os.environ.get("GROQ_API_KEY") else "NOT SET")

# Load UI HTML once at import (path relative to this file)
_STATIC_DIR = Path(__file__).resolve().parent / "static"
_APP_HTML: Optional[str] = None


def _get_app_html() -> str:
    global _APP_HTML
    if _APP_HTML is None:
        index_file = _STATIC_DIR / "index.html"
        if index_file.exists():
            _APP_HTML = index_file.read_text(encoding="utf-8")
        else:
            _APP_HTML = (
                "<!DOCTYPE html><html><body style='font-family:sans-serif;padding:2rem'>"
                "<h1>Restaurant Recommendations</h1>"
                "<p>UI file not found. Use <a href='/docs'>/docs</a> for the API.</p></body></html>"
            )
    return _APP_HTML


class RecommendationQueryBody(BaseModel):
    """Request body for /recommendations/query (raw user preferences)."""

    location: Optional[dict[str, Any]] = None  # may include city, locality, or places: list[str]
    price_range: Optional[dict[str, Any]] = None
    min_rating: Optional[float] = None
    cuisines: Optional[list[str]] = None
    max_results: Optional[int] = Field(default=10, ge=1, le=50)
    sort_preference: Optional[str] = None


def get_router(
    sqlite_db_path: Optional[str] = None,
    use_llm: bool = True,
) -> APIRouter:
    """
    Return FastAPI router for recommendation endpoint.
    sqlite_db_path: path to Phase 1 restaurants DB (default data/processed/restaurants.db).
    use_llm: whether to call Groq LLM in Phase 4 (False = template fallback only).
    """
    from phase2.preferences import validate_and_normalize_preferences
    from phase3.ranking import filter_and_rank
    from phase3.ranking.engine import RankerConfig
    from phase4.llm import run_phase4_recommendations
    from phase5.display.serializer import serialize_response

    router = APIRouter(prefix="/recommendations", tags=["recommendations"])
    db_path = sqlite_db_path or str(Path(__file__).resolve().parents[2] / "data" / "processed" / "restaurants.db")
    config = RankerConfig(sqlite_db_path=db_path)

    @router.get("/health")
    def health():
        """Return DB path and row count so you can verify the server is using the right data."""
        import sqlite3
        try:
            conn = sqlite3.connect(db_path)
            n = conn.execute("SELECT COUNT(*) FROM restaurants").fetchone()[0]
            conn.close()
            return {"db_path": db_path, "restaurant_count": n, "status": "ok"}
        except Exception as e:
            return {"db_path": db_path, "restaurant_count": None, "status": "error", "detail": str(e)}

    @router.get("/places")
    def places():
        """Return distinct place names (city + locality) for the UI dropdown, sorted."""
        import sqlite3
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.execute(
                "SELECT DISTINCT city FROM restaurants WHERE TRIM(city) != '' "
                "UNION SELECT DISTINCT locality FROM restaurants WHERE TRIM(locality) != '' "
                "ORDER BY 1"
            )
            places_list = [row[0] for row in cur.fetchall()]
            conn.close()
            return {"places": places_list}
        except Exception as e:
            logger.warning("places endpoint failed: %s", e)
            return {"places": []}

    @router.post("/query")
    def recommendations_query(body: RecommendationQueryBody) -> JSONResponse:
        """
        Accept raw user preferences, run Phase 2 → 3 → 4, return RecommendationResponse JSON.
        """
        raw: dict[str, Any] = {}
        if body.location is not None:
            raw["location"] = body.location
        if body.price_range is not None:
            raw["price_range"] = body.price_range
        if body.min_rating is not None:
            raw["min_rating"] = body.min_rating
        if body.cuisines is not None:
            raw["cuisines"] = body.cuisines
        if body.max_results is not None:
            raw["max_results"] = body.max_results
        if body.sort_preference is not None:
            raw["sort_preference"] = body.sort_preference

        try:
            request = validate_and_normalize_preferences(raw)
        except Exception as e:
            logger.warning("Phase 2 validation failed: %s", e)
            raise HTTPException(status_code=400, detail=str(e)) from e

        candidates = filter_and_rank(request, config=config)
        response = run_phase4_recommendations(request, candidates, use_llm=use_llm)
        return JSONResponse(content=serialize_response(response))

    return router


def create_app(
    sqlite_db_path: Optional[str] = None,
    use_llm: bool = True,
):
    """Create FastAPI app with recommendations router mounted."""
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, RedirectResponse
    from fastapi.staticfiles import StaticFiles

    app = FastAPI(title="Restaurant Recommendation API", version="1.0")
    project_root = Path(__file__).resolve().parents[2]
    frontend_next_out = project_root / "frontend-next" / "out"
    frontend_dist = project_root / "frontend" / "dist"
    ui_dir = frontend_next_out if (frontend_next_out / "index.html").exists() else frontend_dist

    @app.get("/")
    def root():
        """Redirect to the web UI."""
        return RedirectResponse(url="/app/", status_code=302)

    if ui_dir.exists() and (ui_dir / "index.html").exists():
        @app.get("/app")
        def app_redirect():
            return RedirectResponse(url="/app/", status_code=302)
        app.mount("/app/", StaticFiles(directory=str(ui_dir), html=True), name="app")
    else:
        @app.get("/app", response_class=HTMLResponse)
        @app.get("/app/", response_class=HTMLResponse)
        def app_ui():
            """Serve fallback HTML UI if React build not present."""
            return HTMLResponse(content=_get_app_html())

    app.include_router(get_router(sqlite_db_path=sqlite_db_path, use_llm=use_llm))
    return app
