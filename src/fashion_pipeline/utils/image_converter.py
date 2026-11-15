"""Garment image conversion and offline image synthesis utilities.

This module provides tools to download garment images from URLs or synthesize
clean visual garment representations when offline.
"""

import hashlib
import io
import logging
import os
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import httpx
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

COLOR_MAP: Dict[str, Tuple[int, int, int]] = {
    "black": (30, 30, 30),
    "white": (245, 245, 245),
    "grey": (128, 128, 128),
    "gray": (128, 128, 128),
    "charcoal": (55, 60, 68),
    "navy": (20, 35, 75),
    "blue": (40, 100, 200),
    "red": (210, 40, 40),
    "green": (40, 140, 60),
    "olive": (95, 110, 55),
    "yellow": (230, 200, 50),
    "pink": (230, 120, 160),
    "purple": (120, 50, 160),
    "beige": (220, 205, 180),
    "cream": (245, 240, 225),
    "brown": (110, 70, 40),
    "tan": (195, 155, 115),
    "burgundy": (128, 20, 40),
    "orange": (230, 120, 30),
    "multicolor": (150, 100, 180),
}


def _get_outline_and_pattern_color(rgb: Tuple[int, int, int]) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
    """Calculate outline and pattern accent colors that contrast with garment fill."""
    lum = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
    if lum > 160:
        outline = (max(0, rgb[0] - 80), max(0, rgb[1] - 80), max(0, rgb[2] - 80))
        pattern_col = (max(0, rgb[0] - 50), max(0, rgb[1] - 50), max(0, rgb[2] - 50))
    else:
        outline = (min(255, rgb[0] + 70), min(255, rgb[1] + 70), min(255, rgb[2] + 70))
        pattern_col = (min(255, rgb[0] + 50), min(255, rgb[1] + 50), min(255, rgb[2] + 50))
    return outline, pattern_col


def _draw_pattern(
    draw: ImageDraw.ImageDraw,
    pattern: str,
    box: Tuple[int, int, int, int],
    pattern_color: Tuple[int, int, int],
) -> None:
    """Draw texture pattern lines or shapes inside bounding box."""
    x0, y0, x1, y1 = box
    pat = pattern.lower().replace("_", " ")

    if "stripe" in pat:
        step = 14
        for x in range(x0 + 4, x1 - 4, step):
            draw.line([(x, y0 + 10), (x, y1 - 10)], fill=pattern_color, width=2)
    elif "plaid" in pat or "check" in pat:
        step = 20
        for x in range(x0 + 6, x1 - 6, step):
            draw.line([(x, y0 + 8), (x, y1 - 8)], fill=pattern_color, width=2)
        for y in range(y0 + 12, y1 - 8, step):
            draw.line([(x0 + 8, y), (x1 - 8, y)], fill=pattern_color, width=2)
    elif "dot" in pat:
        step_x = 22
        step_y = 20
        for x in range(x0 + 10, x1 - 10, step_x):
            for y in range(y0 + 12, y1 - 12, step_y):
                draw.ellipse([(x - 2, y - 2), (x + 2, y + 2)], fill=pattern_color)
    elif "floral" in pat or "print" in pat or "camo" in pat:
        step_x = 30
        step_y = 28
        for x in range(x0 + 12, x1 - 12, step_x):
            for y in range(y0 + 14, y1 - 14, step_y):
                draw.ellipse([(x - 3, y - 1), (x + 3, y + 1)], fill=pattern_color)
                draw.ellipse([(x - 1, y - 3), (x + 1, y + 3)], fill=pattern_color)


