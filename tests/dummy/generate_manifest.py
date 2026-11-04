import json
import os
from urllib.parse import urlencode

BASE_IMAGE_URL = "https://raw.githubusercontent.com/alexeygrigorev/clothing-dataset-small/master"

CATEGORIES_BREAKDOWN = [
    ("top", 6, [
        {"cat": "t-shirt", "neckline": "crew neck", "sleeve": "short sleeve", "fab": "cotton", "pat": "solid", "fit": "regular fit"},
        {"cat": "shirt", "neckline": "collar", "sleeve": "long sleeve", "fab": "cotton", "pat": "solid", "fit": "slim fit"},
        {"cat": "blouse", "neckline": "v-neck", "sleeve": "long sleeve", "fab": "silk", "pat": "floral", "fit": "regular fit"},
        {"cat": "sweater", "neckline": "turtleneck", "sleeve": "long sleeve", "fab": "wool", "pat": "solid", "fit": "regular fit"},
        {"cat": "hoodie", "neckline": "hooded", "sleeve": "long sleeve", "fab": "cotton", "pat": "solid", "fit": "oversized"},
        {"cat": "top", "neckline": "scoop neck", "sleeve": "sleeveless", "fab": "linen", "pat": "solid", "fit": "regular fit"},
    ]),
    ("bottom", 5, [
        {"cat": "pants", "fab": "cotton", "pat": "solid", "fit": "regular fit"},
        {"cat": "jeans", "fab": "denim", "pat": "solid", "fit": "slim fit"},
        {"cat": "shorts", "fab": "cotton", "pat": "solid", "fit": "regular fit"},
        {"cat": "skirt", "fab": "linen", "pat": "floral", "fit": "regular fit"},
        {"cat": "pants", "fab": "wool", "pat": "plaid", "fit": "regular fit"},
    ]),
    ("one_piece", 2, [
        {"cat": "dress", "neckline": "v-neck", "sleeve": "sleeveless", "fab": "silk", "pat": "solid", "fit": "slim fit"},
        {"cat": "dress", "neckline": "crew neck", "sleeve": "short sleeve", "fab": "cotton", "pat": "floral", "fit": "regular fit"},
    ]),
    ("outerwear", 2, [
        {"cat": "blazer", "neckline": "collar", "sleeve": "long sleeve", "fab": "wool", "pat": "solid", "fit": "regular fit"},
        {"cat": "jacket", "neckline": "collar", "sleeve": "long sleeve", "fab": "denim", "pat": "solid", "fit": "regular fit"},
    ]),
    ("footwear", 3, [
        {"cat": "sneakers", "fab": "cotton", "pat": "solid", "color": "white"},
        {"cat": "shoes", "fab": "leather", "pat": "solid", "color": "black"},
        {"cat": "boots", "fab": "leather", "pat": "solid", "color": "brown"},
    ]),
    ("accessory", 2, [
        {"cat": "hat", "fab": "cotton", "pat": "solid", "color": "beige"},
        {"cat": "hat", "fab": "wool", "pat": "solid", "color": "black"},
    ]),
]

COLOR_PALETTE = [
    "black", "white", "grey", "navy", "blue", "red", "green", "beige", "brown", "pink"
]


