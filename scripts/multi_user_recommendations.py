"""Multi-user wardrobe ingestion and recommendation script for Google Colab."""

import json
import os
import sys
import httpx

API_BASE = "http://localhost:8000"
MANIFEST = "/content/Auspicious-fire-/tests/dummy/dummy_wardrobes.json"

USER_CONFIGS = [
    {
        "user_id": "user_002",
        "scenario_name": "Work / Office in Cold Weather",
        "context": {
            "occasion": "work_office",
            "weather": "cold",
            "formality": "business_casual",
        },
    },
    {
        "user_id": "user_003",
        "scenario_name": "Party / Social in Warm Weather",
        "context": {
            "occasion": "party_social",
            "weather": "warm",
            "style_mood": "bold_expressive",
        },
    },
    {
        "user_id": "user_004",
        "scenario_name": "Outdoor / Travel in Mild Weather",
        "context": {
            "occasion": "outdoor_travel",
            "weather": "mild",
            "style_mood": "relaxed_comfort",
        },
    },
    {
        "user_id": "user_005",
        "scenario_name": "Formal Event in Mild Weather",
        "context": {
            "occasion": "formal_event",
            "weather": "mild",
            "formality": "semi_formal",
        },
    },
]


def main():
    print("=================================================================")
    print("Multi-User Wardrobe Ingestion and Recommendation Suite")
    print("=================================================================")

    if not os.path.exists(MANIFEST):
        print(f"Error: Manifest not found at {MANIFEST}")
        sys.exit(1)

    with open(MANIFEST, "r", encoding="utf-8") as f:
        data = json.load(f)

    with httpx.Client() as client:
        # Check API health
        r = client.get(f"{API_BASE}/healthz")
        if r.status_code != 200:
            print("API gateway is not healthy.")
            sys.exit(1)
        print("API gateway is healthy.")

        for cfg in USER_CONFIGS:
            u_id = cfg["user_id"]
            name = cfg["scenario_name"]
            ctx = cfg["context"]

            print(f"\n-----------------------------------------------------------------")
            print(f"Processing User: {u_id} ({name})")
            print(f"-----------------------------------------------------------------")

            user_entry = next((u for u in data["users"] if u["user_id"] == u_id), None)
            if not user_entry:
                print(f"User {u_id} not found in manifest, skipping.")
                continue

            items = user_entry["items"]
            print(f"Ingesting {len(items)} items for {u_id}...")

            for idx, item in enumerate(items, 1):
                payload = {"image_url": item["image_url"]}
                resp = client.post(
                    f"{API_BASE}/api/v1/users/{u_id}/wardrobe?sync_tag=true",
                    json=payload,
                    timeout=30.0,
                )
                if resp.status_code != 201:
                    print(f"Item {idx} ingestion failed: {resp.text}")
                else:
                    item_data = resp.json()
                    print(
                        f" [{idx:02d}/{len(items)}] {item_data['item_id']}: "
                        f"slot={item_data['slot']}, category={item_data['category']}, "
                        f"color={item_data['color']}, status={item_data['status']}"
                    )

            # Query recommendations
            print(f"\nQuerying recommendations for {u_id} with context:")
            print(f" {json.dumps(ctx)}")
            rec_resp = client.post(
                f"{API_BASE}/api/v1/users/{u_id}/recommendations?top_k=2",
                json=ctx,
                timeout=15.0,
            )
            if rec_resp.status_code != 200:
                print(f"Recommendation request failed: {rec_resp.text}")
                continue

            result = rec_resp.json()
            outfits = result.get("outfits", [])
            print(f"Received {len(outfits)} recommended outfits:")

            for o_idx, outfit in enumerate(outfits, 1):
                score = outfit.get("total_score")
                score_val = f"{score:.3f}" if score is not None else "N/A"
                items_dict = outfit.get("items", {})
                rationale = outfit.get("rationale", "")
                print(f"  [Outfit {o_idx}] Total Score: {score_val} / 100")
                print(f"   Rationale: {rationale}")
                for slot, g in items_dict.items():
                    print(
                        f"     * {slot.upper()}: {g.get('category')} "
                        f"(color: {g.get('color')}, fabric: {g.get('fabric')})"
                    )

        # Print overall statistics
        print("\n=================================================================")
        print("Final Ingestion Summary")
        print("=================================================================")
        for u in data["users"]:
            u_id = u["user_id"]
            w_resp = client.get(f"{API_BASE}/api/v1/users/{u_id}/wardrobe")
            count = w_resp.json().get("total_items", 0) if w_resp.status_code == 200 else 0
            print(f"User {u_id} ({u['display_name']}): {count} items registered")


if __name__ == "__main__":
    main()
