## AI Restaurant Recommendation Service — Architecture

This document describes the system architecture for the AI-powered Zomato-style restaurant recommendation service, structured as **functional pipeline phases**. Current implementation:
- **Backend**: Python FastAPI service
- **LLM**: Groq (default model `llama-3.3-70b-versatile`), configured via `GROQ_API_KEY` in `.env`; pluggable provider with deterministic fallback when disabled or on failure
- **Processed Storage**: SQLite (`data/processed/restaurants.db`)
- **Raw Storage**: JSONL files (e.g. `data/raw/zomato_snapshot.jsonl`)
- **UI**: Static HTML (Phase 5 `phase5/display/static/index.html`) with Zomato-style styling

---

## High-Level Logical Architecture of the AI Recommendation Service

High-level diagram:

```text
                       +-----------------------------------------+
                       |        RAW Hugging Face Datasets        |
                       |        (Zomato Restaurant Data)         |
                       +------------------------+----------------+
                                                |
                    Hugging Face datasets library (load_dataset)
                                                v
+-------------------------+        +-----------------------------+
|   Data Ingestion Job    |        |     Raw Snapshot Store      |
|  (scheduled / manual)   |------->| (JSONL raw snapshot)       |
| - Fetch & validate      |        +-----------------------------+
| - Clean & transform     |
| - Load processed data   |        +-----------------------------+
+------------+------------+------->| SQLite (Processed Store)   |
             |                     |  - restaurants table        |
             |                     +-----------------------------+
             |
             |                                     (online path)
             |                     +-----------------------------+
             |   UserPreference    |       Web UI (Client)       |
             +-------------------->|  - Zomato-themed UX         |
                                   +--------------+--------------+
                                                  |
                                                  | UserPreferenceRequest JSON
                                                  v
                                   +--------------+--------------+
                                   |     Backend API (FastAPI)   |
                                   |  - Validate & normalize     |
                                   |  - Orchestrate request      |
                                   +--------------+--------------+
                                                  |
                                                  v
                                   +--------------+--------------+
                                   |      Filter + Rank Engine   |
                                   |  - Hard filters (loc, etc.) |
                                   |  - Scores & diversity       |
                                   +--------------+--------------+
                                                  |
                                                  | Candidate set (top K)
                          +-----------------------+------------------------+
                          |             Cache (optional)                   |
                          +-----------------------+------------------------+
                                                  |
                                                  v
                                   +--------------+--------------+
                                   |       LLM Orchestrator      |
                                   |  - Build grounded prompt    |
                                   |  - Call external LLM        |
                                   +--------------+--------------+
                                                  |
                              LLM prompt payload  |  Structured recommendations
                                                  v
                       +-------------------------+---------------------------+
                       |       External LLM Provider (Groq / Llama, etc.)    |
                       +-------------------------+---------------------------+
                                                  |
                                                  | Structured recommendations
                                                  v
                                   +--------------+--------------+
                                   |       LLM Orchestrator      |
                                   |  - Validate & ground output |
                                   +--------------+--------------+
                                                  |
                                                  | RecommendationResponse JSON
                                                  v
                                   +--------------+--------------+
                                   |     Backend API (FastAPI)   |
                                   |  - Serialize response       |
                                   +--------------+--------------+
                                                  |
                                                  | RecommendationResponse JSON
                                                  v
                                   +--------------+--------------+
                                   |       Web UI (Client)       |
                                   |  - Render recommendations   |
                                   +-----------------------------+
```

High-level flow (left to right):

1. **External Data Source**
   - Hugging Face Hub (Zomato dataset)  
     ↓ (loaded via official Python `datasets` library, `load_dataset`)

2. **Ingestion Layer**
   - Data Ingestion Job (scheduled/manual)
     - Loads dataset via `datasets.load_dataset` (non-streaming or streaming)
     - Writes raw JSON to Raw Snapshot Store
     - Validates, cleans, and loads processed records into SQLite

