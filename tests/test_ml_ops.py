import numpy as np
import pytest
import torch
from fashion_pipeline.ml.image_ops import (
    decode_image_bytes,
    encode_image_png,
    isolate_and_crop_mask,
    prepare_stage1_tensor,
)
from fashion_pipeline.ml.tagger import (
    grouped_softmax_tagging,
    apply_conditional_rules,
)
from fashion_pipeline.schemas.job import FacetedTag


def test_decode_and_encode_image():
    # Create test RGB image
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[:, :] = [120, 150, 180]

    png_bytes = encode_image_png(img)
    assert len(png_bytes) > 0

    decoded = decode_image_bytes(png_bytes)
    assert decoded.shape == (100, 100, 3)
    np.testing.assert_array_equal(decoded[50, 50], [120, 150, 180])


def test_isolate_and_crop_mask_solid_white():
    # 200x200 image with black background and a red rectangle (50 to 100 y, 40 to 80 x)
    img = np.zeros((200, 200, 3), dtype=np.uint8)
    img[50:100, 40:80] = [255, 0, 0]  # Red garment

    # Create binary mask for the red garment
    mask = np.zeros((200, 200), dtype=np.uint8)
    mask[60:90, 50:70] = 255  # Inside the bounding box, partially covered

    cropped, (x_min, y_min, x_max, y_max) = isolate_and_crop_mask(img, mask)

    assert x_min == 50
    assert y_min == 60
    assert x_max == 70
    assert y_max == 90
    assert cropped.shape == (30, 20, 3)

    # Active mask pixels should retain garment pixels
    np.testing.assert_array_equal(cropped[10, 10], [255, 0, 0])


def test_prepare_stage1_tensor_shape():
    img = np.ones((300, 200, 3), dtype=np.uint8) * 128
    tensor = prepare_stage1_tensor(img)
    assert tensor.shape == (3, 224, 224)


def test_grouped_softmax_tagging_and_conditional_rules():
    vocab = {
        "category": ["top", "pants", "shoes"],
        "color": ["black", "white", "blue"],
        "sleeve": ["short sleeve", "long sleeve"],
        "neckline": ["crew neck", "v-neck"],
    }

    dim = 512
    # Create text embeddings
    cached_texts = {
        facet: torch.randn(len(labels), dim) for facet, labels in vocab.items()
    }
    for k in cached_texts:
        cached_texts[k] = torch.nn.functional.normalize(cached_texts[k], p=2, dim=-1)

    # Image embedding strongly correlated with "pants"
    img_embed = cached_texts["category"][1:2].clone()  # "pants"

    results = grouped_softmax_tagging(img_embed, cached_texts, vocab)
    assert len(results) == 1
    tags = results[0]

    assert tags["category"].label == "pants"
    # Conditional rules MUST suppress sleeve and neckline for pants!
    assert "sleeve" not in tags
    assert "neckline" not in tags
    assert "color" in tags


def test_conditional_suppression_accessories():
    tags = {
        "category": FacetedTag(label="sneakers", confidence=0.95),
        "color": FacetedTag(label="white", confidence=0.9),
        "sleeve": FacetedTag(label="short sleeve", confidence=0.4),
        "neckline": FacetedTag(label="crew neck", confidence=0.3),
    }
    apply_conditional_rules(tags)
    assert "sleeve" not in tags
    assert "neckline" not in tags
    assert "category" in tags
    assert "color" in tags


def test_conditional_keep_upper_clothes():
    tags = {
        "category": FacetedTag(label="blouse", confidence=0.95),
        "color": FacetedTag(label="pink", confidence=0.9),
        "sleeve": FacetedTag(label="long sleeve", confidence=0.85),
        "neckline": FacetedTag(label="v-neck", confidence=0.88),
    }
    apply_conditional_rules(tags)
    assert "sleeve" in tags
    assert "neckline" in tags
