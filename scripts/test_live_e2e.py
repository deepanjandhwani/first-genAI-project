#!/usr/bin/env python3
"""
Live end-to-end test: hits the running app at BASE_URL and verifies the full flow.
Run the server first, then:
  python scripts/test_live_e2e.py
  or
  pytest scripts/test_live_e2e.py -v -s
"""
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Project root on path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")


def request(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    url = f"{BASE_URL.rstrip('/')}{path}"
    data = None
    if method == "POST" and path != "/":
        data = json.dumps(body if body is not None else {}).encode("utf-8")
    req = Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except HTTPError as e:
        return e.code, json.loads(e.read().decode()) if e.fp else {"detail": str(e)}
    except URLError:
        raise


def main() -> int:
    print(f"Live E2E test → {BASE_URL}\n")

    # 1. Root (optional: 404 if server wasn’t restarted after adding root route)
    status, body = request("GET", "/")
    if status == 200 and "docs" in body:
        print("GET /  → 200 OK")
    else:
        print("GET /  →", status, "(continuing; restart server for root route)")

    # 2. POST /recommendations/query (minimal)
    status, body = request("POST", "/recommendations/query", {})
    assert status == 200, body
    assert "request_id" in body
    assert "recommendations" in body
    assert "user_preferences" in body
    assert "metadata" in body
    print("POST /recommendations/query {}  → 200 OK")

    # 3. POST with filters
    payload = {
        "location": {"city": "Bengaluru"},
        "price_range": {"min": 200, "max": 1500},
        "min_rating": 3.5,
        "cuisines": ["north indian", "chinese"],
        "max_results": 5,
    }
    status, body = request("POST", "/recommendations/query", payload)
    assert status == 200, body
    assert body["user_preferences"]["location"]["city"] == "Bengaluru"
    recs = body["recommendations"]
    for r in recs:
        assert "name" in r and "why_recommended" in r
    print(f"POST /recommendations/query (with filters)  → 200 OK  ({len(recs)} recommendations)")

    # 4. Invalid body → 422
    status, body = request("POST", "/recommendations/query", {"max_results": 0})
    assert status == 422, f"Expected 422, got {status}"
    print("POST /recommendations/query (invalid)  → 422 OK")

    print("\nAll live E2E checks passed.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except URLError as e:
        print(f"Cannot reach {BASE_URL}. Is the server running?")
        print("  uvicorn phase5.display.api:create_app --factory --host 0.0.0.0 --port 8000")
        sys.exit(1)


def test_live_e2e_root():
    """Pytest: GET / returns 200 and links."""
    status, body = request("GET", "/")
    assert status == 200
    assert "docs" in body


def test_live_e2e_recommendations_minimal():
    """Pytest: POST /recommendations/query {} returns 200 and full shape."""
    status, body = request("POST", "/recommendations/query", {})
    assert status == 200
    assert "request_id" in body and "recommendations" in body and "metadata" in body


def test_live_e2e_recommendations_with_filters():
    """Pytest: POST with filters returns 200 and valid recommendations."""
    status, body = request(
        "POST",
        "/recommendations/query",
        {"location": {"city": "Bengaluru"}, "price_range": {"min": 200, "max": 1500}, "max_results": 5},
    )
    assert status == 200
    assert "recommendations" in body
    for r in body["recommendations"]:
        assert "name" in r and "why_recommended" in r


def test_live_e2e_invalid_returns_422():
    """Pytest: Invalid body returns 422."""
    status, _ = request("POST", "/recommendations/query", {"max_results": 0})
    assert status == 422