3. **Storage Layer**
   - Raw Snapshot Store (JSONL files, e.g. `data/raw/zomato_snapshot.jsonl`)
   - SQLite (Processed Serving Store: `data/processed/restaurants.db`, table `restaurants`)

4. **Serving & Orchestration Layer**
   - Web UI (Client)  
     ↓ sends `UserPreferenceRequest` JSON  
   - Backend API (FastAPI)
     - Validates and normalizes `UserPreferenceRequest`
     - Invokes Request Orchestrator
   - Request Orchestrator
     - Calls Filter + Rank Engine
     - Calls LLM Orchestrator when candidates are ready

5. **Filter + Rank Engine**
   - Reads processed restaurants from SQLite
   - Applies hard filters: location (city/locality **starts-with** match), cuisine, min rating, price range (min/max)
   - Deduplicates by `restaurant_id` then by canonical key (name, locality, city)
   - Computes soft ranking score (rating, price affinity, popularity, cuisine match)
   - Produces bounded candidate set (top K) with `best_review`, `popular_dishes` (from `dish_liked`), `phone`
   - Optional cache for repeated queries

6. **LLM Recommendation Layer**
   - LLM Orchestrator
     - Builds grounded prompt from `UserPreferenceRequest` + candidate set (candidate IDs, names, cuisines, cost, rating)
     - Calls External LLM Provider (Groq by default; `GROQ_API_KEY` in `.env`)
     - Validates JSON response: only candidate IDs from the list accepted; parses reason, strengths, best_for
     - On failure or when LLM disabled: **fallback** to top-N by Phase 3 score with template “why recommended” and badges
   - External LLM Provider (Groq / Llama; replaceable)
     - Returns structured recommendations (order + reason + strengths + best_for) for candidates only

7. **Response & Observability**
   - Backend API returns `RecommendationResponse` JSON to Web UI
   - Observability service collects logs, metrics, and traces from:
     - Data Ingestion Job
     - Backend API / Request Orchestrator
     - Filter + Rank Engine
     - LLM Orchestrator

---

## 1. Functional Pipeline Phases

The system is organized into 5 functional phases that form an end-to-end pipeline:

1. **PHASE 1 — Data Ingestion (Load Zomato Data)**
2. **PHASE 2 — User Input (Preference Capture)**
3. **PHASE 3 — Integration (Filter + Rank Candidate Set)**
4. **PHASE 4 — Recommendation (LLM Grounded Explanation Layer)**
5. **PHASE 5 — Display (User-Facing Response)**

Each phase has clear responsibilities, inputs/outputs, and data contracts.

### 1.1 PHASE 1 — Data Ingestion (Load Zomato Data)

**Objective**
- Load Zomato restaurant data from Hugging Face using the official **Python `datasets` library** (`load_dataset`).
- Persist a raw JSONL snapshot and a cleaned, serving-optimized schema in **SQLite** (`data/processed/restaurants.db`).

**Main responsibilities**
- **Data Ingestion Job** (scheduled or manual) loads data via:
  - `datasets.load_dataset(dataset_name, split=..., streaming=...)`
  - Default dataset: `ManikaSaini/zomato-restaurant-recommendation`, split `train`, non-streaming.
  - Optional streaming mode for large datasets or memory-constrained runs.
- Configuration: `hf_dataset_name`, `hf_split`, `hf_streaming`, `raw_snapshot_path`, `sqlite_db_path` (default `data/processed/restaurants.db`).
- Store raw records in **Raw Snapshot Store** (JSONL, e.g. `data/raw/zomato_snapshot.jsonl`) in a single pass.
- **Location**: Taken only from `raw.get("location")` for filtering; city from `raw.get("city")`. `listed_in(city)` is not used.
- Validate and normalize records:
  - Required: name, address, cuisines; type checks and null handling.
  - Rating from `rate` or `aggregate_rating`; cost from `average_cost_for_two` or `approx_cost(for two people)`.
  - **best_review**: from `reviews_list` / `review_list` / `reviews` (highest-rated review text, or first).
  - **dish_liked**: from `dish_liked` / `dishes` (list or JSON/comma-separated), normalized to list of dish names.
  - **phone**: one number from `phone`, `Phone`, `contact`, `mobile`, `phone_number`, `contact_number`, `phone_no`, `tel` (mobile 10-digit preferred).
