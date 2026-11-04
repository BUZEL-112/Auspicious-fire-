from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # API
    API_PORT: int = 8000
    API_HOST: str = "0.0.0.0"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://fashion_user:fashion_pass@localhost:5432/fashion_db"

    # MinIO
    MINIO_ENDPOINT: str = "localhost:9020"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    MINIO_RAW_BUCKET: str = "raw-images"
    MINIO_CROPS_BUCKET: str = "crops"

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_TOPIC_STAGE1: str = "fashion.jobs.stage1"
    KAFKA_TOPIC_STAGE2: str = "fashion.jobs.stage2"
    KAFKA_TOPIC_DLQ: str = "fashion.jobs.dlq"
    KAFKA_GROUP_ID: str = "fashion-gpu-workers"

    # ML & Inference
    DEVICE: str = "cuda"  # fallback to 'cpu' if cuda unavailable
    TAXONOMY_PATH: str = "data/deepfashion_taxonomy.json"
    MIN_MASK_PIXELS: int = 500
    MAX_RETRIES: int = 3
    YOLO_MODEL_PATH: str = "yolov8n.pt"
    SAM_CHECKPOINT_PATH: str = "sam_vit_b_01ec64.pth"
    SAM_MODEL_TYPE: str = "vit_b"
    ENABLE_PERSON_DETECTION: bool = True
    ENABLE_LAYER_SPLITTING: bool = True


settings = Settings()