def _draw_top_silhouette(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    fill: Tuple[int, int, int],
    outline: Tuple[int, int, int],
    category: str,
    sleeve: Optional[str],
    neckline: Optional[str],
) -> None:
    """Draw shirt, blouse, hoodie, sweater, or outerwear silhouette."""
    x0, y0, x1, y1 = box
    w = x1 - x0
    h = y1 - y0
    cx = (x0 + x1) // 2

    # Neckline depth
    is_vneck = neckline and "v-neck" in neckline.lower()
    neck_depth = int(h * 0.18) if is_vneck else int(h * 0.10)

    # Sleeve dimensions
    is_sleeveless = sleeve and "sleeveless" in sleeve.lower()
    is_long_sleeve = (sleeve and "long" in sleeve.lower()) or category in {"sweater", "hoodie", "blazer", "jacket", "coat"}

    if is_sleeveless:
        points = [
            (cx - int(w * 0.16), y0 + neck_depth),
            (cx - int(w * 0.24), y0 + 4),
            (cx - int(w * 0.32), y0 + int(h * 0.28)),
            (cx - int(w * 0.28), y1),
            (cx + int(w * 0.28), y1),
            (cx + int(w * 0.32), y0 + int(h * 0.28)),
            (cx + int(w * 0.24), y0 + 4),
            (cx + int(w * 0.16), y0 + neck_depth),
        ]
    elif is_long_sleeve:
        points = [
            (cx - int(w * 0.14), y0 + neck_depth),
            (cx - int(w * 0.24), y0 + 4),
            (x0, y0 + int(h * 0.25)),
            (x0 + int(w * 0.08), y0 + int(h * 0.70)),
            (cx - int(w * 0.26), y0 + int(h * 0.36)),
            (cx - int(w * 0.26), y1),
            (cx + int(w * 0.26), y1),
            (cx + int(w * 0.26), y0 + int(h * 0.36)),
            (x1 - int(w * 0.08), y0 + int(h * 0.70)),
            (x1, y0 + int(h * 0.25)),
            (cx + int(w * 0.24), y0 + 4),
            (cx + int(w * 0.14), y0 + neck_depth),
        ]
    else:  # Short sleeve (default)
        points = [
            (cx - int(w * 0.14), y0 + neck_depth),
            (cx - int(w * 0.24), y0 + 4),
            (x0 + int(w * 0.04), y0 + int(h * 0.22)),
            (x0 + int(w * 0.12), y0 + int(h * 0.38)),
            (cx - int(w * 0.26), y0 + int(h * 0.32)),
            (cx - int(w * 0.26), y1),
            (cx + int(w * 0.26), y1),
            (cx + int(w * 0.26), y0 + int(h * 0.32)),
            (x1 - int(w * 0.12), y0 + int(h * 0.38)),
            (x1 - int(w * 0.04), y0 + int(h * 0.22)),
            (cx + int(w * 0.24), y0 + 4),
            (cx + int(w * 0.14), y0 + neck_depth),
        ]

    draw.polygon(points, fill=fill, outline=outline)

    # Collar detail for buttoned shirts and blazers
    if (category in {"shirt", "blazer"} or (neckline and "collar" in neckline.lower())):
        draw.line([(cx, y0 + neck_depth), (cx, y1)], fill=outline, width=2)
        draw.polygon([(cx - int(w * 0.12), y0 + 4), (cx, y0 + neck_depth), (cx - 4, y0 + 4)], fill=fill, outline=outline)
        draw.polygon([(cx + int(w * 0.12), y0 + 4), (cx, y0 + neck_depth), (cx + 4, y0 + 4)], fill=fill, outline=outline)

    # Hood contour for hoodies
    if category == "hoodie" or (neckline and "hood" in neckline.lower()):
        draw.arc([cx - int(w * 0.22), y0 - int(h * 0.06), cx + int(w * 0.22), y0 + int(h * 0.22)], start=160, end=20, fill=outline, width=2)


def _draw_bottom_silhouette(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    fill: Tuple[int, int, int],
    outline: Tuple[int, int, int],
    category: str,
) -> None:
    """Draw pants, jeans, shorts, or skirt silhouette."""
    x0, y0, x1, y1 = box
    w = x1 - x0
    h = y1 - y0
    cx = (x0 + x1) // 2

    if "skirt" in category:
        points = [
            (cx - int(w * 0.22), y0),
            (cx + int(w * 0.22), y0),
            (cx + int(w * 0.44), y1),
            (cx - int(w * 0.44), y1),
        ]
        draw.polygon(points, fill=fill, outline=outline)
        # Pleat lines
        draw.line([(cx, y0 + 6), (cx, y1 - 2)], fill=outline, width=1)
        draw.line([(cx - int(w * 0.16), y0 + 6), (cx - int(w * 0.22), y1 - 2)], fill=outline, width=1)
        draw.line([(cx + int(w * 0.16), y0 + 6), (cx + int(w * 0.22), y1 - 2)], fill=outline, width=1)
    elif "short" in category:
        points = [
            (cx - int(w * 0.28), y0),
            (cx + int(w * 0.28), y0),
            (cx + int(w * 0.32), y0 + int(h * 0.60)),
            (cx + int(w * 0.08), y0 + int(h * 0.60)),
            (cx, y0 + int(h * 0.36)),
            (cx - int(w * 0.08), y0 + int(h * 0.60)),
            (cx - int(w * 0.32), y0 + int(h * 0.60)),
        ]
        draw.polygon(points, fill=fill, outline=outline)
    else:  # Pants / Jeans / Trousers
        points = [
            (cx - int(w * 0.26), y0),
            (cx + int(w * 0.26), y0),
            (cx + int(w * 0.28), y1),
            (cx + int(w * 0.07), y1),
            (cx, y0 + int(h * 0.42)),
            (cx - int(w * 0.07), y1),
            (cx - int(w * 0.28), y1),
        ]
        draw.polygon(points, fill=fill, outline=outline)
        # Waistband and fly line
        draw.line([(cx - int(w * 0.26), y0 + 8), (cx + int(w * 0.26), y0 + 8)], fill=outline, width=1)
        draw.line([(cx, y0 + 8), (cx, y0 + int(h * 0.38))], fill=outline, width=1)


