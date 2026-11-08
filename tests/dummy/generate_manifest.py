"""Generate dummy wardrobe manifest for tests and visual evaluations.

This module builds a realistic fashion dataset with five distinct user personas.
Each item connects to a unique real clothing image from the remote repository.
"""

import json
import os
from typing import Any, Dict, List
from urllib.parse import urlencode

BASE_IMAGE_URL = "https://raw.githubusercontent.com/alexeygrigorev/clothing-dataset-small/master"

USER_PERSONAS: List[Dict[str, Any]] = [
    {
        "user_id": "user_001",
        "display_name": "Fashion User 001",
        "default_city": "Copenhagen",
        "default_style": "clean_minimalist",
        "items": [
            # 6 tops
            {"slot": "top", "cat": "t-shirt", "color": "white", "fab": "cotton", "pat": "solid", "fit": "regular fit", "neckline": "crew neck", "sleeve": "short sleeve"},
            {"slot": "top", "cat": "shirt", "color": "white", "fab": "cotton", "pat": "solid", "fit": "regular fit", "neckline": "collar", "sleeve": "long sleeve"},
            {"slot": "top", "cat": "sweater", "color": "grey", "fab": "wool", "pat": "solid", "fit": "regular fit", "neckline": "crew neck", "sleeve": "long sleeve"},
            {"slot": "top", "cat": "top", "color": "black", "fab": "linen", "pat": "solid", "fit": "regular fit", "neckline": "crew neck", "sleeve": "short sleeve"},
            {"slot": "top", "cat": "shirt", "color": "navy", "fab": "cotton", "pat": "solid", "fit": "slim fit", "neckline": "collar", "sleeve": "long sleeve"},
            {"slot": "top", "cat": "blouse", "color": "beige", "fab": "silk", "pat": "solid", "fit": "regular fit", "neckline": "v-neck", "sleeve": "long sleeve"},
            # 5 bottoms
            {"slot": "bottom", "cat": "pants", "color": "black", "fab": "wool", "pat": "solid", "fit": "regular fit"},
            {"slot": "bottom", "cat": "pants", "color": "grey", "fab": "cotton", "pat": "solid", "fit": "regular fit"},
            {"slot": "bottom", "cat": "jeans", "color": "black", "fab": "denim", "pat": "solid", "fit": "slim fit"},
            {"slot": "bottom", "cat": "skirt", "color": "black", "fab": "linen", "pat": "solid", "fit": "regular fit"},
            {"slot": "bottom", "cat": "shorts", "color": "beige", "fab": "cotton", "pat": "solid", "fit": "regular fit"},
            # 2 one_piece
            {"slot": "one_piece", "cat": "dress", "color": "black", "fab": "silk", "pat": "solid", "fit": "slim fit", "neckline": "v-neck", "sleeve": "sleeveless"},
            {"slot": "one_piece", "cat": "dress", "color": "navy", "fab": "cotton", "pat": "solid", "fit": "regular fit", "neckline": "crew neck", "sleeve": "short sleeve"},
            # 2 outerwear
            {"slot": "outerwear", "cat": "blazer", "color": "black", "fab": "wool", "pat": "solid", "fit": "regular fit", "neckline": "collar", "sleeve": "long sleeve"},
            {"slot": "outerwear", "cat": "jacket", "color": "grey", "fab": "cotton", "pat": "solid", "fit": "regular fit", "neckline": "collar", "sleeve": "long sleeve"},
            # 3 footwear
            {"slot": "footwear", "cat": "sneakers", "color": "white", "fab": "leather", "pat": "solid"},
            {"slot": "footwear", "cat": "shoes", "color": "black", "fab": "leather", "pat": "solid"},
            {"slot": "footwear", "cat": "boots", "color": "black", "fab": "leather", "pat": "solid"},
            # 2 accessory
            {"slot": "accessory", "cat": "hat", "color": "black", "fab": "wool", "pat": "solid"},
            {"slot": "accessory", "cat": "hat", "color": "grey", "fab": "cotton", "pat": "solid"},
        ],
    },
    {
        "user_id": "user_002",
        "display_name": "Fashion User 002",
        "default_city": "London",
        "default_style": "smart_casual",
        "items": [
            # 6 tops
            {"slot": "top", "cat": "t-shirt", "color": "white", "fab": "cotton", "pat": "solid", "fit": "regular fit", "neckline": "crew neck", "sleeve": "short sleeve"},
            {"slot": "top", "cat": "shirt", "color": "blue", "fab": "cotton", "pat": "solid", "fit": "slim fit", "neckline": "collar", "sleeve": "long sleeve"},
            {"slot": "top", "cat": "blouse", "color": "navy", "fab": "silk", "pat": "solid", "fit": "regular fit", "neckline": "v-neck", "sleeve": "long sleeve"},
            {"slot": "top", "cat": "sweater", "color": "grey", "fab": "wool", "pat": "solid", "fit": "regular fit", "neckline": "crew neck", "sleeve": "long sleeve"},
            {"slot": "top", "cat": "hoodie", "color": "black", "fab": "cotton", "pat": "solid", "fit": "regular fit", "neckline": "hooded", "sleeve": "long sleeve"},
            {"slot": "top", "cat": "top", "color": "beige", "fab": "linen", "pat": "solid", "fit": "regular fit", "neckline": "scoop neck", "sleeve": "short sleeve"},
            # 5 bottoms
            {"slot": "bottom", "cat": "pants", "color": "navy", "fab": "cotton", "pat": "solid", "fit": "regular fit"},
            {"slot": "bottom", "cat": "jeans", "color": "blue", "fab": "denim", "pat": "solid", "fit": "slim fit"},
            {"slot": "bottom", "cat": "shorts", "color": "black", "fab": "cotton", "pat": "solid", "fit": "regular fit"},
            {"slot": "bottom", "cat": "skirt", "color": "grey", "fab": "cotton", "pat": "solid", "fit": "regular fit"},
            {"slot": "bottom", "cat": "pants", "color": "black", "fab": "wool", "pat": "solid", "fit": "regular fit"},
            # 2 one_piece
            {"slot": "one_piece", "cat": "dress", "color": "navy", "fab": "silk", "pat": "solid", "fit": "slim fit", "neckline": "v-neck", "sleeve": "short sleeve"},
            {"slot": "one_piece", "cat": "dress", "color": "black", "fab": "cotton", "pat": "solid", "fit": "regular fit", "neckline": "crew neck", "sleeve": "short sleeve"},
            # 2 outerwear
            {"slot": "outerwear", "cat": "blazer", "color": "navy", "fab": "wool", "pat": "solid", "fit": "regular fit", "neckline": "collar", "sleeve": "long sleeve"},
            {"slot": "outerwear", "cat": "jacket", "color": "blue", "fab": "denim", "pat": "solid", "fit": "regular fit", "neckline": "collar", "sleeve": "long sleeve"},
            # 3 footwear
            {"slot": "footwear", "cat": "sneakers", "color": "white", "fab": "cotton", "pat": "solid"},
            {"slot": "footwear", "cat": "shoes", "color": "black", "fab": "leather", "pat": "solid"},
            {"slot": "footwear", "cat": "boots", "color": "brown", "fab": "leather", "pat": "solid"},
            # 2 accessory
            {"slot": "accessory", "cat": "hat", "color": "beige", "fab": "cotton", "pat": "solid"},
            {"slot": "accessory", "cat": "hat", "color": "black", "fab": "wool", "pat": "solid"},
        ],
    },
    {
        "user_id": "user_003",
        "display_name": "Fashion User 003",
        "default_city": "Tokyo",
        "default_style": "streetwear",
        "items": [
            # 6 tops
            {"slot": "top", "cat": "hoodie", "color": "black", "fab": "cotton", "pat": "solid", "fit": "oversized", "neckline": "hooded", "sleeve": "long sleeve"},
            {"slot": "top", "cat": "t-shirt", "color": "white", "fab": "cotton", "pat": "graphic", "fit": "oversized", "neckline": "crew neck", "sleeve": "short sleeve"},
            {"slot": "top", "cat": "shirt", "color": "red", "fab": "flannel", "pat": "plaid", "fit": "oversized", "neckline": "collar", "sleeve": "long sleeve"},
            {"slot": "top", "cat": "sweater", "color": "grey", "fab": "cotton", "pat": "solid", "fit": "oversized", "neckline": "crew neck", "sleeve": "long sleeve"},
            {"slot": "top", "cat": "t-shirt", "color": "black", "fab": "cotton", "pat": "solid", "fit": "oversized", "neckline": "crew neck", "sleeve": "short sleeve"},
            {"slot": "top", "cat": "top", "color": "orange", "fab": "polyester", "pat": "solid", "fit": "regular fit", "neckline": "crew neck", "sleeve": "sleeveless"},
            # 5 bottoms
            {"slot": "bottom", "cat": "pants", "color": "black", "fab": "cotton", "pat": "solid", "fit": "oversized"},
            {"slot": "bottom", "cat": "jeans", "color": "blue", "fab": "denim", "pat": "solid", "fit": "oversized"},
            {"slot": "bottom", "cat": "shorts", "color": "grey", "fab": "cotton", "pat": "solid", "fit": "oversized"},
            {"slot": "bottom", "cat": "pants", "color": "green", "fab": "cotton", "pat": "camo", "fit": "oversized"},
            {"slot": "bottom", "cat": "skirt", "color": "black", "fab": "denim", "pat": "solid", "fit": "regular fit"},
            # 2 one_piece
            {"slot": "one_piece", "cat": "dress", "color": "black", "fab": "cotton", "pat": "graphic", "fit": "oversized", "neckline": "crew neck", "sleeve": "short sleeve"},
            {"slot": "one_piece", "cat": "dress", "color": "grey", "fab": "cotton", "pat": "solid", "fit": "oversized", "neckline": "hooded", "sleeve": "long sleeve"},
            # 2 outerwear
            {"slot": "outerwear", "cat": "jacket", "color": "black", "fab": "nylon", "pat": "solid", "fit": "oversized", "neckline": "collar", "sleeve": "long sleeve"},
            {"slot": "outerwear", "cat": "jacket", "color": "green", "fab": "cotton", "pat": "solid", "fit": "oversized", "neckline": "collar", "sleeve": "long sleeve"},
            # 3 footwear
            {"slot": "footwear", "cat": "sneakers", "color": "black", "fab": "leather", "pat": "solid"},
            {"slot": "footwear", "cat": "sneakers", "color": "red", "fab": "leather", "pat": "solid"},
            {"slot": "footwear", "cat": "boots", "color": "black", "fab": "leather", "pat": "solid"},
            # 2 accessory
            {"slot": "accessory", "cat": "hat", "color": "black", "fab": "cotton", "pat": "solid"},
            {"slot": "accessory", "cat": "hat", "color": "orange", "fab": "wool", "pat": "solid"},
        ],
    },
    {
        "user_id": "user_004",
        "display_name": "Fashion User 004",
        "default_city": "New York",
        "default_style": "office_formal",
        "items": [
            # 6 tops
            {"slot": "top", "cat": "shirt", "color": "white", "fab": "cotton", "pat": "solid", "fit": "slim fit", "neckline": "collar", "sleeve": "long sleeve"},
            {"slot": "top", "cat": "blouse", "color": "navy", "fab": "silk", "pat": "solid", "fit": "regular fit", "neckline": "v-neck", "sleeve": "long sleeve"},
            {"slot": "top", "cat": "shirt", "color": "blue", "fab": "cotton", "pat": "striped", "fit": "slim fit", "neckline": "collar", "sleeve": "long sleeve"},
            {"slot": "top", "cat": "sweater", "color": "black", "fab": "wool", "pat": "solid", "fit": "slim fit", "neckline": "turtleneck", "sleeve": "long sleeve"},
            {"slot": "top", "cat": "blouse", "color": "white", "fab": "silk", "pat": "solid", "fit": "regular fit", "neckline": "collar", "sleeve": "long sleeve"},
            {"slot": "top", "cat": "t-shirt", "color": "navy", "fab": "cotton", "pat": "solid", "fit": "slim fit", "neckline": "crew neck", "sleeve": "short sleeve"},
            # 5 bottoms
            {"slot": "bottom", "cat": "pants", "color": "charcoal", "fab": "wool", "pat": "solid", "fit": "slim fit"},
            {"slot": "bottom", "cat": "pants", "color": "black", "fab": "wool", "pat": "solid", "fit": "regular fit"},
            {"slot": "bottom", "cat": "skirt", "color": "navy", "fab": "wool", "pat": "solid", "fit": "slim fit"},
            {"slot": "bottom", "cat": "pants", "color": "navy", "fab": "wool", "pat": "pinstripe", "fit": "slim fit"},
            {"slot": "bottom", "cat": "shorts", "color": "black", "fab": "linen", "pat": "solid", "fit": "regular fit"},
            # 2 one_piece
            {"slot": "one_piece", "cat": "dress", "color": "navy", "fab": "wool", "pat": "solid", "fit": "slim fit", "neckline": "crew neck", "sleeve": "short sleeve"},
            {"slot": "one_piece", "cat": "dress", "color": "black", "fab": "silk", "pat": "solid", "fit": "slim fit", "neckline": "v-neck", "sleeve": "long sleeve"},
            # 2 outerwear
            {"slot": "outerwear", "cat": "blazer", "color": "charcoal", "fab": "wool", "pat": "solid", "fit": "slim fit", "neckline": "collar", "sleeve": "long sleeve"},
            {"slot": "outerwear", "cat": "blazer", "color": "navy", "fab": "wool", "pat": "solid", "fit": "slim fit", "neckline": "collar", "sleeve": "long sleeve"},
            # 3 footwear
            {"slot": "footwear", "cat": "shoes", "color": "black", "fab": "leather", "pat": "solid"},
            {"slot": "footwear", "cat": "shoes", "color": "burgundy", "fab": "leather", "pat": "solid"},
            {"slot": "footwear", "cat": "boots", "color": "black", "fab": "leather", "pat": "solid"},
            # 2 accessory
            {"slot": "accessory", "cat": "hat", "color": "black", "fab": "wool", "pat": "solid"},
            {"slot": "accessory", "cat": "hat", "color": "navy", "fab": "wool", "pat": "solid"},
        ],
    },
    {
        "user_id": "user_005",
        "display_name": "Fashion User 005",
        "default_city": "Nice",
        "default_style": "summer_resort",
        "items": [
            # 6 tops
            {"slot": "top", "cat": "shirt", "color": "white", "fab": "linen", "pat": "solid", "fit": "relaxed", "neckline": "collar", "sleeve": "short sleeve"},
            {"slot": "top", "cat": "t-shirt", "color": "blue", "fab": "cotton", "pat": "striped", "fit": "regular fit", "neckline": "crew neck", "sleeve": "short sleeve"},
            {"slot": "top", "cat": "top", "color": "yellow", "fab": "linen", "pat": "solid", "fit": "relaxed", "neckline": "scoop neck", "sleeve": "sleeveless"},
            {"slot": "top", "cat": "blouse", "color": "pink", "fab": "silk", "pat": "floral", "fit": "regular fit", "neckline": "v-neck", "sleeve": "short sleeve"},
            {"slot": "top", "cat": "shirt", "color": "beige", "fab": "linen", "pat": "solid", "fit": "relaxed", "neckline": "collar", "sleeve": "long sleeve"},
            {"slot": "top", "cat": "sweater", "color": "white", "fab": "cotton", "pat": "solid", "fit": "relaxed", "neckline": "crew neck", "sleeve": "long sleeve"},
            # 5 bottoms
            {"slot": "bottom", "cat": "shorts", "color": "white", "fab": "linen", "pat": "solid", "fit": "relaxed"},
            {"slot": "bottom", "cat": "pants", "color": "beige", "fab": "linen", "pat": "solid", "fit": "relaxed"},
            {"slot": "bottom", "cat": "skirt", "color": "blue", "fab": "cotton", "pat": "floral", "fit": "relaxed"},
            {"slot": "bottom", "cat": "shorts", "color": "blue", "fab": "cotton", "pat": "striped", "fit": "regular fit"},
            {"slot": "bottom", "cat": "jeans", "color": "white", "fab": "denim", "pat": "solid", "fit": "regular fit"},
            # 2 one_piece
            {"slot": "one_piece", "cat": "dress", "color": "yellow", "fab": "linen", "pat": "solid", "fit": "relaxed", "neckline": "v-neck", "sleeve": "sleeveless"},
            {"slot": "one_piece", "cat": "dress", "color": "pink", "fab": "silk", "pat": "floral", "fit": "relaxed", "neckline": "v-neck", "sleeve": "short sleeve"},
            # 2 outerwear
            {"slot": "outerwear", "cat": "jacket", "color": "beige", "fab": "linen", "pat": "solid", "fit": "relaxed", "neckline": "collar", "sleeve": "long sleeve"},
            {"slot": "outerwear", "cat": "jacket", "color": "white", "fab": "denim", "pat": "solid", "fit": "regular fit", "neckline": "collar", "sleeve": "long sleeve"},
            # 3 footwear
            {"slot": "footwear", "cat": "shoes", "color": "beige", "fab": "leather", "pat": "solid"},
            {"slot": "footwear", "cat": "sneakers", "color": "white", "fab": "cotton", "pat": "solid"},
            {"slot": "footwear", "cat": "shoes", "color": "brown", "fab": "leather", "pat": "solid"},
            # 2 accessory
            {"slot": "accessory", "cat": "hat", "color": "beige", "fab": "straw", "pat": "solid"},
            {"slot": "accessory", "cat": "hat", "color": "white", "fab": "cotton", "pat": "solid"},
        ],
    },
]


