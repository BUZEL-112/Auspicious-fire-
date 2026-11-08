"""Outfit lookbook composite image generator.

Composes individual garments of an outfit combination into an anatomical,
vertically stacked lookbook composite image with slot and category labels.
"""

import io
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from PIL import Image, ImageDraw, ImageFont

from fashion_pipeline.utils.image_converter import (
    download_or_synthesize_garment_image,
    synthesize_garment_image,
)

logger = logging.getLogger(__name__)

# Row layout height constants in pixels
HEIGHT_ACCESSORY = 110
HEIGHT_TOP_OUTERWEAR = 190
HEIGHT_ONE_PIECE = 260
HEIGHT_BOTTOM = 190
HEIGHT_FOOTWEAR = 130
HEIGHT_DEFAULT = 170

# Colors for presentation
BG_CANVAS = (248, 250, 252)
BG_CARD = (255, 255, 255)
BORDER_CARD = (226, 232, 240)
TEXT_PRIMARY = (15, 23, 42)
TEXT_MUTED = (100, 116, 139)
BADGE_BG = (241, 245, 249)
BADGE_TEXT = (37, 99, 235)


def _extract_item_metadata(item: Any, slot_hint: str) -> Dict[str, str]:
    """Extract slot, category, color, fabric, and image url from an item object or dictionary."""
    if isinstance(item, dict):
        hints = item.get("hints", {})
        slot = item.get("slot") or hints.get("slot") or slot_hint
        category = item.get("category") or hints.get("category") or slot
        color = item.get("color") or hints.get("color") or "neutral"
        fabric = item.get("fabric") or hints.get("fabric") or ""
        url = item.get("source_url") or item.get("image_url") or ""
    else:
        slot = getattr(item, "slot", None) or slot_hint
        category = getattr(item, "category", None) or slot
        color = getattr(item, "color", None) or "neutral"
        fabric = getattr(item, "fabric", None) or ""
        url = getattr(item, "source_url", None) or getattr(item, "image_url", None) or ""

    return {
        "slot": str(slot).lower(),
        "category": str(category).replace("_", " ").title(),
        "color": str(color).replace("_", " ").title(),
        "fabric": str(fabric).replace("_", " ").title(),
        "url": str(url) if url else "",
    }


def _resolve_garment_image(
    item: Any,
    slot: str,
    meta: Dict[str, str],
    garment_images: Optional[Dict[str, Union[bytes, Image.Image]]] = None,
) -> Image.Image:
    """Retrieve or synthesize an RGB PIL image for a garment item."""
    if garment_images and slot in garment_images:
        val = garment_images[slot]
        if isinstance(val, Image.Image):
            return val.convert("RGB")
        if isinstance(val, (bytes, bytearray)):
            return Image.open(io.BytesIO(val)).convert("RGB")

    raw_bytes = (
        item.get("image_bytes")
        if isinstance(item, dict)
        else getattr(item, "image_bytes", None)
    )
    if raw_bytes and isinstance(raw_bytes, (bytes, bytearray)):
        try:
            return Image.open(io.BytesIO(raw_bytes)).convert("RGB")
        except Exception as exc:
            logger.debug(f"Failed to decode item image bytes: {exc}")

    url = meta.get("url")
    if url:
        try:
            image_bytes = download_or_synthesize_garment_image(url)
            return Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception as exc:
            logger.debug(f"Failed to fetch image from URL {url}: {exc}")

    synth_url = (
        f"https://example.com/synth?slot={meta['slot']}&category="
        f"{meta['category']}&color={meta['color']}"
    )
    image_bytes = synthesize_garment_image(synth_url)
    return Image.open(io.BytesIO(image_bytes)).convert("RGB")


def _render_garment_card(
    draw: ImageDraw.ImageDraw,
    canvas: Image.Image,
    garment_img: Image.Image,
    meta: Dict[str, str],
    box: Tuple[int, int, int, int],
    font: ImageFont.ImageFont,
) -> None:
    """Render a single garment card with image and labels inside the given bounding box."""
    x1, y1, x2, y2 = box

    # Draw card background and subtle border
    draw.rounded_rectangle([x1, y1, x2, y2], radius=8, fill=BG_CARD, outline=BORDER_CARD, width=1)

    # Label area at top (height 34px)
    label_h = 34
    slot_label = meta["slot"].upper()
    cat_label = meta["category"]
    color_label = meta["color"]
    detail_text = f"{cat_label} - {color_label}" if color_label != "Neutral" else cat_label

    # Slot badge on the left
    badge_x = x1 + 8
    badge_y = y1 + 8
    draw.rectangle([badge_x, badge_y, badge_x + 64, badge_y + 16], fill=BADGE_BG)
    draw.text((badge_x + 4, badge_y + 2), slot_label[:8], fill=BADGE_TEXT, font=font)

    # Detail text on the right
    draw.text((badge_x + 70, badge_y + 2), detail_text[:22], fill=TEXT_PRIMARY, font=font)

    # Available image rectangle
    img_pad = 8
    avail_x1 = x1 + img_pad
    avail_y1 = y1 + label_h + 2
    avail_x2 = x2 - img_pad
    avail_y2 = y2 - img_pad

    avail_w = max(10, avail_x2 - avail_x1)
    avail_h = max(10, avail_y2 - avail_y1)

    # Scale garment image preserving aspect ratio
    src_w, src_h = garment_img.size
    scale = min(avail_w / max(1, src_w), avail_h / max(1, src_h))
    new_w = max(1, int(src_w * scale))
    new_h = max(1, int(src_h * scale))

    resized = garment_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # Center resized image in available space
    paste_x = avail_x1 + (avail_w - new_w) // 2
    paste_y = avail_y1 + (avail_h - new_h) // 2

    canvas.paste(resized, (paste_x, paste_y))


