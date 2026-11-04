import argparse
import json
import os
from typing import Generator, List, Optional, Tuple
from fashion_pipeline.utils.image_converter import (
    download_or_synthesize_garment_image,
    synthesize_garment_image,
)


def convert_url_to_image_bytes(image_url: str, timeout: float = 2.0) -> bytes:
    """Convert a garment URL into valid RGB image bytes."""
    return download_or_synthesize_garment_image(image_url, timeout=timeout)


def stream_dummy_wardrobe_images(
    manifest_path: str,
    target_user_id: Optional[str] = None,
) -> Generator[Tuple[str, str, bytes, dict], None, None]:
    """Stream converted garment image bytes directly from a wardrobe JSON manifest."""
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    users_data = data.get("users", [])
    for user_entry in users_data:
        u_id = user_entry.get("user_id")
        if target_user_id and u_id != target_user_id:
            continue
        items = user_entry.get("items", [])
        for item in items:
            item_id = item["item_id"]
            image_url = item["image_url"]
            image_bytes = convert_url_to_image_bytes(image_url)
            yield u_id, item_id, image_bytes, item


def batch_convert_to_directory(
    manifest_path: str,
    output_dir: str,
    target_user_id: Optional[str] = None,
) -> int:
    """Convert manifest garment URLs and save image files to target directory."""
    os.makedirs(output_dir, exist_ok=True)
    count = 0
    for u_id, item_id, image_bytes, _ in stream_dummy_wardrobe_images(manifest_path, target_user_id):
        user_dir = os.path.join(output_dir, u_id)
        os.makedirs(user_dir, exist_ok=True)
        out_file = os.path.join(user_dir, f"{item_id}.jpg")
        with open(out_file, "wb") as f:
            f.write(image_bytes)
        count += 1
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert dummy wardrobe garment URLs to image files")
    parser.add_argument("--manifest", default="tests/dummy/dummy_wardrobes.json", help="Path to manifest JSON")
    parser.add_argument("--outdir", default="data/dummy_images", help="Output directory")
    parser.add_argument("--user", default=None, help="Optional user ID filter")
    args = parser.parse_args()

    total = batch_convert_to_directory(args.manifest, args.outdir, args.user)
    print(f"Converted {total} garment images.")