def load_real_image_paths() -> Dict[str, List[str]]:
    """Load verified unique clothing image paths from JSON file."""
    paths_file = os.path.join(os.path.dirname(__file__), "real_image_paths.json")
    if os.path.exists(paths_file):
        with open(paths_file, "r", encoding="utf-8") as f:
            return json.load(f)

    # Fallback to GitHub tree API if local file is missing
    import httpx

    api_url = "https://api.github.com/repos/alexeygrigorev/clothing-dataset-small/git/trees/master?recursive=1"
    resp = httpx.get(api_url, headers={"User-Agent": "Python"}, timeout=15.0)
    tree = resp.json().get("tree", [])

    by_cat: Dict[str, List[str]] = {}
    for item in tree:
        p = item["path"]
        if p.startswith("test/") and p.endswith(".jpg"):
            parts = p.split("/")
            if len(parts) >= 2:
                by_cat.setdefault(parts[1], []).append(p)

    return {
        "top": by_cat.get("t-shirt", [])[:15] + by_cat.get("shirt", [])[:12] + by_cat.get("longsleeve", [])[:10],
        "bottom": by_cat.get("pants", [])[:15] + by_cat.get("shorts", [])[:12] + by_cat.get("skirt", [])[:8],
        "one_piece": by_cat.get("dress", [])[:12],
        "outerwear": by_cat.get("outwear", [])[:15],
        "footwear": by_cat.get("shoes", [])[:20],
        "accessory": by_cat.get("hat", [])[:12],
    }


