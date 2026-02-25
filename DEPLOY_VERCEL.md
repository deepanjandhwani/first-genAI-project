# Deploy on Vercel

This project deploys as **static UI + Python serverless API** on Vercel.

## What gets deployed

- **Static UI**: `public/index.html` (Zomato-style form and results). Served at `/`.
- **API**: Single FastAPI app in `api/index.py` (Vercel’s required entrypoint). It serves GET `/api/places` and POST `/api/query`. Rewrites in `vercel.json` map `/recommendations/places` → `/api/places` and `/recommendations/query` → `/api/query` so the frontend works unchanged.

## Before first deploy

1. **Database**  
   The API reads from `data/processed/restaurants.db`. You must either:
   - Run Phase 1 locally and **commit** the DB (ensure `data/processed/restaurants.db` is **not** in `.gitignore`), or  
   - Add the DB to the repo another way (e.g. build step that runs Phase 1 — slow and may hit Hugging Face limits).

2. **Environment variable (optional)**  
   For LLM “why recommended” and re-ranking, set **`GROQ_API_KEY`** in the Vercel project: **Project → Settings → Environment Variables**.

## Deploy steps

1. Install Vercel CLI (optional): `npm i -g vercel`
2. From the project root:
   ```bash
   vercel
   ```
   Or connect the repo at [vercel.com](https://vercel.com) and deploy from the dashboard.

3. Ensure **Root Directory** is the repo root (where `api/`, `public/`, `vercel.json`, `requirements.txt`, and `data/` live).

4. After deploy, open the project URL. You should see the Zomato UI; selecting a place and clicking **Get AI Recommendations** calls the serverless API.

## Keeping `public/index.html` in sync

The UI is copied from `phase5/display/static/index.html` into `public/index.html`. If you change the static HTML, update the copy:

```bash
cp phase5/display/static/index.html public/index.html
```

Then commit and redeploy.
