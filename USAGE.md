# Using the AI Restaurant Recommendation Service locally

## 0. (Optional) Build the React UI

The app has a React UI with a **Place** dropdown (all areas from the DB). To use it:

```bash
cd frontend
npm install
npm run build
cd ..
```

If you skip this, the server still serves a simple HTML form at `/app`.

## 1. Start the server

From the project root, run:

```bash
bash scripts/run_server.sh
```

Or manually:

```bash
# Optional: load restaurant data first (only needed once)
.venv/bin/python -c "from phase1.ingestion.phase1_ingestion import run_phase1_ingestion; run_phase1_ingestion()"

# Start the API
.venv/bin/python -m uvicorn phase5.display.api:create_app --factory --host 0.0.0.0 --port 8000
```

---

## 2. Check that the server is running

- **Browser:** Open **http://localhost:8000**  
  You are redirected to the **web UI** at **http://localhost:8000/app** (form + recommendations).

- **Browser:** Open **http://localhost:8000/docs**  
  Swagger UI loads (interactive API docs).

- **Terminal:**
  ```bash
  curl -s http://localhost:8000/
  ```
  You should get JSON like `{"message":"Restaurant Recommendation API", ...}`.

If you see "Connection refused" or no response, the server is not running — start it with step 1.

---

## 3. Get recommendations

**Option A – Web UI (easiest)**  
1. Open **http://localhost:8000** (or **http://localhost:8000/app**).  
2. Fill in City, price range, cuisines, etc. (all optional).  
3. Click **Get recommendations**.  
4. Results appear as cards with name, rating, price, and “Why recommended”.

**Option B – API docs**  
1. Go to **http://localhost:8000/docs**.  
2. Open **POST /recommendations/query** → **Try it out** → edit body → **Execute**.

**Option C – curl**
```bash
curl -X POST http://localhost:8000/recommendations/query \
  -H "Content-Type: application/json" \
  -d '{"location":{"city":"Bengaluru"},"price_range":{"min":200,"max":1500},"max_results":5}'
```

---

## 4. Stop the server

In the terminal where the server is running, press **Ctrl+C**.

---

## 5. Optional: Groq LLM

For LLM-generated “why recommended” text, set **GROQ_API_KEY** in `.env`.  
If it’s not set, the app still works and uses template explanations.