- Transform into canonical record and bulk load into SQLite table `restaurants`:
  - Columns: `restaurant_id`, `name`, `address`, `locality`, `city`, `cuisines` (JSON), `average_cost_for_two`, `currency`, `aggregate_rating`, `rating_text`, `votes`, `best_review`, `dish_liked` (JSON), `phone`.
  - `ALTER TABLE` adds `best_review`, `dish_liked`, `phone` if missing (backward compatibility).

**Key components**
- Data Ingestion Job (`phase1/ingestion/phase1_ingestion.py`)
- Hugging Face `datasets` library (`load_dataset`)
- Raw Snapshot Store (JSONL)
- SQLite schema: table `restaurants` with columns above

**Inputs**
- Ingestion config: `hf_dataset_name`, `hf_split`, `hf_streaming`, raw snapshot path, SQLite DB path

**Outputs**
- Raw snapshot files (immutable JSONL)
- Processed restaurant records in SQLite (`restaurants` table)
- Ingestion run metadata and validation statistics

---

### 1.2 PHASE 2 — User Input (Preference Capture)

**Objective**
- Capture user preferences in the web UI and normalize them into a `UserPreferenceRequest` used by the backend.

**Main responsibilities**
- Web UI presents a form for:
  - **Location/place**: dropdown of places from `GET /recommendations/places` (city/locality from SQLite); user selects one.
  - **Price range**: min (default 0), max (optional; **no default** — blank means no maximum, sent as high cap for backend).
  - **Minimum rating**: stepper with editable numeric input.
  - **Cuisines**: multi-select (optional).
- Frontend sends JSON to `POST /recommendations/query`.
- Backend (Phase 2 validation):
  - Validates shape and types (Pydantic models).
  - Normalizes fields (lowercase cuisines, numeric ranges, location normalization).
  - Produces `UserPreferenceRequest` for Phase 3.

**Key components**
- Static HTML UI (`phase5/display/static/index.html`), FastAPI endpoints

**Inputs**
- Raw user inputs from browser

**Outputs**
- Normalized `UserPreferenceRequest` JSON passed into Phase 3

---

### 1.3 PHASE 3 — Integration (Filter + Rank Candidate Set)

**Objective**
- From the SQLite restaurant store, compute a **bounded candidate set** that matches the user’s preferences using deterministic filtering and ranking.

**Main responsibilities**
- Apply **hard filters** against SQLite (`restaurants` table):
  - **Location**: city/locality **starts-with** match (e.g. "Banashankari" matches "Banashankari 2nd Stage"); places from request location.
  - Cuisine intersection (when user selected cuisines)
  - Minimum rating (`aggregate_rating >= ?`)
  - Price range: `average_cost_for_two` between min and max (max may be very large when user leaves max price blank).
- **Deduplication**: by `restaurant_id` first; then by canonical key (name, locality, city) so one row per distinct place.
- Compute **soft ranking score** (weighted rating, price affinity, popularity, cuisine match); sort by score.
- SELECT includes `best_review`, `dish_liked`, `phone`; on legacy DB without these columns, fallback SELECT omits them and candidates get empty values.
- Build **CandidateRestaurant** with: `best_review`, `popular_dishes` (parsed from `dish_liked`), `phone`, `rating_text`, plus address, cuisines, cost, rating, votes, `explanation_features`.
- Limit to configurable **top-K** (e.g. top 30). Optional cache for repeated queries.

**Key components**
- Filter + Rank Engine (`phase3/ranking/engine.py`), `CandidateRestaurant` model (`phase3/ranking/models.py`)
- SQLite as serving store (`data/processed/restaurants.db`)

