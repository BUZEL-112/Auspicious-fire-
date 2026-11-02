import uuid
from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fashion_pipeline.config.settings import settings
from fashion_pipeline.db.models import Job
from fashion_pipeline.db.session import get_db_session
from fashion_pipeline.storage.minio_client import storage_client
from fashion_pipeline.api.kafka_producer import kafka_service
from fashion_pipeline.api.notifications import listen_for_job_notification
from fashion_pipeline.schemas.job import (
    ExecutionMode,
    JobStatus,
    JobCreateResponse,
    JobResultResponse,
    PieceResult,
)

router = APIRouter(prefix="/api/v1", tags=["Jobs & Ingestion"])


@router.post(
    "/jobs",
    response_model=JobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Non-blocking job submission with multipart file or presigned URL generation",
)
async def submit_job(
    mode: ExecutionMode = Query(ExecutionMode.STAGE_1, description="Execution mode: stage_1 or stage_2"),
    file: Optional[UploadFile] = File(None, description="Optional raw image file"),
    db: AsyncSession = Depends(get_db_session),
):
    """Clients interact with the system using a Non-Blocking Submit pattern.
    - Input: Multipart image file (or request for a MinIO Presigned PUT URL) + mode
    - Immediate Output (<30ms): Returns {"job_id": "...", "status": "PENDING", "stream_url": "..."}
    """
    job_id = f"job-{uuid.uuid4().hex[:12]}"
    bucket = settings.MINIO_RAW_BUCKET
    object_key = f"{mode.value}/{job_id}.jpg"
    stream_url = f"/api/v1/jobs/{job_id}/stream"

    presigned_upload_url = None

    if file is not None:
        # Read uploaded image bytes directly
        content = await file.read()
        storage_client.upload_bytes(
            bucket_name=bucket,
            object_name=object_key,
            data=content,
            content_type=file.content_type or "image/jpeg",
        )
    else:
        # Generate presigned PUT URL for client-direct MinIO upload
        presigned_upload_url = storage_client.generate_presigned_put_url(
            bucket_name=bucket,
            object_name=object_key,
        )

    # Create job in database (status = PENDING)
    new_job = Job(
        id=job_id,
        mode=mode.value,
        status=JobStatus.PENDING.value,
        bucket=bucket,
        object_key=object_key,
    )
    db.add(new_job)
    await db.commit()

    # If file was directly uploaded, emit event to Kafka topic
    # (When using MinIO Presigned PUT, MinIO natively emits s3:ObjectCreated:Put to Kafka)
    if file is not None:
        topic = (
            settings.KAFKA_TOPIC_STAGE2
            if mode == ExecutionMode.STAGE_2
            else settings.KAFKA_TOPIC_STAGE1
        )
        event_payload = {
            "job_id": job_id,
            "bucket": bucket,
            "object_key": object_key,
            "execution_mode": mode.value,
            "retry_count": 0,
        }
        await kafka_service.publish_event(topic, event_payload)

    return JobCreateResponse(
        job_id=job_id,
        status=JobStatus.PENDING,
        stream_url=stream_url,
        mode=mode,
        upload_url=presigned_upload_url,
    )


@router.post(
    "/analyze",
    response_model=JobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Alias ingestion endpoint: POST /api/v1/analyze?mode=stage_1",
)
async def analyze_garment(
    mode: ExecutionMode = Query(ExecutionMode.STAGE_1),
    file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db_session),
):
    return await submit_job(mode=mode, file=file, db=db)


@router.get(
    "/jobs/{job_id}",
    response_model=JobResultResponse,
    summary="Preview / MVP Polling: Polls job status and result",
)
async def get_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Preview / MVP Polling:
    Client polls every 500ms-1s.
    Returns status: PROCESSING/PENDING until completed, then COMPLETED with full JSON payload.
    """
    stmt = select(Job).where(Job.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found")

    pieces = None
    if job.result:
        pieces = [PieceResult(**p) for p in job.result]

    return JobResultResponse(
        job_id=job.id,
        status=JobStatus(job.status),
        mode=ExecutionMode(job.mode),
        error_reason=job.error_reason,
        pieces=pieces,
        created_at=job.created_at.isoformat() if job.created_at else "",
        updated_at=job.updated_at.isoformat() if job.updated_at else "",
    )


@router.get(
    "/jobs/{job_id}/stream",
    summary="Production Real-Time Push: SSE connection with Postgres NOTIFY trigger",
)
async def stream_job_updates(
    job_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Production Real-Time Push:
    Client opens a Server-Sent Events (SSE) connection.
    When the worker updates PostgreSQL, a Postgres NOTIFY trigger alerts FastAPI,
    which pushes the final JSON down the open SSE pipe and closes the connection.
    """
    # Verify job exists
    stmt = select(Job).where(Job.id == job_id)
    res = await db.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found")

    return StreamingResponse(
        listen_for_job_notification(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        },
    )
