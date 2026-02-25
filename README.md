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

3. **Run the app**

   **Option A — Streamlit (deploy-friendly)**
   ```bash
   streamlit run streamlit_app.py
   ```
   Open the URL in the browser. Use the sidebar to set location, price, rating, cuisines, then **Get recommendations**.

   **Option B — FastAPI + HTML**
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
- `phase5/` — FastAPI + static HTML UI
- `streamlit_app.py` — Streamlit UI (runs Phase 2–4 in-process)

### Deploy on Streamlit Community Cloud

1. Push the latest code (including `.streamlit/config.toml` and `streamlit_app.py`) to GitHub.
2. At [share.streamlit.io](https://share.streamlit.io), click **New app** → choose repo `deepanjandhwani/first-genAI-project`, branch `main`, main file path **`streamlit_app.py`**.
3. Click **Deploy**. You should see the red **ZOMATO** header and **AI Restaurant Recommendation Platform** form.
4. If you still see the old UI: in the app’s **Manage app** → **Reboot app**, or confirm the correct branch and that the repo is public. Add `GROQ_API_KEY` in **Secrets** if you use the LLM.

See **ARCHITECTURE.md** for full design and deployment notes.