def _draw_one_piece_silhouette(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    fill: Tuple[int, int, int],
    outline: Tuple[int, int, int],
    category: str,
    sleeve: Optional[str],
    neckline: Optional[str],
) -> None:
    """Draw dress or jumpsuit silhouette."""
    x0, y0, x1, y1 = box
    w = x1 - x0
    h = y1 - y0
    cx = (x0 + x1) // 2

    points = [
        (cx - int(w * 0.16), y0 + 12),
        (cx - int(w * 0.26), y0 + 2),
        (cx - int(w * 0.22), y0 + int(h * 0.28)),
        (cx - int(w * 0.14), y0 + int(h * 0.42)),
        (cx - int(w * 0.40), y1),
        (cx + int(w * 0.40), y1),
        (cx + int(w * 0.14), y0 + int(h * 0.42)),
        (cx + int(w * 0.22), y0 + int(h * 0.28)),
        (cx + int(w * 0.26), y0 + 2),
        (cx + int(w * 0.16), y0 + 12),
    ]
    draw.polygon(points, fill=fill, outline=outline)
    # Waist line
    draw.line([(cx - int(w * 0.14), y0 + int(h * 0.42)), (cx + int(w * 0.14), y0 + int(h * 0.42))], fill=outline, width=2)


def _draw_footwear_silhouette(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    fill: Tuple[int, int, int],
    outline: Tuple[int, int, int],
    category: str,
) -> None:
    """Draw shoe, sneaker, or boot silhouette."""
    x0, y0, x1, y1 = box
    w = x1 - x0
    h = y1 - y0
    cx = (x0 + x1) // 2

    is_boot = "boot" in category.lower()
    top_y = y0 + int(h * 0.18) if is_boot else y0 + int(h * 0.42)

    # Sole and upper side profile
    sole_points = [
        (cx - int(w * 0.36), y1 - 4),
        (cx + int(w * 0.38), y1 - 4),
        (cx + int(w * 0.36), y1),
        (cx - int(w * 0.38), y1),
    ]
    draw.polygon(sole_points, fill=(230, 230, 230), outline=outline)

    upper_points = [
        (cx - int(w * 0.36), y1 - 4),
        (cx - int(w * 0.34), top_y),
        (cx - int(w * 0.14), top_y),
        (cx, y0 + int(h * 0.60)),
        (cx + int(w * 0.34), y0 + int(h * 0.70)),
        (cx + int(w * 0.38), y1 - 4),
    ]
    draw.polygon(upper_points, fill=fill, outline=outline)

    # Sneaker sole accent
    if "sneaker" in category.lower():
        draw.line([(cx - int(w * 0.36), y1 - 8), (cx + int(w * 0.36), y1 - 8)], fill=outline, width=1)


