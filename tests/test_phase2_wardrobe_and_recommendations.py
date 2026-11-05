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
_test_async_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)
_test_session_factory = async_sessionmaker(
    _test_async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(autouse=True)
async def setup_test_db(monkeypatch):
    """Set up in-memory SQLite tables and mock MinIO client."""
    async with _test_async_engine.begin() as conn:
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
        async with _test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session

    yield

    app.dependency_overrides.pop(get_db_session, None)
    async with _test_async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def test_dummy_wardrobe_manifest_structure():
    """Verify dummy wardrobes JSON manifest contains 5 users with 20 garments each."""
    manifest_path = "tests/dummy/dummy_wardrobes.json"
    assert os.path.exists(manifest_path), "tests/dummy/dummy_wardrobes.json must exist"

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["total_users"] == 5
    assert data["total_items"] == 100
    assert len(data["users"]) == 5

    for user in data["users"]:
        assert user["items_count"] == 20
        assert len(user["items"]) == 20

        slot_counts = {}
        for itm in user["items"]:
            assert "item_id" in itm
            assert "user_id" in itm
            assert "image_url" in itm
            assert "hints" in itm
            # Must be a real reachable GitHub URL, not example.com
            assert "example.com" not in itm["image_url"]
            assert itm["image_url"].startswith("https://raw.githubusercontent.com/alexeygrigorev/clothing-dataset-small/master/")

            slot = itm["hints"]["slot"]
            slot_counts[slot] = slot_counts.get(slot, 0) + 1

        assert slot_counts["top"] == 6
        assert slot_counts["bottom"] == 5
        assert slot_counts["one_piece"] == 2
        assert slot_counts["outerwear"] == 2
        assert slot_counts["footwear"] == 3
        assert slot_counts["accessory"] == 2


def test_url_to_images_converter():
    """Verify URL converter produces valid image bytes for real URLs and synthesizer fallback."""
    manifest_path = "tests/dummy/dummy_wardrobes.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    sample_real_url = data["users"][0]["items"][0]["image_url"]

    # Real URL download test
    real_img_bytes = convert_url_to_image_bytes(sample_real_url)
    assert isinstance(real_img_bytes, bytes)
    assert len(real_img_bytes) > 1000

    # Fallback test with synthetic generator
    synth_url = "https://dummyfashion.example.com/wardrobe/item.jpg?category=t-shirt&color=navy"
    synth_bytes = convert_url_to_image_bytes(synth_url)
    assert isinstance(synth_bytes, bytes)
    assert len(synth_bytes) > 200

    # Stream first 5 images from manifest
    stream = stream_dummy_wardrobe_images(manifest_path, target_user_id="user_001")
    first_five = [next(stream) for _ in range(5)]
    assert len(first_five) == 5
    for u_id, item_id, raw_bytes, item_meta in first_five:
        assert u_id == "user_001"
        assert item_id.startswith("item-user_001")
        assert len(raw_bytes) > 1000
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

    manifest_path = "tests/dummy/dummy_wardrobes.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    sample_url = data["users"][0]["items"][0]["image_url"]

    resp = client.post(
        f"/api/v1/users/{user_id}/wardrobe?sync_tag=true",
        json={"image_url": sample_url},
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

    manifest_path = "tests/dummy/dummy_wardrobes.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Ingest user_002's 20 items from manifest
    user_items = data["users"][1]["items"]
    for itm in user_items:
        r = client.post(
            f"/api/v1/users/{user_id}/wardrobe?sync_tag=true",
            json={"image_url": itm["image_url"]},
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
        # Verify no heavy wool or coats in hot weather
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
        # Cold weather should not contain shorts or sleeveless
        for slot, garment in outfit["items"].items():
            assert garment["category"] != "shorts", "Cold outfit should not contain shorts"
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
