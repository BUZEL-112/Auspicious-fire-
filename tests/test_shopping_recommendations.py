import json
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from fashion_pipeline.api.main import app
from fashion_pipeline.db.models import Base, User, WardrobeItem
from fashion_pipeline.db.session import get_db_session
from fashion_pipeline.repositories.store_repository import StoreRepository
from fashion_pipeline.schemas.context import (
    FormalityLevel,
    OccasionType,
    WeatherCondition,
)
from fashion_pipeline.storage.minio_client import storage_client

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
    """Initialize database tables and mock object storage for testing."""
    async with _test_async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Mock MinIO storage operations
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


def test_get_store_items_catalog():
    """Verify GET /api/v1/store/items returns valid curated catalog items."""
    client = TestClient(app)
    resp = client.get("/api/v1/store/items")
    assert resp.status_code == 200

    items = resp.json()
    assert 24 <= len(items) <= 30

    slots_present = set()
    for item in items:
        assert item["sku_id"].startswith("sku-")
        assert len(item["name"]) > 0
        assert item["price_usd"] > 0
        assert item["product_url"].startswith("http")
        assert item["image_url"].startswith("https://raw.githubusercontent.com/alexeygrigorev/clothing-dataset-small/master/")
        assert "example.com" not in item["image_url"]
        assert item["slot"] in {"top", "bottom", "one_piece", "outerwear", "footwear", "accessory"}
        assert len(item["tags"]) > 0
        slots_present.add(item["slot"])

    assert slots_present == {"top", "bottom", "one_piece", "outerwear", "footwear", "accessory"}

    # Test filtering by slot
    resp_outerwear = client.get("/api/v1/store/items?slot=outerwear")
    assert resp_outerwear.status_code == 200
    outerwear_items = resp_outerwear.json()
    assert len(outerwear_items) > 0
    for itm in outerwear_items:
        assert itm["slot"] == "outerwear"


