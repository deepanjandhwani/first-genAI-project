import json
import logging
import os
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from datasets import load_dataset

logger = logging.getLogger(__name__)


@dataclass
class IngestionConfig:
    raw_snapshot_path: str = "data/raw/zomato_snapshot.jsonl"
    sqlite_db_path: str = "data/processed/restaurants.db"
    # Hugging Face datasets library
    hf_dataset_name: str = "ManikaSaini/zomato-restaurant-recommendation"
    hf_split: str = "train"
    hf_streaming: bool = False


def iter_all_raw_records(config: IngestionConfig) -> Iterable[Dict[str, Any]]:
    """
    Yield raw records from Hugging Face via datasets.load_dataset.
    Supports non-streaming (default) and streaming mode.
    """
    logger.info(
        "dataset=%s split=%s streaming=%s",
        config.hf_dataset_name,
        config.hf_split,
        config.hf_streaming,
    )
    ds = load_dataset(
        config.hf_dataset_name,
        split=config.hf_split,
        streaming=config.hf_streaming,
        trust_remote_code=True,
    )
    for row in ds:
        # HF datasets yield dicts with column names as keys; support legacy "row" wrapper
        if isinstance(row, dict) and "row" in row:
            yield row["row"]
        else:
            yield row


def _parse_rating(rate_value: Any) -> float:
    """Parse 'rate' from dataset (e.g. '4.1/5') to float."""
    if rate_value is None:
        return 0.0
    s = str(rate_value).strip()
    if not s or s.lower() in ("nan", "null", "-"):
        return 0.0
    try:
        if "/" in s:
            return float(s.split("/")[0].strip())
        return float(s)
    except (TypeError, ValueError):
        return 0.0


def _pick_best_review(reviews_list: Any) -> str:
    """From reviews_list (list of dicts or strings), return one best review text."""
    if not reviews_list:
        return ""
    if isinstance(reviews_list, str):
        try:
            reviews_list = json.loads(reviews_list)
        except (TypeError, json.JSONDecodeError):
            return reviews_list.strip()[:500] if reviews_list.strip() else ""
    if not isinstance(reviews_list, list) or not reviews_list:
        return ""
    best_text = ""
    best_rating = -1.0
    for r in reviews_list:
        if isinstance(r, str) and r.strip():
            if best_rating < 0:
                best_text = r.strip()[:500]
            break
        if isinstance(r, dict):
            text = (r.get("review") or r.get("text") or r.get("Review") or "").strip()
            rating = _parse_rating(r.get("rating") or r.get("Rating"))
            if text and (best_rating < 0 or rating > best_rating):
                best_text = text[:500]
                best_rating = rating
    return best_text


def _parse_dish_liked(dish_liked: Any) -> List[str]:
    """Return list of dish names from dish_liked (string comma-sep or JSON list)."""
    if not dish_liked:
        return []
    if isinstance(dish_liked, list):
        return [str(x).strip() for x in dish_liked if str(x).strip()][:15]
    if isinstance(dish_liked, str):
        try:
            data = json.loads(dish_liked)
            return _parse_dish_liked(data)
        except (TypeError, json.JSONDecodeError):
            return [x.strip() for x in dish_liked.split(",") if x.strip()][:15]
    return []


def _pick_one_phone(raw: Dict[str, Any]) -> str:
    """Pick one phone: mobile preferred, else landline. Returns single number string."""
    import re
    candidates: List[Tuple[bool, str]] = []  # (is_mobile, number)
    for key in ("phone", "Phone", "contact", "Contact", "mobile", "Mobile", "phone_number", "contact_number", "phone_no", "tel", "Phone_No"):
        val = raw.get(key)
        if not val:
            continue
        if isinstance(val, (int, float)):
            val = str(int(val))
        else:
            val = str(val).strip()
        if not val or val.lower() in ("nan", "null", "-", "na"):
            continue
        # Extract digits only
        digits = re.sub(r"\D", "", val)
        if len(digits) >= 10:
            # Indian mobile often 10 digits starting 6-9
            is_mobile = digits.startswith(("6", "7", "8", "9")) and len(digits) == 10
            num = digits[-10:] if len(digits) > 10 else digits
            candidates.append((is_mobile, num))
    if not candidates:
        return ""
    # Prefer mobile, then first
    candidates.sort(key=lambda x: (not x[0], 0))
    return candidates[0][1]


