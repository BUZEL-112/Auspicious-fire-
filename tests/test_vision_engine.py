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


def test_stage2_no_garments_detected_error(vision_engine):
    # Empty image where mock segformer finds 0 pixels above high threshold
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    _, buf = cv2.imencode(".jpg", img)

    with pytest.raises(ValueError, match="NO_GARMENTS_DETECTED"):
        vision_engine.process_stage2(buf.tobytes(), min_pixel_threshold=100000)