def build_stacked_outfit_image(
    outfit_items: Dict[str, Any],
    canvas_width: int = 420,
    garment_images: Optional[Dict[str, Union[bytes, Image.Image]]] = None,
) -> Image.Image:
    """Compose outfit garments vertically in anatomical lookbook order.

    Anatomical lookbook order:
    1. Accessory (if present)
    2. Upper body: Top and Outerwear side-by-side, or One-piece and Outerwear
    3. Lower body: Bottom (if One-piece is not present)
    4. Footwear (if present)
    """
    normalized_items: Dict[str, Any] = {}
    for slot_key, item in outfit_items.items():
        if item is not None:
            normalized_items[slot_key.lower()] = item

    has_accessory = "accessory" in normalized_items
    has_top = "top" in normalized_items
    has_one_piece = "one_piece" in normalized_items
    has_outerwear = "outerwear" in normalized_items
    has_bottom = "bottom" in normalized_items
    has_footwear = "footwear" in normalized_items

    # Determine structured rows
    # Each row is a tuple: (list_of_slots, row_height)
    rows: List[Tuple[List[str], int]] = []

    # 1. Top row: accessory
    if has_accessory:
        rows.append((["accessory"], HEIGHT_ACCESSORY))

    # 2. Upper row: top / one_piece and outerwear
    upper_slots: List[str] = []
    if has_one_piece:
        upper_slots.append("one_piece")
    elif has_top:
        upper_slots.append("top")

    if has_outerwear:
        upper_slots.append("outerwear")

    if upper_slots:
        upper_h = HEIGHT_ONE_PIECE if has_one_piece else HEIGHT_TOP_OUTERWEAR
        rows.append((upper_slots, upper_h))

    # 3. Lower row: bottom (only if not one_piece)
    if has_bottom and not has_one_piece:
        rows.append((["bottom"], HEIGHT_BOTTOM))

    # 4. Footwear
    if has_footwear:
        rows.append((["footwear"], HEIGHT_FOOTWEAR))

    # 5. Any residual slots not in standard taxonomy
    standard_slots = {"accessory", "top", "one_piece", "outerwear", "bottom", "footwear"}
    for slot_key in normalized_items:
        if slot_key not in standard_slots:
            rows.append(([slot_key], HEIGHT_DEFAULT))

    if not rows:
        # Fallback empty canvas with message
        empty = Image.new("RGB", (canvas_width, 140), BG_CANVAS)
        draw = ImageDraw.Draw(empty)
        font = ImageFont.load_default()
        draw.text((20, 60), "No outfit items to display", fill=TEXT_MUTED, font=font)
        return empty

    # Calculate total canvas height
    margin = 16
    gap = 12
    total_height = margin * 2 + sum(h for _, h in rows) + gap * (len(rows) - 1)

    canvas = Image.new("RGB", (canvas_width, total_height), BG_CANVAS)
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()

    curr_y = margin
    content_width = canvas_width - (margin * 2)

    for slot_list, row_h in rows:
        col_count = len(slot_list)
        if col_count == 1:
            slot_name = slot_list[0]
            item = normalized_items[slot_name]
            meta = _extract_item_metadata(item, slot_name)
            img = _resolve_garment_image(item, slot_name, meta, garment_images)
            box = (margin, curr_y, margin + content_width, curr_y + row_h)
            _render_garment_card(draw, canvas, img, meta, box, font)
        else:
            col_gap = 10
            col_width = (content_width - (col_gap * (col_count - 1))) // col_count
            for i, slot_name in enumerate(slot_list):
                col_x1 = margin + i * (col_width + col_gap)
                col_x2 = col_x1 + col_width
                item = normalized_items[slot_name]
                meta = _extract_item_metadata(item, slot_name)
                img = _resolve_garment_image(item, slot_name, meta, garment_images)
                box = (col_x1, curr_y, col_x2, curr_y + row_h)
                _render_garment_card(draw, canvas, img, meta, box, font)

        curr_y += row_h + gap

    return canvas


def build_stacked_outfit_bytes(
    outfit_items: Dict[str, Any],
    canvas_width: int = 420,
    garment_images: Optional[Dict[str, Union[bytes, Image.Image]]] = None,
    image_format: str = "PNG",
) -> bytes:
    """Generate stacked composite outfit image and return raw encoded bytes."""
    canvas = build_stacked_outfit_image(
        outfit_items=outfit_items,
        canvas_width=canvas_width,
        garment_images=garment_images,
    )
    output = io.BytesIO()
    canvas.save(output, format=image_format)
    return output.getvalue()
