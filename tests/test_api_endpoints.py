import pytest
import io
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool
from fashion_pipeline.api.main import app
from fashion_pipeline.db.models import Base, Job
from fashion_pipeline.db.session import get_db_session
from fashion_pipeline.storage.minio_client import storage_client

# In-memory SQLite async test engine with StaticPool
test_async_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)
test_session_factory = async_sessionmaker(test_async_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def setup_test_db():
    async with test_async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db_session():
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    yield
    app.dependency_overrides.pop(get_db_session, None)
    async with test_async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def test_healthz_endpoint():
    client = TestClient(app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "fashion-vision-api"}


def test_submit_job_without_file_presigned_url(monkeypatch):
    client = TestClient(app)

    # Mock MinIO generate presigned url
    monkeypatch.setattr(
        storage_client,
        "generate_presigned_put_url",
        lambda bucket_name, object_name: f"http://mock-minio/{bucket_name}/{object_name}",
    )

    resp = client.post("/api/v1/jobs?mode=stage_1")
    assert resp.status_code == 202
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "PENDING"
    assert data["mode"] == "stage_1"
    assert data["upload_url"].startswith("http://mock-minio/")
    assert data["stream_url"] == f"/api/v1/jobs/{data['job_id']}/stream"


def test_submit_job_with_file_upload(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        storage_client,
        "upload_bytes",
        lambda bucket_name, object_name, data, content_type: f"minio://{bucket_name}/{object_name}",
    )

    fake_img = io.BytesIO(b"fake-image-bytes")
    resp = client.post(
        "/api/v1/jobs?mode=stage_2",
        files={"file": ("test.jpg", fake_img, "image/jpeg")},
    )
    assert resp.status_code == 202
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "PENDING"
    assert data["mode"] == "stage_2"


def test_get_job_polling_completed():
    client = TestClient(app)

    # Insert a dummy completed job directly
    import asyncio
    async def insert_job():
        async with test_session_factory() as session:
            job = Job(
                id="job-test-123",
                mode="stage_1",
                status="COMPLETED",
                bucket="raw-images",
                object_key="stage1/job-test-123.jpg",
                result=[
                    {
                        "piece_id": "piece_0",
                        "label": "dress",
                        "pixel_count": 5000,
                        "bbox": {
                            "x_min": 10,
                            "y_min": 20,
                            "x_max": 100,
                            "y_max": 200,
                            "width": 90,
                            "height": 180,
                        },
                        "tags": {
                            "category": {"label": "dress", "confidence": 0.98},
                            "color": {"label": "red", "confidence": 0.95},
                        },
                        "crop_url": None,
                    }
                ],
            )
            session.add(job)
            await session.commit()

    asyncio.run(insert_job())

    resp = client.get("/api/v1/jobs/job-test-123")
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == "job-test-123"
    assert data["status"] == "COMPLETED"
    assert len(data["pieces"]) == 1
    assert data["pieces"][0]["label"] == "dress"
    assert data["pieces"][0]["tags"]["color"]["label"] == "red"