**Inputs**
- `UserPreferenceRequest`
- Restaurant rows from SQLite `restaurants` table

**Outputs**
- `CandidateRestaurant[]` (bounded top-K) with scores, explanation features, best_review, popular_dishes, phone

---

### 1.4 PHASE 4 — Recommendation (LLM Grounded Explanation Layer)

**Objective**
- Use an LLM (**Groq** by default, model `llama-3.3-70b-versatile`) to re-order candidates and generate human-friendly explanations, while keeping the LLM **strictly grounded** to the provided candidate list.

**Main responsibilities**
- LLM Orchestrator builds a **user prompt** with:
  - User preferences (location, price range, min_rating, cuisines, max_recommendations)
  - Candidate list (candidate_id, name, locality, city, cuisines, average_cost_for_two, aggregate_rating, price_bucket) — up to 30 candidates
  - Instruction to respond with JSON only; only recommend from the list; output shape: `recommendations[]` with `candidate_id`, `reason`, `strengths`, `best_for`.
- Call external LLM via **Groq** provider (`GROQ_API_KEY` in `.env`); pluggable interface for other providers.
- Parse and validate JSON response: only accept `candidate_id` values that exist in the candidate set; extract reason, strengths, best_for.
- Build **SingleRecommendation** per accepted entry: merge candidate data (name, address, locality, city, cuisines, cost, rating, votes, **best_review**, **rating_text**, **popular_dishes**, **phone**) with LLM-generated reason and highlighted_attributes (strengths, best_for). Deduplicate by canonical (name, locality, city) when merging.
- **Fallback** (LLM disabled, missing key, or parse failure): take top-N by Phase 3 score; use template “why recommended” and badges from explanation_features (e.g. “Matches your cuisine preferences. Within your budget. Highly rated.”).

**Key components**
- LLM Orchestrator (`phase4/llm/orchestrator.py`), SingleRecommendation model (`phase4/llm/models.py`)
- Groq provider (`phase4/llm/providers/groq_provider.py`), grounding and fallback logic

**Inputs**
- `UserPreferenceRequest`
- `CandidateRestaurant[]` (top-K)

**Outputs**
- `RecommendationResponse`: ordered list of `SingleRecommendation` (with best_review, rating_text, popular_dishes, phone, why_recommended, badges, highlighted_attributes) + metadata (llm_used, fallback_used, latency)

---

### 1.5 PHASE 5 — Display (User-Facing Response)

**Objective**
- Present the recommendations in a Zomato-style static HTML UI with “why recommended” and a clear call-to-action.

**Main responsibilities**
- Backend returns `RecommendationResponse` JSON (echoed preferences, ordered recommendations with name, address, locality, city, cuisines, cost, rating, badges, why_recommended, popular_dishes, etc., and metadata).
- **Static HTML UI** (`phase5/display/static/index.html`):
  - **Cards** sorted by **aggregate_rating** (descending) in the frontend.
  - **Left column**: name, location (deduplicated locality · city), price for two, rating, badges, cuisines, **popular dishes** (chips, up to 8, colored).
  - **Right column**: **address**; **“Book a table”** button (static, red gradient; no Phone or Best review sections).
  - “Why recommended” text under each card when present.
  - Form: location dropdown, min price, max price (blank = no max), min rating stepper, cuisines; submit triggers `POST /recommendations/query`.
  - Place options loaded from `GET /recommendations/places` (from SQLite localities/cities).
  - “No results” and error states when applicable.

**Key components**
- FastAPI response serialization (`phase5/display/api.py`)
- Static HTML + CSS + JS results page (Zomato-themed)

**Inputs**
- `RecommendationResponse` JSON

**Outputs**
- Rendered cards with recommendations, address, Book a table button, and explanations

---

## 2. High-Level Component Architecture

At a high level, the system is composed of:

- **Web UI (Client)**
  - Static HTML (Zomato-style) in `phase5/display/static/index.html`.
  - Handles preference capture (Phase 2) and display (Phase 5): location dropdown, price range (max optional), min rating, cuisines; cards sorted by rating with address and “Book a table” button.