def _draw_accessory_silhouette(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    fill: Tuple[int, int, int],
    outline: Tuple[int, int, int],
    category: str,
) -> None:
    """Draw hat or sunglasses silhouette."""
    x0, y0, x1, y1 = box
    w = x1 - x0
    h = y1 - y0
    cx = (x0 + x1) // 2

    if "glass" in category.lower():
        # Sunglasses frame
        lens_w = int(w * 0.28)
        lens_h = int(h * 0.28)
        cy = y0 + int(h * 0.48)
        draw.rounded_rectangle([cx - lens_w - 6, cy - lens_h // 2, cx - 6, cy + lens_h // 2], radius=4, fill=(40, 45, 50), outline=outline)
        draw.rounded_rectangle([cx + 6, cy - lens_h // 2, cx + lens_w + 6, cy + lens_h // 2], radius=4, fill=(40, 45, 50), outline=outline)
        draw.line([(cx - 6, cy - 2), (cx + 6, cy - 2)], fill=outline, width=2)
    else:  # Hat (default accessory)
        brim_points = [
            (cx - int(w * 0.42), y0 + int(h * 0.68)),
            (cx + int(w * 0.42), y0 + int(h * 0.68)),
            (cx + int(w * 0.38), y0 + int(h * 0.74)),
            (cx - int(w * 0.38), y0 + int(h * 0.74)),
        ]
        draw.polygon(brim_points, fill=fill, outline=outline)
        crown_points = [
            (cx - int(w * 0.24), y0 + int(h * 0.68)),
            (cx - int(w * 0.20), y0 + int(h * 0.24)),
            (cx + int(w * 0.20), y0 + int(h * 0.24)),
            (cx + int(w * 0.24), y0 + int(h * 0.68)),
        ]
        draw.polygon(crown_points, fill=fill, outline=outline)
        # Ribbon band
        draw.rectangle([cx - int(w * 0.24), y0 + int(h * 0.62), cx + int(w * 0.24), y0 + int(h * 0.68)], fill=outline)


def _draw_caption_badge(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    category: str,
    color_key: str,
) -> None:
    """Draw small centered caption badge at bottom of canvas."""
    text = f"{color_key.capitalize()} {category.replace('_', ' ').title()}"
    bbox = draw.textbbox((0, 0), text)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    bx = (width - tw) // 2 - 8
    by = height - 22
    draw.rounded_rectangle([bx, by, bx + tw + 16, by + th + 6], radius=4, fill=(245, 247, 250), outline=(220, 225, 230))
    draw.text(((width - tw) // 2, by + 3), text, fill=(60, 70, 80))


def synthesize_garment_image(
    image_url: str,
    width: int = 256,
    height: int = 256,
) -> bytes:
    """Generate a clean visual garment silhouette on studio background for offline environments."""
    parsed = urlparse(image_url)
    params = parse_qs(parsed.query)

    color_key = params.get("color", ["grey"])[0].lower()
    category = params.get("category", ["top"])[0].lower()
    slot = params.get("slot", ["top"])[0].lower()
    pattern = params.get("pattern", ["solid"])[0].lower()
    sleeve = params.get("sleeve", [None])[0]
    neckline = params.get("neckline", [None])[0]

    rgb_color = COLOR_MAP.get(color_key)
    if rgb_color is None:
        hasher = hashlib.md5(image_url.encode("utf-8"))
        digest = hasher.digest()
        rgb_color = (int(digest[0]), int(digest[1]), int(digest[2]))

    # Studio background
    bg_color = (240, 243, 246) if color_key in {"white", "cream"} else (255, 255, 255)
    image = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(image)

    outline_color, pattern_color = _get_outline_and_pattern_color(rgb_color)

    # Active garment box
    pad_x = int(width * 0.16)
    pad_y = int(height * 0.12)
    bottom_y = height - 32
    box = (pad_x, pad_y, width - pad_x, bottom_y)

    # Select silhouette based on slot and category
    if slot == "top" or category in {"t-shirt", "shirt", "blouse", "sweater", "hoodie", "top", "blazer", "jacket", "coat"}:
        _draw_top_silhouette(draw, box, rgb_color, outline_color, category, sleeve, neckline)
    elif slot == "bottom" or category in {"pants", "jeans", "shorts", "skirt", "trousers"}:
        _draw_bottom_silhouette(draw, box, rgb_color, outline_color, category)
    elif slot == "one_piece" or category in {"dress", "jumpsuit", "romper"}:
        _draw_one_piece_silhouette(draw, box, rgb_color, outline_color, category, sleeve, neckline)
    elif slot == "footwear" or category in {"shoes", "sneakers", "boots", "sandals", "loafers"}:
        _draw_footwear_silhouette(draw, box, rgb_color, outline_color, category)
    elif slot == "accessory" or category in {"hat", "sunglasses", "belt", "cap"}:
        _draw_accessory_silhouette(draw, box, rgb_color, outline_color, category)
    else:
        # Fallback centered rectangle with rounded corners
        draw.rounded_rectangle(box, radius=8, fill=rgb_color, outline=outline_color)

    # Pattern texture overlay
    if pattern and pattern != "solid":
        _draw_pattern(draw, pattern, box, pattern_color)

    # Bottom caption badge
    _draw_caption_badge(draw, width, height, category, color_key)

    output = io.BytesIO()
    image.save(output, format="JPEG", quality=90)
    return output.getvalue()


def download_or_synthesize_garment_image(
    image_url: str,
    timeout: float = 2.0,
) -> bytes:
    """Convert a garment image URL or local file path into image bytes with fallback to local synthesis."""
    if image_url and not image_url.startswith(("http://", "https://")) and os.path.isfile(image_url):
        with open(image_url, "rb") as f:
            return f.read()

    if "example.com" not in image_url and image_url.startswith(("http://", "https://")):
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(image_url)
                if resp.status_code == 200 and len(resp.content) > 100:
                    return resp.content
        except Exception as exc:
            logger.debug(f"HTTP GET failed for {image_url}: {exc}. Using synthesizer fallback.")

    return synthesize_garment_image(image_url)
