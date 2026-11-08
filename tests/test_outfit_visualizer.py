"""Unit tests for the outfit visualizer lookbook image generator."""

import io

from PIL import Image

from fashion_pipeline.schemas.wardrobe import WardrobeItemResponse
from fashion_pipeline.utils.outfit_visualizer import (
    build_stacked_outfit_bytes,
    build_stacked_outfit_image,
)


def test_build_stacked_outfit_image_top_bottom_footwear():
    """Verify composition of top + bottom + footwear outfit combination."""
    items = {
        "top": {
            "slot": "top",
            "category": "t-shirt",
            "color": "white",
            "fabric": "cotton",
        },
        "bottom": {
            "slot": "bottom",
            "category": "jeans",
            "color": "navy",
            "fabric": "denim",
        },
        "footwear": {
            "slot": "footwear",
            "category": "sneakers",
            "color": "white",
            "fabric": "leather",
        },
    }

    img = build_stacked_outfit_image(items, canvas_width=400)
    assert isinstance(img, Image.Image)
    assert img.mode == "RGB"
    assert img.width == 400
    assert img.height > 400


def test_build_stacked_outfit_image_one_piece_outerwear_accessory_footwear():
    """Verify composition of one_piece + outerwear + accessory + footwear outfit."""
    items = {
        "accessory": {
            "slot": "accessory",
            "category": "sunglasses",
            "color": "black",
        },
        "one_piece": {
            "slot": "one_piece",
            "category": "maxi dress",
            "color": "red",
            "fabric": "silk",
        },
        "outerwear": {
            "slot": "outerwear",
            "category": "denim jacket",
            "color": "blue",
            "fabric": "denim",
        },
        "footwear": {
            "slot": "footwear",
            "category": "sandals",
            "color": "beige",
            "fabric": "leather",
        },
    }

    img = build_stacked_outfit_image(items, canvas_width=420)
    assert isinstance(img, Image.Image)
    assert img.mode == "RGB"
    assert img.width == 420
    assert img.height > 500


def test_build_stacked_outfit_bytes_with_schema_responses():
    """Verify PNG bytes output when given WardrobeItemResponse objects."""
    top_item = WardrobeItemResponse(
        item_id="item-test-top-1",
        user_id="user_test",
        bucket="raw-images",
        object_key="stage_1/item1.jpg",
        status="READY",
        slot="top",
        category="blazer",
        color="grey",
        fabric="wool",
        created_at="2026-01-01T00:00:00",
        updated_at="2026-01-01T00:00:00",
    )
    bottom_item = WardrobeItemResponse(
        item_id="item-test-btm-1",
        user_id="user_test",
        bucket="raw-images",
        object_key="stage_1/item2.jpg",
        status="READY",
        slot="bottom",
        category="trousers",
        color="black",
        fabric="cotton",
        created_at="2026-01-01T00:00:00",
        updated_at="2026-01-01T00:00:00",
    )

    items = {"top": top_item, "bottom": bottom_item}
    raw_bytes = build_stacked_outfit_bytes(items, canvas_width=380, image_format="PNG")

    assert isinstance(raw_bytes, bytes)
    assert len(raw_bytes) > 100

    decoded = Image.open(io.BytesIO(raw_bytes))
    assert decoded.format == "PNG"
    assert decoded.width == 380


def test_empty_outfit_items():
    """Verify fallback handling when outfit has no items."""
    empty_img = build_stacked_outfit_image({}, canvas_width=350)
    assert isinstance(empty_img, Image.Image)
    assert empty_img.width == 350
    assert empty_img.height == 140