- **Backend API (FastAPI)**
  - Request validation and orchestration of Phases 2–5 (`phase5/display/api.py`).
  - Exposes `GET /recommendations/places`, `POST /recommendations/query`.
  - Hosts Filter + Rank Engine (Phase 3), LLM Orchestrator (Phase 4), optional cache.

- **Data Ingestion Job**
  - Phase 1 (`phase1/ingestion/phase1_ingestion.py`): loads Zomato data from Hugging Face via `datasets.load_dataset`, writes JSONL snapshot and SQLite `restaurants` table (with best_review, dish_liked, phone).

- **Storage Layer**
  - Raw: JSONL files (e.g. `data/raw/zomato_snapshot.jsonl`).
  - Processed: SQLite `data/processed/restaurants.db`, table `restaurants`.

- **External Dependencies**
  - Hugging Face Hub (via `datasets` library).
  - Groq API (LLM; `GROQ_API_KEY` in `.env`), pluggable provider with fallback when disabled or on failure.

- **Observability**
  - Logging for ingestion, API, ranking, and LLM calls (e.g. “Phase 4: calling Groq LLM”, “fallback used”).

---

## 4. Data Contracts (Interface-Level)

These JSON shapes describe the main interfaces used between phases. They are conceptual contracts, not full schemas.

### 4.1 `UserPreferenceRequest`

```json
{
  "user_id": "optional-string-or-null",
  "location": {
    "city": "string",
    "locality": "string",
    "latitude": 12.9716,
    "longitude": 77.5946,
    "radius_km": 5.0
  },
  "price_range": {
    "min": 200,
    "max": 1000,
    "currency": "INR"
  },
  "min_rating": 4.0,
  "cuisines": ["north indian", "chinese"],
  "max_results": 10,
  "optional_filters": {
    "vegetarian_only": false,
    "delivery_only": false,
    "open_now": false
  },
  "sort_preference": "best_match",
  "request_context": {
    "locale": "en-IN",
    "device_type": "web"
  }
}
```

### 4.2 `RestaurantRecord` / SQLite `restaurants` (processed canonical record)

```json
{
  "restaurant_id": "string",
  "name": "string",
  "address": "string",
  "locality": "string",
  "city": "string",
  "cuisines": ["north indian", "chinese"],
  "average_cost_for_two": 800,
  "currency": "INR",
  "aggregate_rating": 4.3,
  "rating_text": "Very Good",
  "votes": 1234,
  "best_review": "Single best review text from reviews_list",
  "dish_liked": ["Butter Naan", "Paneer Tikka"],
  "phone": "9876543210"
}
```

### 4.3 `CandidateRestaurant` (for ranking + LLM)

```json
{
  "candidate_id": "string",
  "restaurant_id": "string",
  "name": "string",
  "address": "string",
  "locality": "string",
  "city": "string",
  "cuisines": ["north indian", "chinese"],
  "average_cost_for_two": 800,
  "currency": "INR",
  "aggregate_rating": 4.3,
  "rating_text": "Very Good",
  "votes": 1234,
  "distance_km": 2.1,
  "price_bucket": "medium",
  "best_review": "string",
  "popular_dishes": ["Butter Naan", "Paneer Tikka"],
  "phone": "9876543210",
  "matching_score": 0.87,
  "explanation_features": {
    "matches_cuisine": true,
    "within_budget": true,
    "nearby": true,
    "highly_rated": true
  }
}
```

### 4.4 `LLMRequestPayload` (preferences + candidates)

