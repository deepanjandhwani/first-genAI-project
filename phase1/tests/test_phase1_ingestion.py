import os
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from phase1.ingestion.phase1_ingestion import (  # noqa: E402
    IngestionConfig,
    snapshot_raw_to_file,
    validate_and_normalize_record,
)


@pytest.mark.skipif(
    not os.environ.get("RUN_LIVE_HF_TEST"),
    reason="Set RUN_LIVE_HF_TEST=1 to run (requires network and datasets)",
)
def test_snapshot_raw_to_file_writes_some_rows(tmp_path):
    """
    Optional smoke test: load from Hugging Face via datasets library and write snapshot.
    Run with: RUN_LIVE_HF_TEST=1 pytest phase1/tests/test_phase1_ingestion.py -v -k snapshot
    """
    snapshot_path = tmp_path / "zomato_raw.jsonl"
    config = IngestionConfig(raw_snapshot_path=str(snapshot_path))

    written = snapshot_raw_to_file(config)

    assert written > 0
    assert snapshot_path.exists()
    with open(snapshot_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) == written


def test_validate_and_normalize_record_happy_path():
    raw = {
        "restaurant_id": "123",
        "name": "Test Restaurant",
        "address": "123 Main St",
        "locality": "Indiranagar",
        "city": "Bengaluru",
        "cuisines": "North Indian, Chinese",
        "average_cost_for_two": "800",
        "currency": "INR",
        "aggregate_rating": "4.5",
        "rating_text": "Very Good",
        "votes": "100",
    }

    normalized = validate_and_normalize_record(raw)

    assert normalized is not None
    assert normalized["restaurant_id"] == "123"
    assert normalized["name"] == "Test Restaurant"
    assert normalized["cuisines"] == ["north indian", "chinese"]
    assert normalized["average_cost_for_two"] == 800
    assert normalized["aggregate_rating"] == 4.5


def test_validate_and_normalize_record_drops_invalid():
    raw_missing_name = {
        "restaurant_id": "123",
        "name": "",
        "address": "123 Main St",
        "locality": "Indiranagar",
        "city": "Bengaluru",
        "cuisines": "North Indian",
    }
    assert validate_and_normalize_record(raw_missing_name) is None

    raw_no_cuisines = {
        "restaurant_id": "123",
        "name": "Test Restaurant",
        "address": "123 Main St",
        "locality": "Indiranagar",
        "city": "Bengaluru",
        "cuisines": "",
    }
    assert validate_and_normalize_record(raw_no_cuisines) is None