@pytest.mark.asyncio
async def test_shopping_recommendations_missing_slot_unlock():
    """Verify shopping recommendations detect missing outerwear in cold weather and unlock outfits."""
    user_id = "user_partial_wardrobe"

    # Pre-populate partial wardrobe: tops, bottoms, and shoes, with zero outerwear
    async with _test_session_factory() as session:
        user = User(user_id=user_id, display_name="Partial User")
        session.add(user)

        garments = [
            WardrobeItem(
                item_id=f"item-{user_id}-top-1",
                user_id=user_id,
                bucket="raw-images",
                object_key=f"users/{user_id}/items/top1.jpg",
                status="READY",
                slot="top",
                category="shirt",
                color="white",
                fabric="cotton",
                pattern="solid",
                fit="regular fit",
                sleeve="long sleeve",
                neckline="collar",
                tags_json={"category": {"label": "shirt", "confidence": 0.99}},
            ),
            WardrobeItem(
                item_id=f"item-{user_id}-top-2",
                user_id=user_id,
                bucket="raw-images",
                object_key=f"users/{user_id}/items/top2.jpg",
                status="READY",
                slot="top",
                category="sweater",
                color="navy",
                fabric="wool",
                pattern="solid",
                fit="regular fit",
                sleeve="long sleeve",
                neckline="crew neck",
                tags_json={"category": {"label": "sweater", "confidence": 0.99}},
            ),
            WardrobeItem(
                item_id=f"item-{user_id}-btm-1",
                user_id=user_id,
                bucket="raw-images",
                object_key=f"users/{user_id}/items/btm1.jpg",
                status="READY",
                slot="bottom",
                category="pants",
                color="grey",
                fabric="wool",
                pattern="solid",
                fit="slim fit",
                tags_json={"category": {"label": "pants", "confidence": 0.99}},
            ),
            WardrobeItem(
                item_id=f"item-{user_id}-btm-2",
                user_id=user_id,
                bucket="raw-images",
                object_key=f"users/{user_id}/items/btm2.jpg",
                status="READY",
                slot="bottom",
                category="jeans",
                color="navy",
                fabric="denim",
                pattern="solid",
                fit="regular fit",
                tags_json={"category": {"label": "jeans", "confidence": 0.99}},
            ),
            WardrobeItem(
                item_id=f"item-{user_id}-fw-1",
                user_id=user_id,
                bucket="raw-images",
                object_key=f"users/{user_id}/items/fw1.jpg",
                status="READY",
                slot="footwear",
                category="shoes",
                color="black",
                fabric="leather",
                pattern="solid",
                fit="regular fit",
                tags_json={"category": {"label": "shoes", "confidence": 0.99}},
            ),
        ]
        session.add_all(garments)
        await session.commit()

    client = TestClient(app)

    # Request recommendations for work office in cold weather
    req_body = {
        "occasion": OccasionType.WORK_OFFICE.value,
        "weather": WeatherCondition.COLD.value,
        "formality": FormalityLevel.BUSINESS_CASUAL.value,
    }
    resp = client.post(
        f"/api/v1/users/{user_id}/shopping/recommendations?top_k=5",
        json=req_body,
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["user_id"] == user_id
    assert "outerwear" in data["missing_slots"]

    recommendations = data["recommendations"]
    assert len(recommendations) > 0

    # Top recommendation must fill the missing outerwear gap
    top_rec = recommendations[0]
    assert top_rec["is_missing_slot_gap"] is True
    assert top_rec["store_item"]["slot"] == "outerwear"
    assert top_rec["unlocked_outfits_count"] > 0
    assert top_rec["best_outfit_score"] >= 65.0
    assert len(top_rec["sample_unlocked_outfits"]) > 0

    # Verify sample unlocked outfits include the store item
    shop_item_id = f"shop-{top_rec['store_item']['sku_id']}"
    sample_outfit = top_rec["sample_unlocked_outfits"][0]
    outfit_item_ids = [item["item_id"] for item in sample_outfit["items"].values()]
    assert shop_item_id in outfit_item_ids


def test_shopping_one_click_add_to_wardrobe():
    """Verify POST /api/v1/users/{user_id}/wardrobe/from-store/{sku_id} adds item to user wardrobe."""
    client = TestClient(app)
    user_id = "user_buyer_001"
    sku_id = "sku-outerwear-001"

    # Add store item to user wardrobe
    resp = client.post(f"/api/v1/users/{user_id}/wardrobe/from-store/{sku_id}")
    assert resp.status_code == 201

    item_data = resp.json()
    assert item_data["user_id"] == user_id
    assert item_data["item_id"].startswith("item-")
    assert item_data["job_id"].startswith("job-")
    assert item_data["status"] == "READY"
    assert item_data["slot"] == "outerwear"
    assert item_data["category"] == "blazer"
    assert item_data["color"] == "navy"
    assert item_data["fabric"] == "wool"
    assert "alexeygrigorev/clothing-dataset-small" in item_data["source_url"]

    # Verify GET /api/v1/users/{user_id}/wardrobe returns the newly added item
    get_resp = client.get(f"/api/v1/users/{user_id}/wardrobe")
    assert get_resp.status_code == 200
    wardrobe_data = get_resp.json()
    assert wardrobe_data["total_items"] == 1
    assert wardrobe_data["items"][0]["item_id"] == item_data["item_id"]
    assert wardrobe_data["items"][0]["status"] == "READY"


def test_shopping_add_invalid_sku_returns_404():
    """Verify purchasing a non-existent SKU returns 404 Not Found."""
    client = TestClient(app)
    user_id = "user_buyer_002"
    resp = client.post(f"/api/v1/users/{user_id}/wardrobe/from-store/nonexistent-sku-999")
    assert resp.status_code == 404
    assert "was not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_shopping_recommendations_skips_already_owned_items():
    """Verify store items identical to owned garments are not recommended."""
    user_id = "user_blazer_owner"

    # User already owns the exact same navy wool blazer
    async with _test_session_factory() as session:
        user = User(user_id=user_id, display_name="Blazer Owner")
        session.add(user)
        owned_blazer = WardrobeItem(
            item_id=f"item-{user_id}-blazer",
            user_id=user_id,
            bucket="raw-images",
            object_key=f"users/{user_id}/items/blazer.jpg",
            status="READY",
            slot="outerwear",
            category="blazer",
            color="navy",
            fabric="wool",
            pattern="solid",
            fit="regular fit",
            tags_json={"category": {"label": "blazer", "confidence": 0.99}},
        )
        session.add(owned_blazer)
        await session.commit()

    client = TestClient(app)
    req_body = {
        "occasion": OccasionType.WORK_OFFICE.value,
        "weather": WeatherCondition.COLD.value,
    }
    resp = client.post(
        f"/api/v1/users/{user_id}/shopping/recommendations?top_k=20",
        json=req_body,
    )
    assert resp.status_code == 200
    recommended_skus = [r["store_item"]["sku_id"] for r in resp.json()["recommendations"]]
    assert "sku-outerwear-001" not in recommended_skus


def test_store_repository_direct():
    """Verify StoreRepository methods operate correctly."""
    repo = StoreRepository()
    all_items = repo.list_items()
    assert len(all_items) >= 24

    top_items = repo.list_items(slot="top")
    assert len(top_items) > 0
    assert all(itm["slot"] == "top" for itm in top_items)

    blazer = repo.get_by_sku("sku-outerwear-001")
    assert blazer is not None
    assert blazer["category"] == "blazer"

    missing = repo.get_by_sku("does-not-exist")
    assert missing is None
