from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from fashion_pipeline.schemas.context import DressingContext


class WardrobeItemStatus(str, Enum):
    """Lifecycle status of a wardrobe item."""

    PENDING_TAGS = "PENDING_TAGS"
    READY = "READY"
    FAILED = "FAILED"


class GarmentSlot(str, Enum):
    """Garment slot category for outfit assembly."""

    TOP = "top"
    BOTTOM = "bottom"
    ONE_PIECE = "one_piece"
    OUTERWEAR = "outerwear"
    FOOTWEAR = "footwear"
    ACCESSORY = "accessory"


class WardrobeItemCreateRequest(BaseModel):
    """Request payload to ingest an item from an external image URL."""

    image_url: Optional[str] = None


class WardrobeItemResponse(BaseModel):
    """Wardrobe item representation with taxonomy tags and storage metadata."""

    item_id: str
    user_id: str
    job_id: Optional[str] = None
    bucket: str
    object_key: str
    source_url: Optional[str] = None
    status: str
    slot: Optional[str] = None
    category: Optional[str] = None
    color: Optional[str] = None
    fabric: Optional[str] = None
    pattern: Optional[str] = None
    neckline: Optional[str] = None
    sleeve: Optional[str] = None
    fit: Optional[str] = None
    tags_json: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: str


class UserWardrobeListResponse(BaseModel):
    """List response for all wardrobe items owned by a user."""

    user_id: str
    total_items: int
    items: List[WardrobeItemResponse]


class OutfitCombination(BaseModel):
    """Recommended outfit assembly with heuristic score evaluation."""

    outfit_id: str
    items: Dict[str, WardrobeItemResponse]
    total_score: float = Field(ge=0.0, le=100.0)
    score_breakdown: Dict[str, float]
    rationale: Optional[str] = None


class RecommendationResponse(BaseModel):
    """Top outfit recommendations for a resolved user context."""

    user_id: str
    resolved_context: DressingContext
    outfits: List[OutfitCombination]