def generate_dummy_manifest(output_path: str = "tests/dummy/dummy_wardrobes.json") -> Dict[str, Any]:
    """Generate five dummy users with twenty unique garments each (one hundred items total)."""
    real_paths = load_real_image_paths()
    slot_cursors: Dict[str, int] = {slot: 0 for slot in real_paths}

    users: List[Dict[str, Any]] = []

    for persona in USER_PERSONAS:
        user_id = persona["user_id"]
        display_name = persona["display_name"]
        default_city = persona["default_city"]
        default_style = persona["default_style"]

        user_items: List[Dict[str, Any]] = []
        item_counter = 1

        for tmpl in persona["items"]:
            slot_name = tmpl["slot"]
            category = tmpl["cat"]
            color = tmpl["color"]
            fabric = tmpl["fab"]
            pattern = tmpl["pat"]
            fit = tmpl.get("fit", "regular fit")
            neckline = tmpl.get("neckline")
            sleeve = tmpl.get("sleeve")

            item_id = f"item-{user_id}-{slot_name}-{item_counter:03d}"

            # Assign next unique real image path for this slot
            slot_paths = real_paths.get(slot_name, [])
            if slot_cursors[slot_name] >= len(slot_paths):
                raise ValueError(f"Not enough unique image paths for slot: {slot_name}")

            rel_path = slot_paths[slot_cursors[slot_name]]
            slot_cursors[slot_name] += 1

            query_params: Dict[str, str] = {
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

            hints: Dict[str, str] = {
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

    manifest: Dict[str, Any] = {
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