```json
{
  "user_preferences": {
    "location": {
      "city": "string",
      "locality": "string"
    },
    "price_range": {
      "min": 200,
      "max": 1000,
      "currency": "INR"
    },
    "min_rating": 4.0,
    "cuisines": ["north indian", "chinese"]
  },
  "candidates": [
    {
      "candidate_id": "cand_1",
      "restaurant_id": "rest_123",
      "name": "The Spice House",
      "locality": "Indiranagar",
      "city": "Bengaluru",
      "cuisines": ["north indian"],
      "average_cost_for_two": 700,
      "currency": "INR",
      "aggregate_rating": 4.5,
      "votes": 980,
      "distance_km": 1.4,
      "price_bucket": "medium",
      "tags": ["family-friendly"],
      "matching_score": 0.91
    }
  ],
  "instruction": "You are a restaurant recommendation assistant. Only recommend restaurants from the candidate list. Do not invent any restaurants.",
  "output_schema_hint": {
    "max_recommendations": 10,
    "fields": ["candidate_id", "restaurant_id", "reason", "highlighted_attributes"]
  }
}
```

### 4.5 `RecommendationResponse` (top N + explanation + metadata)

```json
{
  "request_id": "string-uuid",
  "generated_at": "2026-02-24T12:34:56Z",
  "user_preferences": {
    "location": { "city": "string", "locality": "string" },
    "price_range": { "min": 200, "max": 1000, "currency": "INR" },
    "min_rating": 4.0,
    "cuisines": ["north indian", "chinese"]
  },
  "recommendations": [
    {
      "rank": 1,
      "candidate_id": "cand_1",
      "restaurant_id": "rest_123",
      "name": "The Spice House",
      "address": "string",
      "locality": "Indiranagar",
      "city": "Bengaluru",
      "cuisines": ["north indian"],
      "average_cost_for_two": 700,
      "currency": "INR",
      "aggregate_rating": 4.5,
      "rating_text": "Very Good",
      "votes": 980,
      "best_review": "",
      "popular_dishes": ["Butter Naan"],
      "phone": "",
      "top_reviews": [],
      "badges": ["Top Match", "Highly Rated"],
      "why_recommended": "Matches your preference for North Indian food in Indiranagar, highly rated and within your budget.",
      "highlighted_attributes": {
        "strengths": ["taste", "service"],
        "best_for": ["family dinner", "casual outing"]
      }
    }
  ],
  "metadata": {
    "grounded_in_candidates": true,
    "llm_used": "llama-3.3-70b-versatile",
    "llm_latency_ms": 600,
    "fallback_used": false
  }
}
```

---

## 5. Key Architectural Decisions & Non-Goals

- Maintain **separate raw and processed storage** to enable reprocessing, audits, and isolation from external schema changes.
- Always **filter and rank** deterministically before calling the LLM, to:
  - Reduce latency and cost.
  - Enforce strict constraints (budget, distance, rating).
  - Keep the LLM focused on explanation and light re-ranking within a small, relevant set.
- Enforce **LLM grounding** via:
  - Prompt that only references candidates.
  - Schema requiring candidate/restaurant IDs.
  - Post-validation of responses and deterministic fallback.
- Design for **LLM provider replaceability** via a clean client interface and configuration-based selection.
- Core pipeline remains **simple and functional** (SQLite + HTTP); vector DBs are optional enhancements for future semantic retrieval.
- **Max price** in the UI has no default; when left blank, the backend receives a high cap so no maximum price filter is applied.

---

## 6. Running the application

### Streamlit (recommended for deployment)

A single-page Streamlit app runs the full pipeline (Phase 2 → 3 → 4) without a separate API server:

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

- **Location**: project root `streamlit_app.py`.
- **Config**: `.env` in project root for `GROQ_API_KEY` (optional; fallback to template explanations if unset).
- **Data**: expects `data/processed/restaurants.db` (run Phase 1 ingestion first).
- **Deploy**: e.g. Streamlit Community Cloud by connecting the repo and setting run command to `streamlit run streamlit_app.py`.

### FastAPI + static HTML

```bash
uvicorn phase5.display.api:create_app --factory
```

Then open the URL shown (e.g. `http://127.0.0.1:8000`) and use the web UI. The API also exposes `GET /recommendations/places`, `POST /recommendations/query`, and `GET /docs`.