def load_real_image_paths() -> dict:
    """Load or fetch real clothing image paths from alexeygrigorev/clothing-dataset-small."""
    paths_file = os.path.join(os.path.dirname(__file__), "real_image_paths.json")
    if os.path.exists(paths_file):
        with open(paths_file, "r", encoding="utf-8") as f:
            return json.load(f)

    # Fallback to GitHub tree API
    import httpx
    api_url = "https://api.github.com/repos/alexeygrigorev/clothing-dataset-small/git/trees/master?recursive=1"
    resp = httpx.get(api_url, headers={"User-Agent": "Python"}, timeout=15.0)
    tree = resp.json().get("tree", [])

    by_cat = {}
    for item in tree:
        p = item["path"]
        if p.endswith(".jpg"):
            parts = p.split("/")
            if len(parts) >= 2:
                by_cat.setdefault(parts[1], []).append(p)

    return {
        "top": by_cat.get("t-shirt", [])[:15] + by_cat.get("shirt", [])[:10] + by_cat.get("longsleeve", [])[:5],
        "bottom": by_cat.get("pants", [])[:12] + by_cat.get("shorts", [])[:8] + by_cat.get("skirt", [])[:5],
        "one_piece": by_cat.get("dress", [])[:10],
        "outerwear": by_cat.get("outwear", [])[:10],
        "footwear": by_cat.get("shoes", [])[:15],
        "accessory": by_cat.get("hat", [])[:10],
    }


def generate_dummy_manifest(output_path: str = "tests/dummy/dummy_wardrobes.json") -> dict:
    """Generate 5 dummy users with 20 real clothing garments each (100 items total)."""
    real_paths = load_real_image_paths()
    slot_cursors = {slot: 0 for slot in real_paths}

    users = []

    for u_idx in range(1, 6):
        user_id = f"user_{u_idx:03d}"
        display_name = f"Fashion User {u_idx:03d}"
        default_city = "Paris" if u_idx % 2 == 0 else "New York"
        default_style = "clean_minimalist" if u_idx % 3 == 0 else "smart_casual"

        user_items = []
        item_counter = 1

        for slot_name, count, templates in CATEGORIES_BREAKDOWN:
            for i in range(count):
                tmpl = templates[i % len(templates)]
                item_id = f"item-{user_id}-{slot_name}-{item_counter:03d}"
                color = tmpl.get("color") or COLOR_PALETTE[(u_idx + i) % len(COLOR_PALETTE)]
                category = tmpl["cat"]
                fabric = tmpl.get("fab", "cotton")
                pattern = tmpl.get("pat", "solid")
                neckline = tmpl.get("neckline")
                sleeve = tmpl.get("sleeve")
                fit = tmpl.get("fit", "regular fit")

                # Get real image path for slot
                slot_paths = real_paths.get(slot_name, [])
                cursor = slot_cursors[slot_name] % len(slot_paths)
                slot_cursors[slot_name] += 1
                rel_path = slot_paths[cursor]

                query_params = {
                    "user_id": user_id,
                    "item_id": item_id,
                    "slot": slot_name,
                    "category": category,
                    "color": color,
                    "fabric": fabric,
                    "pattern": pattern,
                    "fit": fit,
                }
                if neckline:
                    query_params["neckline"] = neckline
                if sleeve:
                    query_params["sleeve"] = sleeve

                image_url = f"{BASE_IMAGE_URL}/{rel_path}?{urlencode(query_params)}"

                hints = {
                    "slot": slot_name,
                    "category": category,
                    "color": color,
                    "fabric": fabric,
                    "pattern": pattern,
                    "fit": fit,
                }
                if neckline:
                    hints["neckline"] = neckline
                if sleeve:
                    hints["sleeve"] = sleeve

                user_items.append({
                    "item_id": item_id,
                    "user_id": user_id,
                    "image_url": image_url,
                    "hints": hints,
                })
                item_counter += 1

        assert len(user_items) == 20, f"Expected 20 items for {user_id}, got {len(user_items)}"
        users.append({
            "user_id": user_id,
            "display_name": display_name,
            "default_city": default_city,
            "default_style": default_style,
            "items_count": len(user_items),
            "items": user_items,
        })

    manifest = {
        "version": "2.0",
        "description": "Dummy wardrobe dataset containing 5 users with 20 real clothing garments each (100 items total)",
        "total_users": len(users),
        "total_items": sum(len(u["items"]) for u in users),
        "users": users,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest


if __name__ == "__main__":
    m = generate_dummy_manifest()
    print(f"Generated manifest with {m['total_users']} users and {m['total_items']} items.")
