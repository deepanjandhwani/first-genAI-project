# Pipeline connectivity (Phases 1–5)

All phases are connected and tested. Data flow:

```
Phase 1 (Ingestion)          →  data/raw/zomato_snapshot.jsonl
                             →  data/processed/restaurants.db  (SQLite, table: restaurants)

Phase 2 (Preferences)        ←  raw JSON (e.g. from API body)
                             →  UserPreferenceRequest

Phase 3 (Filter + Rank)     ←  UserPreferenceRequest + restaurants.db
                             →  list[CandidateRestaurant]

Phase 4 (LLM)                ←  UserPreferenceRequest + list[CandidateRestaurant]
                             →  RecommendationResponse

Phase 5 (Display)            ←  RecommendationResponse
                             →  JSON (and FastAPI POST /recommendations/query runs 2→3→4→5)
```

**Contracts verified**

- Phase 1 writes the schema read by Phase 3 (`restaurants`: restaurant_id, name, address, locality, city, cuisines, average_cost_for_two, currency, aggregate_rating, rating_text, votes).
- Phase 2 output (`UserPreferenceRequest`) is the input to Phase 3 and Phase 4.
- Phase 3 output (`CandidateRestaurant[]`) is the input to Phase 4.
- Phase 4 output (`RecommendationResponse`) is the input to Phase 5 serializer and matches the API response shape.

**Tests**

- **36 passed, 2 skipped** (Phase 1 live Hugging Face, Phase 4 live Groq; both optional).
- **E2E:** `phase5/tests/test_e2e_pipeline.py` runs Phase 2→3→4→5 in code and via the API with a fixture DB and asserts end-to-end connectivity.

**Run full suite**

```bash
pytest phase1/tests/ phase2/tests/ phase3/tests/ phase4/tests/ phase5/tests/ -v
```

**Run API (after Phase 1 has populated the DB)**

```bash
uvicorn phase5.display.api:create_app --factory
# POST http://localhost:8000/recommendations/query with JSON body
```
