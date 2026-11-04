import asyncio
import json
import logging
from typing import Optional, Dict, Any, Tuple
from urllib.parse import parse_qs, urlparse
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from fashion_pipeline.config.settings import settings
from fashion_pipeline.db.models import Job, WardrobeItem
from fashion_pipeline.db.session import async_session_factory
from fashion_pipeline.repositories.wardrobe_repository import map_category_to_slot
from fashion_pipeline.storage.minio_client import storage_client, MinIOClient
from fashion_pipeline.schemas.job import (
    ExecutionMode,
    JobStatus,
    ErrorReason,
    KafkaJobEvent,
)
from fashion_pipeline.ml.engine import FashionVisionEngine

logger = logging.getLogger(__name__)


class FashionGPUWorker:
    def __init__(
        self,
        engine: Optional[FashionVisionEngine] = None,
        minio_client: Optional[MinIOClient] = None,
        bootstrap_servers: Optional[str] = None,
    ):
        self.engine = engine or FashionVisionEngine()
        self.minio_client = minio_client or storage_client
        self.bootstrap_servers = bootstrap_servers or settings.KAFKA_BOOTSTRAP_SERVERS
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.producer: Optional[AIOKafkaProducer] = None
        self._running = False

    async def start(self) -> None:
        """Step A: Cold-Start Initialization and Step B: Kafka Consumer Setup."""
        logger.info("Initializing Fashion GPU Worker...")
        # Cold start ML models and text matrices
        self.engine.cold_start_init()

        # Initialize Kafka Producer (for DLQ)
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        await self.producer.start()

        # Initialize Kafka Consumer
        topics = [settings.KAFKA_TOPIC_STAGE1, settings.KAFKA_TOPIC_STAGE2]
        self.consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=self.bootstrap_servers,
            group_id=settings.KAFKA_GROUP_ID,
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )
        await self.consumer.start()
        self._running = True
        logger.info(f"Worker connected to Kafka on {self.bootstrap_servers}. Subscribed to {topics}")

        # Start event execution loop
        await self.run_loop()

    async def stop(self) -> None:
        self._running = False
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()
        logger.info("Fashion GPU Worker stopped gracefully.")

    async def run_loop(self) -> None:
        """Step B: Per-Event Execution Loop."""
        while self._running:
            try:
                msg = await self.consumer.getone()
                await self.process_kafka_message(msg)
                await self.consumer.commit()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in worker main loop: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def process_kafka_message(self, message: Any) -> None:
        """Parses event and executes Step B per-event execution."""
        event_dict = message.value
        logger.info(f"Received message from topic {message.topic}: {event_dict}")

        # Extract event fields (support both raw schema and MinIO s3 notification schema)
        job_id, bucket, object_key, mode = self._parse_event_payload(event_dict, message.topic)
        retry_count = event_dict.get("retry_count", 0)

        # Mark job as PROCESSING in PostgreSQL
        await self._update_job_status(job_id, JobStatus.PROCESSING)

        try:
            # 2. In-Memory Fetch from MinIO
            image_bytes = self.minio_client.download_bytes(bucket, object_key)

            # 3 & 4. Branching Execution & Batched Tagging
            if mode == ExecutionMode.STAGE_1:
                pieces = self.engine.process_stage1(image_bytes)
                crops = []
            elif mode == ExecutionMode.STAGE_2:
                pieces, crops = self.engine.process_stage2(image_bytes)
            else:
                raise ValueError(f"Unsupported execution mode: {mode}")

            # 5. State Persistence & Optional Crop Artifact Upload
            crops_bucket = settings.MINIO_CROPS_BUCKET
            for piece_id, crop_png in crops:
                crop_path = f"crops/{job_id}/{piece_id}.png"
                self.minio_client.upload_bytes(
                    crops_bucket,
                    crop_path,
                    crop_png,
                    content_type="image/png",
                )
                # Assign crop url
                crop_url = self.minio_client.generate_presigned_get_url(crops_bucket, crop_path)
                for p in pieces:
                    if p.piece_id == piece_id:
                        p.crop_url = crop_url

            # Write completed result JSON to PostgreSQL
            result_payload = [p.model_dump() for p in pieces]
            await self._update_job_status(
                job_id,
                JobStatus.COMPLETED,
                result=result_payload,
            )
            if mode == ExecutionMode.STAGE_1:
                await self._update_wardrobe_item_from_stage1(job_id, pieces)
            logger.info(f"Successfully processed job {job_id} with {len(pieces)} pieces.")

        except Exception as e:
            logger.error(f"Failed processing job {job_id}: {e}", exc_info=True)
            error_reason = self._classify_error(e)

            if retry_count < settings.MAX_RETRIES and error_reason not in (
                ErrorReason.NO_GARMENTS_DETECTED.value,
                ErrorReason.CORRUPTED_IMAGE.value,
            ):
                # Retry by re-publishing event with incremented retry count
                event_dict["retry_count"] = retry_count + 1
                topic = message.topic or settings.KAFKA_TOPIC_STAGE1
                if self.producer:
                    await self.producer.send_and_wait(topic, event_dict)
                logger.warning(f"Requeued job {job_id} for retry {retry_count + 1}/{settings.MAX_RETRIES}")
            else:
                # Mark as FAILED in PostgreSQL
                await self._update_job_status(
                    job_id,
                    JobStatus.FAILED,
                    error_reason=error_reason,
                )
                await self._fail_wardrobe_item_if_exists(job_id)
                # Send poison pill to Dead-Letter Queue (DLQ)
                event_dict["error_reason"] = error_reason
                if self.producer:
                    await self.producer.send_and_wait(settings.KAFKA_TOPIC_DLQ, event_dict)
                logger.warning(f"Routed failed job {job_id} to DLQ topic {settings.KAFKA_TOPIC_DLQ}")

    def _parse_event_payload(
        self,
        event_dict: Dict[str, Any],
        topic: str,
    ) -> Tuple[str, str, str, ExecutionMode]:
        """Supports direct KafkaJobEvent payload and MinIO S3 ObjectCreated notification structure."""
        if "Records" in event_dict:
            # Native MinIO bucket notification structure
            record = event_dict["Records"][0]
            s3_data = record["s3"]
            bucket = s3_data["bucket"]["name"]
            object_key = s3_data["object"]["key"]

            # Derive job_id and mode from object key (e.g. stage1/{job_id}.jpg or stage2/{job_id}.jpg)
            parts = object_key.split("/")
            mode_str = parts[0] if len(parts) > 1 else ("stage_2" if "stage2" in topic else "stage_1")
            filename = parts[-1]
            job_id = filename.split(".")[0]
            mode = ExecutionMode.STAGE_2 if "stage2" in mode_str or "stage2" in topic else ExecutionMode.STAGE_1
            return job_id, bucket, object_key, mode

        job_id = event_dict["job_id"]
        bucket = event_dict.get("bucket", settings.MINIO_RAW_BUCKET)
        object_key = event_dict.get("object_key", f"{job_id}.jpg")
        mode = ExecutionMode(event_dict.get("execution_mode", "stage_1"))
        return job_id, bucket, object_key, mode

    def _classify_error(self, exc: Exception) -> str:
        msg = str(exc)
        if "NO_GARMENTS_DETECTED" in msg:
            return ErrorReason.NO_GARMENTS_DETECTED.value
        elif "decode image bytes" in msg or "corrupted" in msg.lower():
            return ErrorReason.CORRUPTED_IMAGE.value
        elif "minio" in msg.lower() or "s3" in msg.lower():
            return ErrorReason.STORAGE_ERROR.value
        return ErrorReason.INFERENCE_ERROR.value

    async def _update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        result: Optional[Any] = None,
        error_reason: Optional[str] = None,
    ) -> None:
        """Updates PostgreSQL record status, triggering Postgres NOTIFY."""
        async with async_session_factory() as session:
            stmt = (
                update(Job)
                .where(Job.id == job_id)
                .values(
                    status=status.value,
                    result=result,
                    error_reason=error_reason,
                )
            )
            await session.execute(stmt)
            await session.commit()

    async def _update_wardrobe_item_from_stage1(
        self,
        job_id: str,
        pieces: list,
    ) -> None:
        """Update matching WardrobeItem when Stage 1 tagging completes."""
        if not pieces:
            return
        piece = pieces[0]
        tags = piece.tags
        category = tags.get("category").label if "category" in tags else None
        color = tags.get("color").label if "color" in tags else None
        fabric = tags.get("fabric").label if "fabric" in tags else None
        pattern = tags.get("pattern").label if "pattern" in tags else None
        neckline = tags.get("neckline").label if "neckline" in tags else None
        sleeve = tags.get("sleeve").label if "sleeve" in tags else None
        fit = tags.get("fit").label if "fit" in tags else None
        slot = map_category_to_slot(category)
        tags_json = {k: v.model_dump() for k, v in tags.items()}

        async with async_session_factory() as session:
            stmt = select(WardrobeItem).where(WardrobeItem.job_id == job_id)
            res = await session.execute(stmt)
            item = res.scalar_one_or_none()
            if item is not None:
                if item.source_url:
                    parsed = urlparse(item.source_url)
                    params = parse_qs(parsed.query)
                    if "category" in params:
                        category = params["category"][0]
                    if "color" in params:
                        color = params["color"][0]
                    if "fabric" in params:
                        fabric = params["fabric"][0]
                    if "pattern" in params:
                        pattern = params["pattern"][0]
                    if "neckline" in params:
                        neckline = params["neckline"][0]
                    if "sleeve" in params:
                        sleeve = params["sleeve"][0]
                    if "fit" in params:
                        fit = params["fit"][0]
                slot = map_category_to_slot(category)
                tags_json = {k: v.model_dump() for k, v in tags.items()}
                item.status = "READY"
                item.slot = slot
                item.category = category
                item.color = color
                item.fabric = fabric
                item.pattern = pattern
                item.neckline = neckline
                item.sleeve = sleeve
                item.fit = fit
                item.tags_json = tags_json
                await session.commit()
                logger.info(f"Updated WardrobeItem {item.item_id} to READY for job {job_id}")

    async def _fail_wardrobe_item_if_exists(self, job_id: str) -> None:
        """Mark matching WardrobeItem as FAILED when vision job fails."""
        async with async_session_factory() as session:
            stmt = select(WardrobeItem).where(WardrobeItem.job_id == job_id)
            res = await session.execute(stmt)
            item = res.scalar_one_or_none()
            if item is not None:
                item.status = "FAILED"
                await session.commit()
