#!/usr/bin/env bash
# Start the Restaurant Recommendation API for local use.
# Usage: ./scripts/run_server.sh   or   bash scripts/run_server.sh

cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
  echo "Creating venv and installing dependencies..."
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt -q
fi

if [ ! -f "data/processed/restaurants.db" ]; then
  echo "No restaurants DB found. Running Phase 1 ingestion once (this may take a minute)..."
  .venv/bin/python -c "from phase1.ingestion.phase1_ingestion import run_phase1_ingestion; run_phase1_ingestion()"
  echo ""
fi

echo "Starting server at http://localhost:8000"
echo "  API docs: http://localhost:8000/docs"
echo "  Press Ctrl+C to stop"
echo ""
.venv/bin/python -m uvicorn phase5.display.api:create_app --factory --host 0.0.0.0 --port 8000
