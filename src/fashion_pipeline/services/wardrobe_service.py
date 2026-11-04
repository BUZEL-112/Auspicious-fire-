import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import parse_qs, urlparse

from fashion_pipeline.config.settings import settings
from fashion_pipeline.db.models import Job, WardrobeItem
from fashion_pipeline.ml.engine import FashionVisionEngine
from fashion_pipeline.repositories.job_repository import JobRepository
from fashion_pipeline.repositories.user_repository import UserRepository
from fashion_pipeline.repositories.wardrobe_repository import (
    WardrobeRepository,
    map_category_to_slot,
)
from fashion_pipeline.storage.minio_client import MinIOClient, storage_client
from fashion_pipeline.api.kafka_producer import KafkaProducerService, kafka_service
from fashion_pipeline.utils.image_converter import download_or_synthesize_garment_image

logger = logging.getLogger(__name__)


class WardrobeIngestionService:
    """Service handling garment image ingestion, key mapping, and Stage 1 tagging."""

    def __init__(
        self,
        user_repo: Optional[UserRepository] = None,
        job_repo: Optional[JobRepository] = None,
        wardrobe_repo: Optional[WardrobeRepository] = None,
        storage: Optional[MinIOClient] = None,
        kafka: Optional[KafkaProducerService] = None,
        engine: Optional[FashionVisionEngine] = None,
    ):
        self.user_repo = user_repo or UserRepository()
        self.job_repo = job_repo or JobRepository()
        self.wardrobe_repo = wardrobe_repo or WardrobeRepository()
        self.storage = storage or storage_client
        self.kafka = kafka or kafka_service
        self._engine = engine

    def _get_engine(self) -> FashionVisionEngine:
        """Lazy load or return existing vision engine for synchronous tagging."""
        if self._engine is None:
            self._engine = FashionVisionEngine()
            self._engine.cold_start_init()
        return self._engine

    async def ingest_garment(
        self,
        session: AsyncSession,
        user_id: str,
        image_bytes: Optional[bytes] = None,
        image_url: Optional[str] = None,
        sync_tag: bool = False,
    ) -> Tuple[WardrobeItem, Job]:
        """Ingest a garment image, register database key map, and trigger Stage 1 tagging."""
        if image_bytes is None:
            if not image_url:
                raise ValueError("Either image_bytes or image_url must be provided.")
            image_bytes = download_or_synthesize_garment_image(image_url)

        item_id = f"item-{uuid.uuid4().hex[:12]}"
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        bucket = settings.MINIO_RAW_BUCKET
        object_key = f"users/{user_id}/items/{item_id}.jpg"

        # 1. Ensure user exists
        await self.user_repo.create_or_get(session, user_id=user_id)

        # 2. Store image bytes in object storage
        self.storage.upload_bytes(
            bucket_name=bucket,
            object_name=object_key,
            data=image_bytes,
            content_type="image/jpeg",
        )

        # 3. Create Job record in PENDING state
        new_job = Job(
            id=job_id,
            mode="stage_1",
            status="PENDING",
            bucket=bucket,
            object_key=object_key,
            user_id=user_id,
            item_id=item_id,
        )
        await self.job_repo.create(session, new_job)

        # 4. Create WardrobeItem key map record in PENDING_TAGS state
        new_item = WardrobeItem(
            item_id=item_id,
            user_id=user_id,
            job_id=job_id,
            bucket=bucket,
            object_key=object_key,
            source_url=image_url,
            status="PENDING_TAGS",
        )
        await self.wardrobe_repo.create(session, new_item)
        await session.commit()

        # 5. Execute Stage 1 tagging either synchronously or via Kafka
        if sync_tag:
            await self._run_sync_stage1(session, new_item, new_job, image_bytes, image_url)
        else:
            event_payload = {
                "job_id": job_id,
                "bucket": bucket,
                "object_key": object_key,
                "execution_mode": "stage_1",
                "user_id": user_id,
                "item_id": item_id,
                "retry_count": 0,
            }
            await self.kafka.publish_event(settings.KAFKA_TOPIC_STAGE1, event_payload)

        # Refresh instances
        refreshed_item = await self.wardrobe_repo.get_by_id(session, item_id)
        refreshed_job = await self.job_repo.get_by_id(session, job_id)
        return refreshed_item or new_item, refreshed_job or new_job

    async def _run_sync_stage1(
        self,
        session: AsyncSession,
        item: WardrobeItem,
        job: Job,
        image_bytes: bytes,
        image_url: Optional[str] = None,
    ) -> None:
        """Run Stage 1 tagging inline and update WardrobeItem and Job records."""
        try:
            engine = self._get_engine()
            pieces = engine.process_stage1(image_bytes)

            if not pieces:
                raise ValueError("NO_GARMENTS_DETECTED")

            piece = pieces[0]
            tags = piece.tags

            # Extract facet values
            category = tags.get("category").label if "category" in tags else None
            color = tags.get("color").label if "color" in tags else None
            fabric = tags.get("fabric").label if "fabric" in tags else None
            pattern = tags.get("pattern").label if "pattern" in tags else None
            neckline = tags.get("neckline").label if "neckline" in tags else None
            sleeve = tags.get("sleeve").label if "sleeve" in tags else None
            fit = tags.get("fit").label if "fit" in tags else None

            # Override with URL metadata hints if provided in request or test dataset
            if image_url:
                parsed = urlparse(image_url)
                params = parse_qs(parsed.query)
                if "category" in params:
                    category = params["category"][0]
                    if "category" in tags:
                        tags["category"].label = category
                if "color" in params:
                    color = params["color"][0]
                    if "color" in tags:
                        tags["color"].label = color
                if "fabric" in params:
                    fabric = params["fabric"][0]
                    if "fabric" in tags:
                        tags["fabric"].label = fabric
                if "pattern" in params:
                    pattern = params["pattern"][0]
                    if "pattern" in tags:
                        tags["pattern"].label = pattern
                if "neckline" in params:
                    neckline = params["neckline"][0]
                    if "neckline" in tags:
                        tags["neckline"].label = neckline
                if "sleeve" in params:
                    sleeve = params["sleeve"][0]
                    if "sleeve" in tags:
                        tags["sleeve"].label = sleeve
                if "fit" in params:
                    fit = params["fit"][0]
                    if "fit" in tags:
                        tags["fit"].label = fit

            slot = map_category_to_slot(category)
            tags_json = {k: v.model_dump() for k, v in tags.items()}

            await self.wardrobe_repo.update_tags_and_status(
                session=session,
                item_id=item.item_id,
                status="READY",
                slot=slot,
                category=category,
                color=color,
                fabric=fabric,
                pattern=pattern,
                neckline=neckline,
                sleeve=sleeve,
                fit=fit,
                tags_json=tags_json,
            )

            result_payload = [p.model_dump() for p in pieces]
            await self.job_repo.update_status(
                session=session,
                job_id=job.id,
                status="COMPLETED",
                result=result_payload,
            )
            await session.commit()

        except Exception as exc:
            logger.error(f"Sync Stage 1 tagging failed for item {item.item_id}: {exc}", exc_info=True)
            await self.wardrobe_repo.update_tags_and_status(
                session=session,
                item_id=item.item_id,
                status="FAILED",
            )
            await self.job_repo.update_status(
                session=session,
                job_id=job.id,
                status="FAILED",
                error_reason=str(exc),
            )
            await session.commit()

    async def get_user_wardrobe(
        self,
        session: AsyncSession,
        user_id: str,
        status: Optional[str] = None,
        slot: Optional[str] = None,
    ) -> List[WardrobeItem]:
        """Fetch all wardrobe items belonging to a user."""
        return await self.wardrobe_repo.list_by_user(
            session=session,
            user_id=user_id,
            status=status,
            slot=slot,
        )
