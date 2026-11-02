from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ExecutionMode(str, Enum):
    STAGE_1 = "stage_1"
    STAGE_2 = "stage_2"


class JobStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ErrorReason(str, Enum):
    NO_GARMENTS_DETECTED = "NO_GARMENTS_DETECTED"
    CORRUPTED_IMAGE = "CORRUPTED_IMAGE"
    INFERENCE_ERROR = "INFERENCE_ERROR"
    STORAGE_ERROR = "STORAGE_ERROR"
    UNKNOWN = "UNKNOWN"


class BoundingBox(BaseModel):
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    width: int
    height: int


class FacetedTag(BaseModel):
    label: str
    confidence: float = Field(ge=0.0, le=1.0)


class PieceResult(BaseModel):
    piece_id: str
    label: str
    pixel_count: int
    bbox: BoundingBox
    tags: Dict[str, FacetedTag]
    crop_url: Optional[str] = None
    person_id: Optional[str] = None
    layer_role: Optional[str] = None


class JobCreateResponse(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.PENDING
    stream_url: str
    mode: ExecutionMode
    upload_url: Optional[str] = None


class JobResultResponse(BaseModel):
    job_id: str
    status: JobStatus
    mode: ExecutionMode
    error_reason: Optional[str] = None
    pieces: Optional[List[PieceResult]] = None
    created_at: str
    updated_at: str


class KafkaJobEvent(BaseModel):
    job_id: str
    bucket: str
    object_key: str
    execution_mode: ExecutionMode
    retry_count: int = 0
    error_reason: Optional[str] = None
