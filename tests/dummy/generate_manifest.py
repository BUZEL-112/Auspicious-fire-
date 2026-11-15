"""Generate the demo wardrobe manifest used by the Streamlit showcase and tests.

Every item maps to one explicit, hand-verified image in ``data/demo_wardrobe/images``.
Labels (category, color, fabric, ...) describe what is visible in that exact photo,
and each image was checked against the Stage 1 vision model before inclusion.
Image sources and licences are listed in ``data/demo_wardrobe/sources.json``.
"""

import json
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

IMAGE_DIR = "data/demo_wardrobe/images"


def _item(
    file: str,
    slot: str,
    cat: str,
    color: str,
    fab: str,
    pat: str = "solid",
    fit: str = "regular fit",
    neckline: Optional[str] = None,
    sleeve: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "file": file,
        "slot": slot,
        "cat": cat,
        "color": color,
        "fab": fab,
        "pat": pat,
        "fit": fit,
        "neckline": neckline,
        "sleeve": sleeve,
    }


USER_PERSONAS: List[Dict[str, Any]] = [
    {
        "user_id": "user_001",
        "display_name": "Daniel",
        "default_city": "London",
        "default_style": "smart_casual",
        "items": [
            _item("m1_shirt_pink_striped.jpg", "top", "shirt", "pink", "cotton", "striped", neckline="collar", sleeve="long sleeve"),
            _item("m1_tshirt_white.jpg", "top", "t-shirt", "white", "cotton", neckline="crew neck", sleeve="short sleeve"),
            _item("m1_sweater_brown.jpg", "top", "sweater", "brown", "wool", neckline="crew neck", sleeve="long sleeve"),
            _item("m1_chinos_beige.jpg", "bottom", "pants", "beige", "cotton"),
            _item("m1_jeans_navy.jpg", "bottom", "jeans", "navy", "denim", fit="slim fit"),
            _item("m1_coat_brown.jpg", "outerwear", "coat", "brown", "wool", neckline="collar", sleeve="long sleeve"),
            _item("m1_jacket_brown_leather.jpg", "outerwear", "jacket", "brown", "leather", neckline="collar", sleeve="long sleeve"),
            _item("m1_brogues_brown.jpg", "footwear", "shoes", "brown", "leather"),
            _item("m1_derby_brown.jpg", "footwear", "shoes", "brown", "leather"),
            _item("m1_sneakers_navy.jpg", "footwear", "sneakers", "navy", "polyester"),
        ],
    },
    {
        "user_id": "user_002",
        "display_name": "Kenji",
        "default_city": "Tokyo",
        "default_style": "streetwear",
        "items": [
            _item("m2_tshirt_black.jpg", "top", "t-shirt", "black", "cotton", neckline="crew neck", sleeve="short sleeve"),
            _item("m2_shirt_plaid.jpg", "top", "shirt", "multicolor", "cotton", "plaid", neckline="collar", sleeve="short sleeve"),
            _item("m2_sweater_grey_turtleneck.jpg", "top", "sweater", "grey", "wool", neckline="turtleneck", sleeve="long sleeve"),
            _item("m2_jeans_navy.jpg", "bottom", "jeans", "navy", "denim"),
            _item("m2_jeans_black.jpg", "bottom", "jeans", "black", "denim"),
            _item("m2_coat_black_leather.jpg", "outerwear", "coat", "black", "leather", neckline="collar", sleeve="long sleeve"),
            _item("m2_jacket_green_parka.jpg", "outerwear", "jacket", "green", "cotton", fit="loose fit", neckline="hooded", sleeve="long sleeve"),
            _item("m2_sneakers_black.jpg", "footwear", "sneakers", "black", "knit"),
            _item("m2_sneakers_grey.jpg", "footwear", "sneakers", "grey", "knit"),
            _item("m2_boots_black.jpg", "footwear", "boots", "black", "leather"),
        ],
    },
    {
        "user_id": "user_003",
        "display_name": "Amara",
        "default_city": "Lagos",
        "default_style": "office_chic",
        "items": [
            _item("f1_tshirt_white_vneck.jpg", "top", "t-shirt", "white", "cotton", neckline="v-neck", sleeve="short sleeve"),
            _item("f1_tshirt_grey_graphic.jpg", "top", "t-shirt", "grey", "cotton", "graphic", fit="slim fit", neckline="crew neck", sleeve="short sleeve"),
            _item("f1_sweater_pink.jpg", "top", "sweater", "pink", "wool", neckline="v-neck", sleeve="long sleeve"),
            _item("f1_skirt_denim.jpg", "bottom", "skirt", "blue", "denim", fit="slim fit"),
            _item("f1_pants_black_leather.jpg", "bottom", "pants", "black", "leather", fit="slim fit"),
            _item("f1_dress_red.jpg", "one_piece", "dress", "red", "polyester", fit="slim fit", neckline="crew neck", sleeve="long sleeve"),
            _item("f1_coat_beige_trench.jpg", "outerwear", "coat", "beige", "cotton", neckline="collar", sleeve="long sleeve"),
            _item("f1_coat_black_puffer.jpg", "outerwear", "coat", "black", "polyester", neckline="hooded", sleeve="long sleeve"),
            _item("f1_pumps_black.jpg", "footwear", "shoes", "black", "leather"),
            _item("f1_sneakers_navy_canvas.jpg", "footwear", "sneakers", "navy", "cotton"),
        ],
    },
]


def generate_dummy_manifest(output_path: str = "tests/dummy/dummy_wardrobes.json") -> Dict[str, Any]:
    """Generate three demo users with ten verified garments each (thirty items total)."""
    users: List[Dict[str, Any]] = []

    for persona in USER_PERSONAS:
        user_id = persona["user_id"]
        user_items: List[Dict[str, Any]] = []

        for idx, tmpl in enumerate(persona["items"], start=1):
            slot_name = tmpl["slot"]
            item_id = f"item-{user_id}-{slot_name}-{idx:03d}"

            hints: Dict[str, str] = {
                "slot": slot_name,
                "category": tmpl["cat"],
                "color": tmpl["color"],
                "fabric": tmpl["fab"],
                "pattern": tmpl["pat"],
                "fit": tmpl["fit"],
            }
            if tmpl["neckline"]:
                hints["neckline"] = tmpl["neckline"]
            if tmpl["sleeve"]:
                hints["sleeve"] = tmpl["sleeve"]

            # Hints ride along in the query string: API ingestion uses them as
            # authoritative labels, and local file loading strips them.
            query = urlencode({"user_id": user_id, "item_id": item_id, **hints})
            image_url = f"{IMAGE_DIR}/{tmpl['file']}?{query}"

            user_items.append({
                "item_id": item_id,
                "user_id": user_id,
                "image_url": image_url,
                "hints": hints,
            })

        users.append({
            "user_id": user_id,
            "display_name": persona["display_name"],
            "default_city": persona["default_city"],
            "default_style": persona["default_style"],
            "items_count": len(user_items),
            "items": user_items,
        })

    manifest: Dict[str, Any] = {
        "version": "3.0",
        "description": "Demo wardrobe dataset: 3 users with 10 hand-verified garments each (30 items total)",
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
