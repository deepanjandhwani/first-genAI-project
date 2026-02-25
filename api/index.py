"""
Vercel FastAPI entrypoint. Serves /api/places and /api/query so the framework detector finds an app.
Rewrites send /recommendations/places -> /api/places and /recommendations/query -> /api/query.
"""

import sqlite3
import sys
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "processed" / "restaurants.db"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="Recommendations API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def get_places_list() -> list[str]:
    if not DB_PATH.exists():
        return []
    try:
        conn = sqlite3.connect(str(DB_PATH))
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


class QueryBody(BaseModel):
    location: Optional[dict[str, Any]] = None
    price_range: Optional[dict[str, Any]] = None
    min_rating: Optional[float] = None
    cuisines: Optional[list[str]] = None
    max_results: Optional[int] = Field(default=10, ge=1, le=50)
    sort_preference: Optional[str] = None


def run_pipeline(body: dict) -> dict:
    from phase2.preferences import validate_and_normalize_preferences
    from phase3.ranking import filter_and_rank
    from phase3.ranking.engine import RankerConfig
    from phase4.llm import run_phase4_recommendations
    from phase5.display.serializer import serialize_response

    raw = {}
    if body.get("location") is not None:
        raw["location"] = body["location"]
    if body.get("price_range") is not None:
        raw["price_range"] = body["price_range"]
    if body.get("min_rating") is not None:
        raw["min_rating"] = body["min_rating"]
    if body.get("cuisines") is not None:
        raw["cuisines"] = body["cuisines"]
    if body.get("max_results") is not None:
        raw["max_results"] = body["max_results"]
    if body.get("sort_preference") is not None:
        raw["sort_preference"] = body["sort_preference"]

    request = validate_and_normalize_preferences(raw)
    config = RankerConfig(sqlite_db_path=str(DB_PATH))
    candidates = filter_and_rank(request, config=config)
    response = run_phase4_recommendations(request, candidates, use_llm=True)
    return serialize_response(response)


def _places():
    return {"places": get_places_list()}


def _query(body: QueryBody):
    if not DB_PATH.exists():
        raise HTTPException(status_code=503, detail="Database not found. Run Phase 1 ingestion.")
    raw = body.model_dump(exclude_none=True)
    try:
        return run_pipeline(raw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# Expose under all path variants (Vercel may strip /api or not)
@app.get("/api/places")
@app.get("/recommendations/places")
@app.get("/places")
def places():
    return _places()


@app.post("/api/query")
@app.post("/recommendations/query")
@app.post("/query")
def query(body: QueryBody):
    return _query(body)


