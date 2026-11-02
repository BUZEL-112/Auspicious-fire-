import cv2
import numpy as np
import pytest
from fashion_pipeline.ml.engine import FashionVisionEngine


@pytest.fixture(scope="module")
def vision_engine():
    engine = FashionVisionEngine(device="cpu", use_fp16=False)
    engine.cold_start_init()
    return engine


def test_stage1_pipeline_execution(vision_engine):
    # Create synthetic image
    img = (np.random.rand(300, 300, 3) * 255).astype(np.uint8)
    _, buf = cv2.imencode(".jpg", img)

    pieces = vision_engine.process_stage1(buf.tobytes())
    assert len(pieces) == 1
    piece = pieces[0]
    assert piece.piece_id == "piece_0"
    assert piece.bbox.width == 300
    assert piece.bbox.height == 300
    assert "category" in piece.tags
    assert "color" in piece.tags


def test_stage2_pipeline_execution(vision_engine):
    img = (np.random.rand(400, 300, 3) * 255).astype(np.uint8)
    _, buf = cv2.imencode(".jpg", img)

    pieces, crops = vision_engine.process_stage2(buf.tobytes(), min_pixel_threshold=100)
    assert len(pieces) >= 1
    assert len(crops) == len(pieces)

    for i, piece in enumerate(pieces):
        assert piece.piece_id == f"piece_{i}"
        assert piece.pixel_count >= 100
        assert piece.bbox.width > 0
        assert piece.bbox.height > 0
        assert len(piece.tags) > 0
        assert piece.person_id is not None
        assert piece.layer_role is not None


def test_detect_person_instances_fallback(vision_engine):
    img = np.zeros((200, 200, 3), dtype=np.uint8)
    boxes = vision_engine.detect_person_instances(img)
    assert len(boxes) >= 1
    assert boxes[0] == (0, 0, 200, 200)


def test_split_upper_body_layers_fallback(vision_engine):
    crop = np.zeros((100, 100, 3), dtype=np.uint8)
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[20:80, 20:80] = 1
    sub_instances = vision_engine.split_upper_body_layers(crop, mask)
    assert len(sub_instances) == 1
    assert sub_instances[0]["sub_role"] == "single_top"
    assert np.sum(sub_instances[0]["mask"]) > 0


def test_stage2_no_garments_detected_error(vision_engine):
    # Empty image where mock segformer finds 0 pixels above high threshold
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    _, buf = cv2.imencode(".jpg", img)

    with pytest.raises(ValueError, match="NO_GARMENTS_DETECTED"):
        vision_engine.process_stage2(buf.tobytes(), min_pixel_threshold=100000)
