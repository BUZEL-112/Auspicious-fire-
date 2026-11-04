import json
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from fashion_pipeline.api.main import app
from fashion_pipeline.db.models import Base, User, WardrobeItem
from fashion_pipeline.db.session import get_db_session
from fashion_pipeline.schemas.context import (
    FormalityLevel,
    OccasionType,
    StyleMood,
    WeatherCondition,
)
from fashion_pipeline.storage.minio_client import storage_client
from fashion_pipeline.ml.image_ops import decode_image_bytes
from sqlalchemy.pool import StaticPool
from tests.dummy.url_to_images import (
    convert_url_to_image_bytes,
    stream_dummy_wardrobe_images,
)

# In-memory SQLite async test engine with StaticPool
test_async_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)
test_session_factory = async_sessionmaker(
    test_async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(autouse=True)
async def setup_test_db(monkeypatch):
    """Set up in-memory SQLite tables and mock MinIO client."""
    async with test_async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Mock MinIO methods
    monkeypatch.setattr(
        storage_client,
        "upload_bytes",
        lambda bucket_name, object_name, data, content_type="image/jpeg": f"minio://{bucket_name}/{object_name}",
    )
    monkeypatch.setattr(
        storage_client,
        "generate_presigned_put_url",
        lambda bucket_name, object_name: f"http://mock-minio/{bucket_name}/{object_name}",
    )
    monkeypatch.setattr(
        storage_client,
        "generate_presigned_get_url",
        lambda bucket_name, object_name: f"http://mock-minio/{bucket_name}/{object_name}",
    )

    async def override_get_db_session():
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session

    yield

    app.dependency_overrides.pop(get_db_session, None)
    async with test_async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def test_dummy_wardrobe_manifest_structure():
    """Verify dummy wardrobes JSON manifest contains 10 users with 60 garments each."""
    manifest_path = "tests/dummy/dummy_wardrobes.json"
    assert os.path.exists(manifest_path), "tests/dummy/dummy_wardrobes.json must exist"

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["total_users"] == 10
    assert data["total_items"] == 600
    assert len(data["users"]) == 10

    for user in data["users"]:
        assert user["items_count"] == 60
        assert len(user["items"]) == 60

        slot_counts = {}
        for itm in user["items"]:
            assert "item_id" in itm
            assert "user_id" in itm
            assert "image_url" in itm
            assert "hints" in itm
            slot = itm["hints"]["slot"]
            slot_counts[slot] = slot_counts.get(slot, 0) + 1

        assert slot_counts["top"] == 20
        assert slot_counts["bottom"] == 14
        assert slot_counts["one_piece"] == 4
        assert slot_counts["outerwear"] == 6
        assert slot_counts["footwear"] == 10
        assert slot_counts["accessory"] == 6


def test_url_to_images_converter():
    """Verify URL converter produces valid image bytes with synthesizer fallback."""
    test_url = "https://dummyfashion.example.com/wardrobe/user_001/top_001.jpg?category=t-shirt&color=navy"
    img_bytes = convert_url_to_image_bytes(test_url)
    assert isinstance(img_bytes, bytes)
    assert len(img_bytes) > 200

    # Stream first 5 images from manifest
    manifest_path = "tests/dummy/dummy_wardrobes.json"
    stream = stream_dummy_wardrobe_images(manifest_path, target_user_id="user_001")
    first_five = [next(stream) for _ in range(5)]
    assert len(first_five) == 5
    for u_id, item_id, raw_bytes, item_meta in first_five:
        assert u_id == "user_001"
        assert item_id.startswith("item-user_001")
        assert len(raw_bytes) > 200
        assert "hints" in item_meta


def test_context_questionnaire_endpoint():
    """Verify GET /api/v1/context/questions returns the 5 context questions."""
    client = TestClient(app)
    resp = client.get("/api/v1/context/questions")
    assert resp.status_code == 200

    data = resp.json()
    assert "questions" in data
    assert len(data["questions"]) == 5

    question_ids = [q["id"] for q in data["questions"]]
    assert "occasion" in question_ids
    assert "formality" in question_ids
    assert "weather" in question_ids
    assert "time_setting" in question_ids
    assert "style_mood" in question_ids

    # Check occasion question options
    occasion_q = next(q for q in data["questions"] if q["id"] == "occasion")
    assert len(occasion_q["options"]) >= 6
    opt_ids = [opt["id"] for opt in occasion_q["options"]]
    assert "work_office" in opt_ids
    assert "casual_daily" in opt_ids


def test_user_wardrobe_ingestion_and_key_mapping():
    """Verify POST /api/v1/users/{user_id}/wardrobe ingests single garment and creates key map."""
    client = TestClient(app)
    user_id = "user_001"

    # Ingest garment via URL with sync_tag=true
    url = (
        "https://dummyfashion.example.com/wardrobe/user_001/top_001.jpg"
        "?category=t-shirt&color=black&fabric=cotton&pattern=solid&fit=regular+fit"
    )
    resp = client.post(
        f"/api/v1/users/{user_id}/wardrobe?sync_tag=true",
        json={"image_url": url},
    )
    assert resp.status_code == 201
    item_data = resp.json()

    assert item_data["user_id"] == user_id
    assert item_data["item_id"].startswith("item-")
    assert item_data["job_id"].startswith("job-")
    assert item_data["object_key"] == f"users/{user_id}/items/{item_data['item_id']}.jpg"
    assert item_data["status"] == "READY"
    assert item_data["slot"] == "top"
    assert item_data["category"] is not None
    assert item_data["tags_json"] is not None

    # Test list endpoint
    list_resp = client.get(f"/api/v1/users/{user_id}/wardrobe")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["user_id"] == user_id
    assert list_data["total_items"] == 1
    assert list_data["items"][0]["item_id"] == item_data["item_id"]


def test_recommendations_with_context_filtering():
    """Verify heuristic engine filters items and returns ranked outfits across contexts."""
    client = TestClient(app)
    user_id = "user_002"

    # Seed user_002 with representative items across slots
    items_to_seed = [
        # Tops
        ("t-shirt", "white", "cotton", "solid", "short sleeve", "crew neck", "regular fit"),
        ("shirt", "navy", "cotton", "solid", "long sleeve", "collar", "slim fit"),
        ("sweater", "black", "wool", "solid", "long sleeve", "turtleneck", "regular fit"),
        ("top", "red", "linen", "solid", "sleeveless", "scoop neck", "regular fit"),
        # Bottoms
        ("jeans", "blue", "denim", "solid", None, None, "regular fit"),
        ("pants", "black", "wool", "solid", None, None, "regular fit"),
        ("shorts", "beige", "cotton", "solid", None, None, "regular fit"),
        # One piece
        ("dress", "black", "silk", "solid", "sleeveless", "v-neck", "slim fit"),
        # Outerwear
        ("blazer", "navy", "wool", "solid", "long sleeve", "collar", "regular fit"),
        ("coat", "brown", "wool", "solid", "long sleeve", "collar", "oversized"),
        # Footwear
        ("sneakers", "white", "cotton", "solid", None, None, "regular fit"),
        ("shoes", "black", "leather", "solid", None, None, "regular fit"),
        ("sandals", "beige", "leather", "solid", None, None, "regular fit"),
        ("boots", "black", "leather", "solid", None, None, "regular fit"),
    ]

    for cat, col, fab, pat, slv, nck, fit in items_to_seed:
        params = f"category={cat}&color={col}&fabric={fab}&pattern={pat}&fit={fit}"
        if slv:
            params += f"&sleeve={slv}"
        if nck:
            params += f"&neckline={nck}"
        url = f"https://dummyfashion.example.com/wardrobe/{user_id}/item.jpg?{params}"
        r = client.post(
            f"/api/v1/users/{user_id}/wardrobe?sync_tag=true",
            json={"image_url": url},
        )
        assert r.status_code == 201

    # 1. Context: Casual Daily + Hot
    hot_req = {
        "occasion": OccasionType.CASUAL_DAILY.value,
        "weather": WeatherCondition.HOT.value,
        "style_mood": StyleMood.CLEAN_MINIMALIST.value,
    }
    resp_hot = client.post(f"/api/v1/users/{user_id}/recommendations", json=hot_req)
    assert resp_hot.status_code == 200
    hot_data = resp_hot.json()
    assert len(hot_data["outfits"]) > 0

    for outfit in hot_data["outfits"]:
        # Verify no heavy wool sweater or coat in hot weather
        for slot, garment in outfit["items"].items():
            assert garment["fabric"] != "wool", f"Hot outfit should not contain wool: {garment}"
            assert garment["category"] != "coat", "Hot outfit should not contain coat"
            assert garment["category"] != "boots", "Hot outfit should not contain boots"

    # 2. Context: Work & Office + Cold
    cold_req = {
        "occasion": OccasionType.WORK_OFFICE.value,
        "weather": WeatherCondition.COLD.value,
        "formality": FormalityLevel.BUSINESS_CASUAL.value,
    }
    resp_cold = client.post(f"/api/v1/users/{user_id}/recommendations", json=cold_req)
    assert resp_cold.status_code == 200
    cold_data = resp_cold.json()
    assert len(cold_data["outfits"]) > 0

    for outfit in cold_data["outfits"]:
        # Cold weather should not contain shorts or sandals
        for slot, garment in outfit["items"].items():
            assert garment["category"] != "shorts", "Cold outfit should not contain shorts"
            assert garment["category"] != "sandals", "Cold outfit should not contain sandals"
            assert garment["sleeve"] != "sleeveless", "Cold outfit should not contain sleeveless item"

    # 3. Context: Formal Event (Business Formal)
    formal_req = {
        "occasion": OccasionType.FORMAL_EVENT.value,
        "formality": FormalityLevel.BUSINESS_FORMAL.value,
    }
    resp_formal = client.post(f"/api/v1/users/{user_id}/recommendations", json=formal_req)
    assert resp_formal.status_code == 200
    formal_data = resp_formal.json()
    assert len(formal_data["outfits"]) > 0

    for outfit in formal_data["outfits"]:
        # Formal event should not contain sneakers or shorts
        for slot, garment in outfit["items"].items():
            assert garment["category"] != "sneakers", "Formal outfit should not contain sneakers"
            assert garment["category"] != "shorts", "Formal outfit should not contain shorts"

    # 4. Context: Workout & Active
    workout_req = {
        "occasion": OccasionType.WORKOUT_ACTIVE.value,
    }
    resp_workout = client.post(f"/api/v1/users/{user_id}/recommendations", json=workout_req)
    assert resp_workout.status_code == 200
    workout_data = resp_workout.json()
    assert len(workout_data["outfits"]) > 0

    for outfit in workout_data["outfits"]:
        # Workout should not contain blazer, dress, or boots
        for slot, garment in outfit["items"].items():
            assert garment["category"] not in {"blazer", "dress", "boots"}


def test_recommendations_no_wardrobe_returns_404():
    """Verify requesting recommendations for a user with no READY items returns 404."""
    client = TestClient(app)
    resp = client.post(
        "/api/v1/users/non_existent_user/recommendations",
        json={"occasion": "casual_daily"},
    )
    assert resp.status_code == 404
    assert "No READY wardrobe items found" in resp.json()["detail"]
