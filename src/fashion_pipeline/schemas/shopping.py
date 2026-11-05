from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from fashion_pipeline.schemas.context import DressingContext
from fashion_pipeline.schemas.job import FacetedTag
from fashion_pipeline.schemas.wardrobe import OutfitCombination


class StoreItemResponse(BaseModel):
    """Catalog garment available for purchase in curated store."""

    sku_id: str
    name: str
    price_usd: float
    product_url: str
    image_url: str
    slot: str
    category: str
    color: str
    fabric: str
    pattern: str
    neckline: Optional[str] = None
    sleeve: Optional[str] = None
    fit: Optional[str] = None
    tags: Dict[str, FacetedTag] = Field(default_factory=dict)


class ShoppingRecommendationItem(BaseModel):
    """Recommended store garment evaluated for outfit unlock potential."""

    store_item: StoreItemResponse
    unlocked_outfits_count: int
    best_outfit_score: float
    is_missing_slot_gap: bool
    reason: str
    sample_unlocked_outfits: List[OutfitCombination] = Field(default_factory=list)


class ShoppingRecommendationResponse(BaseModel):
    """Shopping recommendation response for a user context."""

    user_id: str
    resolved_context: DressingContext
    missing_slots: List[str] = Field(default_factory=list)
    recommendations: List[ShoppingRecommendationItem] = Field(default_factory=list)
