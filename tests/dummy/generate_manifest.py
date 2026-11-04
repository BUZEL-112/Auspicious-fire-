import json
import os
from urllib.parse import urlencode

CATEGORIES_BREAKDOWN = [
    ("top", 20, [
        {"cat": "t-shirt", "neckline": "crew neck", "sleeve": "short sleeve", "fab": "cotton", "pat": "solid", "fit": "regular fit"},
        {"cat": "shirt", "neckline": "collar", "sleeve": "long sleeve", "fab": "cotton", "pat": "solid", "fit": "slim fit"},
        {"cat": "blouse", "neckline": "v-neck", "sleeve": "long sleeve", "fab": "silk", "pat": "floral", "fit": "regular fit"},
        {"cat": "sweater", "neckline": "turtleneck", "sleeve": "long sleeve", "fab": "wool", "pat": "solid", "fit": "regular fit"},
        {"cat": "hoodie", "neckline": "hooded", "sleeve": "long sleeve", "fab": "cotton", "pat": "solid", "fit": "oversized"},
        {"cat": "top", "neckline": "scoop neck", "sleeve": "sleeveless", "fab": "linen", "pat": "solid", "fit": "regular fit"},
    ]),
    ("bottom", 14, [
        {"cat": "pants", "fab": "cotton", "pat": "solid", "fit": "regular fit"},
        {"cat": "jeans", "fab": "denim", "pat": "solid", "fit": "slim fit"},
        {"cat": "shorts", "fab": "cotton", "pat": "solid", "fit": "regular fit"},
        {"cat": "skirt", "fab": "linen", "pat": "floral", "fit": "regular fit"},
        {"cat": "pants", "fab": "wool", "pat": "plaid", "fit": "regular fit"},
        {"cat": "jeans", "fab": "denim", "pat": "solid", "fit": "loose fit"},
    ]),
    ("one_piece", 4, [
        {"cat": "dress", "neckline": "v-neck", "sleeve": "sleeveless", "fab": "silk", "pat": "solid", "fit": "slim fit"},
        {"cat": "dress", "neckline": "crew neck", "sleeve": "short sleeve", "fab": "cotton", "pat": "floral", "fit": "regular fit"},
        {"cat": "dress", "neckline": "square neck", "sleeve": "long sleeve", "fab": "knit", "pat": "solid", "fit": "regular fit"},
        {"cat": "dress", "neckline": "v-neck", "sleeve": "short sleeve", "fab": "chiffon", "pat": "polka dot", "fit": "regular fit"},
    ]),
    ("outerwear", 6, [
        {"cat": "blazer", "neckline": "collar", "sleeve": "long sleeve", "fab": "wool", "pat": "solid", "fit": "regular fit"},
        {"cat": "jacket", "neckline": "collar", "sleeve": "long sleeve", "fab": "denim", "pat": "solid", "fit": "regular fit"},
        {"cat": "coat", "neckline": "collar", "sleeve": "long sleeve", "fab": "wool", "pat": "solid", "fit": "regular fit"},
        {"cat": "jacket", "neckline": "hooded", "sleeve": "long sleeve", "fab": "leather", "pat": "solid", "fit": "regular fit"},
        {"cat": "blazer", "neckline": "collar", "sleeve": "long sleeve", "fab": "cotton", "pat": "plaid", "fit": "regular fit"},
        {"cat": "coat", "neckline": "collar", "sleeve": "long sleeve", "fab": "wool", "pat": "solid", "fit": "oversized"},
    ]),
    ("footwear", 10, [
        {"cat": "sneakers", "fab": "cotton", "pat": "solid", "color": "white"},
        {"cat": "sneakers", "fab": "cotton", "pat": "solid", "color": "black"},
        {"cat": "shoes", "fab": "leather", "pat": "solid", "color": "black"},
        {"cat": "shoes", "fab": "leather", "pat": "solid", "color": "brown"},
        {"cat": "boots", "fab": "leather", "pat": "solid", "color": "black"},
        {"cat": "boots", "fab": "leather", "pat": "solid", "color": "brown"},
        {"cat": "sandals", "fab": "leather", "pat": "solid", "color": "beige"},
        {"cat": "sandals", "fab": "leather", "pat": "solid", "color": "black"},
        {"cat": "shoes", "fab": "leather", "pat": "solid", "color": "navy"},
        {"cat": "sneakers", "fab": "cotton", "pat": "solid", "color": "grey"},
    ]),
    ("accessory", 6, [
        {"cat": "bag", "fab": "leather", "pat": "solid", "color": "black"},
        {"cat": "bag", "fab": "leather", "pat": "solid", "color": "brown"},
        {"cat": "hat", "fab": "cotton", "pat": "solid", "color": "beige"},
        {"cat": "hat", "fab": "wool", "pat": "solid", "color": "black"},
        {"cat": "scarf", "fab": "silk", "pat": "floral", "color": "red"},
        {"cat": "scarf", "fab": "wool", "pat": "plaid", "color": "grey"},
    ]),
]

COLOR_PALETTE = [
    "black", "white", "grey", "navy", "blue", "red", "green", "beige", "brown", "pink"
]


def generate_dummy_manifest(output_path: str = "tests/dummy/dummy_wardrobes.json") -> dict:
    """Generate 10 dummy users with 60 wardrobe items each (600 items total)."""
    users = []

    for u_idx in range(1, 11):
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

                image_url = f"https://dummyfashion.example.com/wardrobe/{user_id}/{slot_name}_{item_counter:03d}.jpg?{urlencode(query_params)}"

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

        assert len(user_items) == 60, f"Expected 60 items for {user_id}, got {len(user_items)}"
        users.append({
            "user_id": user_id,
            "display_name": display_name,
            "default_city": default_city,
            "default_style": default_style,
            "items_count": len(user_items),
            "items": user_items,
        })

    manifest = {
        "version": "1.0",
        "description": "Dummy wardrobe dataset containing 10 users with 60 clothing garments each (600 items total)",
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