def validate_and_normalize_record(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Minimal validation/normalization into RestaurantRecord-like shape.
    Location is taken only from raw.get("location") for filtering; city from raw.get("city") (listed_in(city) not used).
    Also accepts rate/approx_cost(for two people) and legacy aggregate_rating, average_cost_for_two.
    Returns None if the record should be dropped.
    """
    name = (raw.get("name") or "").strip()
    address = (raw.get("address") or "").strip()
    # Location for filtering: use only raw.get("location"); do not use listed_in(city)
    locality = (raw.get("location") or "").strip()
    city = (raw.get("city") or "").strip()
    cuisines_raw = raw.get("cuisines") or ""

    if not name or not address or not cuisines_raw:
        return None

    if isinstance(cuisines_raw, str):
        cuisine_list = [c.strip().lower() for c in cuisines_raw.split(",") if c.strip()]
    elif isinstance(cuisines_raw, list):
        cuisine_list = [str(c).strip().lower() for c in cuisines_raw if str(c).strip()]
    else:
        cuisine_list = []

    if not cuisine_list:
        return None

    aggregate_rating = _parse_rating(raw.get("rate") or raw.get("aggregate_rating"))
    avg_cost_raw = raw.get("average_cost_for_two") or raw.get("approx_cost(for two people)")
    try:
        avg_cost = int(float(str(avg_cost_raw or "0").replace(",", "")))
    except (TypeError, ValueError):
        avg_cost = 0

    rid = raw.get("restaurant_id") or raw.get("id") or raw.get("url")
    restaurant_id = str(rid) if rid else str(abs(hash((name, address))) % (10**10))

    reviews_list_raw = raw.get("reviews_list") or raw.get("review_list") or raw.get("reviews")
    best_review = _pick_best_review(reviews_list_raw) if reviews_list_raw else ""
    dish_liked_raw = raw.get("dish_liked") or raw.get("dishes")
    dish_list = _parse_dish_liked(dish_liked_raw)
    phone = _pick_one_phone(raw)

    return {
        "restaurant_id": restaurant_id,
        "name": name,
        "address": address,
        "locality": locality or city,
        "city": city or locality,
        "cuisines": cuisine_list,
        "average_cost_for_two": avg_cost,
        "currency": raw.get("currency") or "INR",
        "aggregate_rating": aggregate_rating,
        "rating_text": raw.get("rating_text") or str(raw.get("rate") or ""),
        "votes": int(raw.get("votes") or 0),
        "best_review": best_review,
        "dish_liked": dish_list,
        "phone": phone,
    }


def snapshot_raw_to_file(
    config: IngestionConfig,
    raw_records_collector: Optional[List[Dict[str, Any]]] = None,
) -> int:
    """
    Load raw records via Hugging Face datasets and write them as JSONL to the snapshot path.
    If raw_records_collector is provided, append each raw record to it (enables single pass for streaming).
    Returns number of rows written.
    """
    count = 0
    os.makedirs(os.path.dirname(config.raw_snapshot_path), exist_ok=True)

    with open(config.raw_snapshot_path, "w", encoding="utf-8") as f:
        for raw in iter_all_raw_records(config):
            f.write(json.dumps(raw, ensure_ascii=False) + "\n")
            count += 1
            if raw_records_collector is not None:
                raw_records_collector.append(raw)

    logger.info("total rows processed (raw snapshot): %d", count)
    return count


def _get_sqlite_path(explicit_path: Optional[str] = None, config: Optional[IngestionConfig] = None) -> str:
    if explicit_path:
        return explicit_path
    if config is not None:
        return config.sqlite_db_path
    return "data/processed/restaurants.db"


def load_normalized_records_to_sqlite(
    records: Iterable[Dict[str, Any]],
    sqlite_path: str,
) -> int:
    """
    Stream normalized records into a SQLite database file for serving.
    """
    inserted = 0
    os.makedirs(os.path.dirname(sqlite_path), exist_ok=True)

    with sqlite3.connect(sqlite_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS restaurants (
                restaurant_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                address TEXT NOT NULL,
                locality TEXT NOT NULL,
                city TEXT NOT NULL,
                cuisines TEXT NOT NULL,
                average_cost_for_two INTEGER NOT NULL,
                currency TEXT NOT NULL,
                aggregate_rating REAL NOT NULL,
                rating_text TEXT,
                votes INTEGER NOT NULL,
                best_review TEXT,
                dish_liked TEXT,
                phone TEXT
            )
            """
        )
        # Add new columns to existing tables (no-op if already present)
        for col in ("best_review", "dish_liked", "phone"):
            try:
                cur.execute(f"ALTER TABLE restaurants ADD COLUMN {col} TEXT")
            except sqlite3.OperationalError:
                pass  # column exists

        insert_sql = """
            INSERT INTO restaurants (
                restaurant_id, name, address, locality, city, cuisines,
                average_cost_for_two, currency, aggregate_rating, rating_text, votes,
                best_review, dish_liked, phone
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(restaurant_id) DO UPDATE SET
                name = excluded.name,
                address = excluded.address,
                locality = excluded.locality,
                city = excluded.city,
                cuisines = excluded.cuisines,
                average_cost_for_two = excluded.average_cost_for_two,
                currency = excluded.currency,
                aggregate_rating = excluded.aggregate_rating,
                rating_text = excluded.rating_text,
                votes = excluded.votes,
                best_review = excluded.best_review,
                dish_liked = excluded.dish_liked,
                phone = excluded.phone
        """

        for record in records:
            cur.execute(
                insert_sql,
                (
                    record["restaurant_id"],
                    record["name"],
                    record["address"],
                    record["locality"],
                    record["city"],
                    json.dumps(record["cuisines"], ensure_ascii=False),
                    record["average_cost_for_two"],
                    record["currency"],
                    record["aggregate_rating"],
                    record["rating_text"],
                    record["votes"],
                    record.get("best_review") or "",
                    json.dumps(record.get("dish_liked") or [], ensure_ascii=False),
                    record.get("phone") or "",
                ),
            )
            inserted += 1

    return inserted


def run_phase1_ingestion(
    config: Optional[IngestionConfig] = None,
    sqlite_path: Optional[str] = None,
) -> Tuple[int, int, Optional[int]]:
    """
    Orchestrate Phase 1 ingestion:
    - Load raw records via Hugging Face datasets (one pass)
    - Write raw snapshot and collect raw records for normalization
    - Validate/normalize and load into SQLite

    Returns:
        (raw_count, processed_count, db_inserted_count or None if DB not configured)
    """
    if config is None:
        config = IngestionConfig()

    raw_records: List[Dict[str, Any]] = []
    raw_count = snapshot_raw_to_file(config, raw_records_collector=raw_records)

    processed_records: List[Dict[str, Any]] = []
    for raw in raw_records:
        normalized = validate_and_normalize_record(raw)
        if normalized is not None:
            processed_records.append(normalized)

    processed_count = len(processed_records)
    logger.info("total rows processed (normalized): %d", processed_count)

    db_path = _get_sqlite_path(sqlite_path, config)
    db_inserted_count: Optional[int] = None
    if processed_records:
        db_inserted_count = load_normalized_records_to_sqlite(
            records=processed_records,
            sqlite_path=db_path,
        )

    return raw_count, processed_count, db_inserted_count

