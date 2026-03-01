# Deploy on Vercel

This project deploys as **static UI + Python serverless API** on Vercel.

## What gets deployed

- **Static UI**: `public/index.html` (Zomato-style form and results). Served at `/`.
- **API**: Single FastAPI app in `api/index.py` (Vercel’s required entrypoint). It serves GET `/api/places` and POST `/api/query`. Rewrites in `vercel.json` map `/recommendations/places` → `/api/places` and `/recommendations/query` → `/api/query` so the frontend works unchanged.

## Before first deploy

1. **Deploy size (100 MB limit)**  
   The **`data/`** folder is in `.vercelignore` so the deployment stays under Vercel's 100 MB limit. The DB is not bundled.

2. **Database (for recommendations)**  
   The API needs `restaurants.db` at runtime. Because `data/` is not deployed (size limit), you must host the file and set **`RESTAURANTS_DB_URL`** in Vercel. See **"Fix: Database not found"** below.

3. **Environment variable (optional)**  
   For LLM explanations, set **`GROQ_API_KEY`** in **Settings → Environment Variables**.

## Deploy steps

1. Install Vercel CLI (optional): `npm i -g vercel`
2. From the project root:
   ```bash
   vercel
   ```
   Or connect the repo at [vercel.com](https://vercel.com) and deploy from the dashboard.

3. Ensure **Root Directory** is the repo root (where `api/`, `public/`, `vercel.json`, and `requirements.txt` live).

4. After deploy, open the project URL. You should see the Zomato UI; selecting a place and clicking **Get AI Recommendations** calls the serverless API.

## Troubleshooting

### Groq API calls not increasing / only template recommendations

The app uses the **Groq** LLM only when **`GROQ_API_KEY`** is available to the serverless function. If it’s missing, the code falls back to template text and **no Groq API calls** are made.

1. **Add the key in Vercel:** Project → **Settings** → **Environment Variables** → add **`GROQ_API_KEY`** with your [Groq API key](https://console.groq.com/keys) value.
2. **Apply to Production (and Preview):** When adding the variable, select **Production** (and **Preview** if you use preview URLs).
3. **Redeploy:** Environment variables are applied at deploy time. After saving the variable, go to **Deployments** → latest → **⋯** → **Redeploy**, or run `vercel --prod`.

Then trigger a recommendation again; Groq usage should increase.

### "Function Runtimes must have a valid version"

- **Do not** add a `functions` block with `runtime` in `vercel.json`. This project uses only `rewrites`; Vercel picks the Python version from `pyproject.toml`.
- In the **Vercel Dashboard** → your project → **Settings** → **Functions**: if you see a "Runtime" or "Function Runtime" override, set it to **Default** or remove the override.
- Ensure `vercel.json` in your repo does **not** contain `"functions": { "api/*.py": { "runtime": "..." } }`. Commit and redeploy.

## Keeping `public/index.html` in sync

The UI is copied from `phase5/display/static/index.html` into `public/index.html`. If you change the static HTML, update the copy:

```bash
cp phase5/display/static/index.html public/index.html
```

Then commit and redeploy.

---

## Fix: Database not found

If you see **"Database not found. Set RESTAURANTS_DB_URL or run Phase 1 locally"** when clicking **Get AI Recommendations**, do the following.

### 1. Create the DB (if you haven’t)

From the project root:

```bash
python -m phase1.ingestion.phase1_ingestion
```

This creates `data/processed/restaurants.db` (~55 MB).

### 2. Upload the DB and get a URL

**Option A — Vercel Blob (recommended)**

1. In the [Vercel Dashboard](https://vercel.com/dashboard), open your project (**first-gen-ai-project**).
2. Go to **Storage** → **Create Database** → choose **Blob** → create a store (e.g. name it `restaurants-db`). Ensure the store is **public** (or use a token for private).
3. In the Blob store, **upload** `data/processed/restaurants.db` (from your machine).  
   To get the URL: click the uploaded file name, or look for **URL** / **Copy URL** / **Public URL** in the file row or the file’s detail panel. If you don’t see it, use **Option B (CLI)** below.

**Option B — Get the URL via CLI (use this if the dashboard doesn’t show a copy-URL button)**

1. **Get your Blob token (one-time):**  
   Vercel Dashboard → your project → **Settings** → **Environment Variables**.  
   Find **BLOB_READ_WRITE_TOKEN**, click **Reveal** / **Show**, then **Copy** the value.

2. **In Terminal** (from the project root, with Node and Vercel CLI installed):
   ```bash
   cd /path/to/first-genAI-project
   vercel link
   ```
   When prompted, select your **first-gen-ai-project** and the correct scope.

3. **Upload and get the URL:**
   ```bash
   BLOB_READ_WRITE_TOKEN="paste_the_token_you_copied_here" vercel blob put data/processed/restaurants.db
   ```
   Or set the token once and run:
   ```bash
   export BLOB_READ_WRITE_TOKEN="paste_the_token_you_copied_here"
   vercel blob put data/processed/restaurants.db
   ```
   The command will print a line like **`url: https://xxxxx.public.blob.vercel-storage.com/restaurants-xxxxx.db`**. That is the value to use for **RESTAURANTS_DB_URL**.

**Option C — Any public URL**

Upload `restaurants.db` to any host that gives a **direct download URL** (e.g. a public S3/GCS URL, or a file host that returns the raw file for a GET request). Use that URL in the next step.

### 3. Set the environment variable in Vercel

1. In the project: **Settings** → **Environment Variables**.
2. Add:
   - **Name:** `RESTAURANTS_DB_URL`
   - **Value:** the URL from step 2 (e.g. the Vercel Blob URL).
   - **Environments:** Production (and Preview if you want).
3. Save.

### 4. Redeploy

Redeploy so the serverless function gets the new variable:

- **Deployments** → open the latest deployment → **⋯** → **Redeploy**, or  
- From the repo root: `vercel --prod`

After redeploy, try **Get AI Recommendations** again; the API will download the DB on first use.
