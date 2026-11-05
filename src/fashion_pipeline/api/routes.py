import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fashion_pipeline.config.settings import settings
from fashion_pipeline.db.models import Job, WardrobeItem
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
from fashion_pipeline.schemas.context import (
    ContextQuestionnaireResponse,
    DressingContextRequest,
)
from fashion_pipeline.schemas.wardrobe import (
    RecommendationResponse,
    UserWardrobeListResponse,
    WardrobeItemResponse,
)
from fashion_pipeline.schemas.shopping import (
    ShoppingRecommendationResponse,
    StoreItemResponse,
)
from fashion_pipeline.repositories.user_repository import UserRepository
from fashion_pipeline.services.context_service import ContextGatheringService
from fashion_pipeline.services.recommendation_service import RecommendationService
from fashion_pipeline.services.shopping_service import ShoppingService
from fashion_pipeline.services.wardrobe_service import WardrobeIngestionService

router = APIRouter(prefix="/api/v1", tags=["Jobs & Ingestion"])


def to_wardrobe_item_response(item: WardrobeItem) -> WardrobeItemResponse:
    """Map database WardrobeItem entity to API response schema."""
    return WardrobeItemResponse(
        item_id=item.item_id,
        user_id=item.user_id,
        job_id=item.job_id,
        bucket=item.bucket,
        object_key=item.object_key,
        source_url=item.source_url,
        status=item.status,
        slot=item.slot,
        category=item.category,
        color=item.color,
        fabric=item.fabric,
        pattern=item.pattern,
        neckline=item.neckline,
        sleeve=item.sleeve,
        fit=item.fit,
        tags_json=item.tags_json,
        created_at=item.created_at.isoformat() if item.created_at else "",
        updated_at=item.updated_at.isoformat() if item.updated_at else "",
    )


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
        content = await file.read()
        storage_client.upload_bytes(
            bucket_name=bucket,
            object_name=object_key,
            data=content,
            content_type=file.content_type or "image/jpeg",
        )
    else:
        presigned_upload_url = storage_client.generate_presigned_put_url(
            bucket_name=bucket,
            object_name=object_key,
        )

    new_job = Job(
        id=job_id,
        mode=mode.value,
        status=JobStatus.PENDING.value,
        bucket=bucket,
        object_key=object_key,
    )
    db.add(new_job)
    await db.commit()

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


# --- Phase 2 Endpoints ---


@router.get(
    "/context/questions",
    response_model=ContextQuestionnaireResponse,
    summary="Context Questionnaire: Returns 5 context questions and options",
)
async def get_context_questions() -> ContextQuestionnaireResponse:
    """Return structured context questionnaire options for the client interface."""
    service = ContextGatheringService()
    return service.get_questionnaire()


@router.post(
    "/users/{user_id}/wardrobe",
    response_model=WardrobeItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a single garment image or URL to user wardrobe",
)
async def upload_user_wardrobe_item(
    user_id: str,
    request: Request,
    sync_tag: bool = Query(False, description="Run Stage 1 tagging inline"),
    db: AsyncSession = Depends(get_db_session),
) -> WardrobeItemResponse:
    """Store a single garment in the user wardrobe, register key map, and trigger Stage 1 tagging."""
    content_type = request.headers.get("content-type", "")
    image_bytes = None
    target_url = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        uploaded_file = form.get("file")
        if uploaded_file and hasattr(uploaded_file, "read"):
            image_bytes = await uploaded_file.read()
        target_url = form.get("image_url")
    elif "application/json" in content_type:
        body = await request.json()
        target_url = body.get("image_url")
    else:
        target_url = request.query_params.get("image_url")

    if not image_bytes and not target_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide an image file upload or image_url.",
        )

    service = WardrobeIngestionService()
    item, _ = await service.ingest_garment(
        session=db,
        user_id=user_id,
        image_bytes=image_bytes,
        image_url=target_url,
        sync_tag=sync_tag,
    )
    return to_wardrobe_item_response(item)


@router.get(
    "/users/{user_id}/wardrobe",
    response_model=UserWardrobeListResponse,
    summary="List all stored wardrobe items and key mappings for a user",
)
async def list_user_wardrobe_items(
    user_id: str,
    status: Optional[str] = Query(None, description="Optional status filter: PENDING_TAGS, READY, FAILED"),
    slot: Optional[str] = Query(None, description="Optional slot filter: top, bottom, etc."),
    db: AsyncSession = Depends(get_db_session),
) -> UserWardrobeListResponse:
    """Fetch all wardrobe items registered for a user with optional filters."""
    service = WardrobeIngestionService()
    items = await service.get_user_wardrobe(
        session=db,
        user_id=user_id,
        status=status,
        slot=slot,
    )
    return UserWardrobeListResponse(
        user_id=user_id,
        total_items=len(items),
        items=[to_wardrobe_item_response(i) for i in items],
    )


@router.post(
    "/users/{user_id}/recommendations",
    response_model=RecommendationResponse,
    summary="Get heuristic outfit recommendations for a user given context",
)
async def get_outfit_recommendations(
    user_id: str,
    request: DressingContextRequest,
    top_k: int = Query(5, ge=1, le=50, description="Maximum number of outfits to return"),
    db: AsyncSession = Depends(get_db_session),
) -> RecommendationResponse:
    """Resolve dressing context and run heuristic recommendation engine on user wardrobe."""
    context_service = ContextGatheringService()
    user_repo = UserRepository()
    wardrobe_service = WardrobeIngestionService()
    rec_service = RecommendationService()

    user = await user_repo.get_by_id(db, user_id)
    resolved_context = await context_service.resolve_context(request=request, user=user)

    ready_items = await wardrobe_service.get_user_wardrobe(
        session=db,
        user_id=user_id,
        status="READY",
    )

    if not ready_items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No READY wardrobe items found for user {user_id}.",
        )

    return await rec_service.get_recommendations_for_user(
        wardrobe_items=ready_items,
        user_id=user_id,
        context=resolved_context,
        top_k=top_k,
    )


# --- Curated Store and Shopping Endpoints ---


@router.get(
    "/store/items",
    response_model=List[StoreItemResponse],
    summary="List curated store items available for purchase",
)
async def list_store_items(
    slot: Optional[str] = Query(None, description="Optional slot filter"),
) -> List[StoreItemResponse]:
    """List curated store items with optional slot filter."""
    service = ShoppingService()
    return service.list_store_items(slot=slot)


@router.post(
    "/users/{user_id}/shopping/recommendations",
    response_model=ShoppingRecommendationResponse,
    summary="Get store purchase recommendations that unlock new outfits",
)
async def get_shopping_recommendations(
    user_id: str,
    request: DressingContextRequest,
    top_k: int = Query(5, ge=1, le=50, description="Maximum number of recommendations to return"),
    db: AsyncSession = Depends(get_db_session),
) -> ShoppingRecommendationResponse:
    """Evaluate store items against user wardrobe and rank items by outfit unlocks."""
    service = ShoppingService()
    return await service.recommend_purchases(
        user_id=user_id,
        context_req=request,
        top_k=top_k,
        session=db,
    )


@router.post(
    "/users/{user_id}/wardrobe/from-store/{sku_id}",
    response_model=WardrobeItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a curated store item directly to user wardrobe",
)
async def add_store_item_to_wardrobe(
    user_id: str,
    sku_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> WardrobeItemResponse:
    """Add a selected store garment directly to user wardrobe with READY status."""
    service = ShoppingService()
    try:
        return await service.add_store_item_to_wardrobe(
            user_id=user_id,
            sku_id=sku_id,
            session=db,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
