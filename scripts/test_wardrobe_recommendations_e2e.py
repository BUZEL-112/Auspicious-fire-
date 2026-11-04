"""End-to-End Wardrobe Ingestion and Outfit Recommendation Verification Script.

Tests:
1. API Health Check (/healthz)
2. Questionnaire Check (/api/v1/context/questions)
3. Dummy Wardrobe Ingestion (POST /api/v1/users/{user_id}/wardrobe)
4. User Wardrobe Retrieval (GET /api/v1/users/{user_id}/wardrobe)
5. Outfit Recommendations across 4 distinct context scenarios
6. Background Services Health and Log Inspection
"""

import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List
import httpx

API_BASE_URL = "http://localhost:8000"
USER_ID = "user_001"
MANIFEST_PATH = "tests/dummy/dummy_wardrobes.json"


def wait_for_api(client: httpx.Client, max_retries: int = 30) -> None:
    """Wait for API gateway readiness."""
    print("Checking API service at http://localhost:8000/healthz...")
    for _ in range(max_retries):
        try:
            resp = client.get(f"{API_BASE_URL}/healthz", timeout=3.0)
            if resp.status_code == 200:
                print(f"API service is healthy: {resp.json()}")
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("Timed out waiting for API service.")


def test_questionnaire_endpoint(client: httpx.Client) -> None:
    """Verify context questions endpoint."""
    print("\n--- [Step 1] Verifying Context Questionnaire ---")
    resp = client.get(f"{API_BASE_URL}/api/v1/context/questions", timeout=5.0)
    assert resp.status_code == 200, f"Failed questionnaire: {resp.text}"
    data = resp.json()
    questions = data.get("questions", [])
    print(f"Received {len(questions)} context questions.")
    assert len(questions) == 5, f"Expected 5 questions, got {len(questions)}"
    for q in questions:
        prompt_text = q.get("prompt") or q.get("title") or q.get("text")
        print(f" - Question [{q.get('id')}]: {prompt_text} ({len(q.get('options', []))} options)")


def ingest_dummy_wardrobe(client: httpx.Client) -> List[Dict[str, Any]]:
    """Ingest dummy wardrobe items for user_001 via FastAPI."""
    print(f"\n--- [Step 2] Ingesting Dummy Wardrobe for {USER_ID} ---")
    if not os.path.exists(MANIFEST_PATH):
        raise FileNotFoundError(f"Manifest not found: {MANIFEST_PATH}")

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    user_data = next((u for u in data.get("users", []) if u.get("user_id") == USER_ID), None)
    if not user_data:
        raise ValueError(f"User {USER_ID} not found in manifest")

    items = user_data.get("items", [])
    print(f"Total garments to ingest: {len(items)}")

    ingested_items = []
    for idx, item in enumerate(items, 1):
        image_url = item.get("image_url")
        hints = item.get("hints", {})
        payload = {"image_url": image_url}

        resp = client.post(
            f"{API_BASE_URL}/api/v1/users/{USER_ID}/wardrobe?sync_tag=true",
            json=payload,
            timeout=30.0,
        )
        assert resp.status_code == 201, f"Failed to ingest item {idx}: {resp.text}"
        item_resp = resp.json()
        ingested_items.append(item_resp)
        print(
            f" [{idx}/{len(items)}] Ingested {item_resp.get('item_id')}: "
            f"slot={item_resp.get('slot')}, category={item_resp.get('category')}, "
            f"color={item_resp.get('color')}, status={item_resp.get('status')}"
        )

    # Verify wardrobe list endpoint
    list_resp = client.get(f"{API_BASE_URL}/api/v1/users/{USER_ID}/wardrobe", timeout=10.0)
    assert list_resp.status_code == 200, f"Failed to list wardrobe: {list_resp.text}"
    wardrobe_data = list_resp.json()
    print(f"Verified user wardrobe contains {wardrobe_data.get('total_items')} items in database.")
    assert wardrobe_data.get("total_items") >= len(items)
    return ingested_items


def test_recommendation_scenarios(client: httpx.Client) -> None:
    """Execute four distinct recommendation scenarios for the user."""
    print(f"\n--- [Step 3] Executing Recommendation Scenarios for {USER_ID} ---")

    scenarios = [
        {
            "name": "Scenario A: Casual Daily (Hot Summer)",
            "context": {
                "occasion": "casual_daily",
                "weather": "hot",
                "style_mood": "clean_minimalist",
            },
        },
        {
            "name": "Scenario B: Work / Office (Cold Winter)",
            "context": {
                "occasion": "work_office",
                "weather": "cold",
                "formality": "business_casual",
            },
        },
        {
            "name": "Scenario C: Date Night (Mild Evening)",
            "context": {
                "occasion": "date_night",
                "weather": "mild",
                "formality": "dressy",
            },
        },
        {
            "name": "Scenario D: Streetwear Daily (Cool Weather)",
            "context": {
                "occasion": "casual_daily",
                "weather": "cool",
                "style_mood": "edgy_streetwear",
            },
        },
    ]

    for scenario in scenarios:
        name = scenario["name"]
        ctx = scenario["context"]
        print(f"\n>> {name}")
        print(f"Context Request: {json.dumps(ctx)}")

        resp = client.post(
            f"{API_BASE_URL}/api/v1/users/{USER_ID}/recommendations?top_k=3",
            json=ctx,
            timeout=15.0,
        )
        assert resp.status_code == 200, f"Recommendation failed for {name}: {resp.text}"
        result = resp.json()
        outfits = result.get("outfits", [])
        print(f"Received {len(outfits)} recommended outfits:")

        for o_idx, outfit in enumerate(outfits, 1):
            score = outfit.get("total_score")
            score_val = f"{score:.3f}" if score is not None else "N/A"
            items = outfit.get("items", {})
            rationale = outfit.get("rationale", "")
            print(f"  [Outfit {o_idx}] Total Score: {score_val}")
            print(f"   Rationale: {rationale}")
            for slot, g in items.items():
                print(
                    f"     * {slot.upper()}: {g.get('category')} "
                    f"(color: {g.get('color')}, fabric: {g.get('fabric')})"
                )


def inspect_background_services() -> None:
    """Inspect all background services and their health."""
    print("\n--- [Step 4] Inspecting Background Services ---")
    status_script = "scripts/status_services.sh"
    if os.path.exists(status_script):
        subprocess.run(["bash", status_script], check=False)
    else:
        print(f"Script {status_script} not found.")


def main() -> None:
    """Run full Phase 2 end-to-end verification."""
    print("=================================================================")
    print("Phase 2 Wardrobe Ingestion and Recommendation Test Suite")
    print("=================================================================")

    with httpx.Client() as client:
        try:
            wait_for_api(client)
            test_questionnaire_endpoint(client)
            ingest_dummy_wardrobe(client)
            test_recommendation_scenarios(client)
            inspect_background_services()
            print("\n=================================================================")
            print("ALL WARDROBE AND RECOMMENDATION TESTS PASSED SUCCESSFULLY!")
            print("=================================================================")
        except Exception as e:
            print(f"\nTEST EXECUTION FAILED: {e}", file=sys.stderr)
            inspect_background_services()
            sys.exit(1)


if __name__ == "__main__":
    main()
