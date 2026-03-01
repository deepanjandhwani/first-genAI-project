# Restaurant Recommendation Service

AI-powered restaurant recommendations (Zomato-style): Phase 1 ingestion from Hugging Face → Phase 2–3 filter & rank → Phase 4 LLM (Groq) or fallback.

## Quick start

1. **Install**
   ```bash
   pip install -r requirements.txt
   ```

2. **Ingest data** (once)
   ```bash
   python -m phase1.ingestion.phase1_ingestion
   ```
   Creates `data/processed/restaurants.db`.

3. **Run the app locally** (optional; production is on Vercel)
   ```bash
   uvicorn phase5.display.api:create_app --factory
   ```
   Open http://127.0.0.1:8000 (or the URL shown).

## Optional: LLM (Groq)

For natural-language “why recommended” and re-ranking, set in project root `.env`:

```
GROQ_API_KEY=your_groq_api_key
```

If unset, the app uses template explanations and Phase 3 order.

## Project layout

- `phase1/` — Data ingestion (Hugging Face → JSONL + SQLite)
- `phase2/` — Preference validation and normalization
- `phase3/` — Filter + rank engine (SQLite)
- `phase4/` — LLM orchestrator (Groq) and fallback
- `phase5/` — FastAPI + static HTML UI (local)
- `api/` — Vercel serverless API (places + query)

### Deploy on Vercel

Static UI + Python serverless API. See **DEPLOY_VERCEL.md** for full steps. Summary:

- **UI**: `public/index.html` (same as local Zomato UI). **API**: `api/index.py` (FastAPI app); rewrites map `/recommendations/*` to `/api/*`.
- Run Phase 1 locally, then **commit** `data/processed/restaurants.db` (do not add it to `.gitignore`) so Vercel has the DB.
- In Vercel: set **`GROQ_API_KEY`** in Environment Variables for LLM.
- Deploy: `vercel` from the project root, or connect the repo at [vercel.com](https://vercel.com).

See **ARCHITECTURE.md** for full design and deployment notes.
