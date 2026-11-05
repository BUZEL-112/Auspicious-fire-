import logging
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from fashion_pipeline.config.settings import settings
from fashion_pipeline.db.models import Job, WardrobeItem
from fashion_pipeline.repositories.job_repository import JobRepository
from fashion_pipeline.repositories.store_repository import StoreRepository
from fashion_pipeline.repositories.user_repository import UserRepository
from fashion_pipeline.repositories.wardrobe_repository import (
    WardrobeRepository,
    map_category_to_slot,
)
from fashion_pipeline.schemas.context import (
    DressingContext,
    DressingContextRequest,
    WeatherCondition,
)
from fashion_pipeline.schemas.job import FacetedTag
from fashion_pipeline.schemas.shopping import (
    ShoppingRecommendationItem,
    ShoppingRecommendationResponse,
    StoreItemResponse,
)
from fashion_pipeline.schemas.wardrobe import (
    OutfitCombination,
    WardrobeItemResponse,
)
from fashion_pipeline.services.context_service import ContextGatheringService
from fashion_pipeline.services.recommendation_service import HeuristicRecommendationEngine
from fashion_pipeline.storage.minio_client import MinIOClient, storage_client
from fashion_pipeline.utils.image_converter import download_or_synthesize_garment_image

logger = logging.getLogger(__name__)


def _to_wardrobe_item_response(item: WardrobeItem) -> WardrobeItemResponse:
    """Convert WardrobeItem database entity to WardrobeItemResponse schema."""
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


class ShoppingService:
    """Service handling store catalog access, outfit unlock scoring, and wardrobe purchase."""

    def __init__(
        self,
        session: Optional[AsyncSession] = None,
        store_repo: Optional[StoreRepository] = None,
        wardrobe_repo: Optional[WardrobeRepository] = None,
        user_repo: Optional[UserRepository] = None,
        job_repo: Optional[JobRepository] = None,
        context_service: Optional[ContextGatheringService] = None,
        engine: Optional[HeuristicRecommendationEngine] = None,
        storage: Optional[MinIOClient] = None,
    ):
        self.session = session
        self.store_repo = store_repo or StoreRepository()
        self.wardrobe_repo = wardrobe_repo or WardrobeRepository()
        self.user_repo = user_repo or UserRepository()
        self.job_repo = job_repo or JobRepository()
        self.context_service = context_service or ContextGatheringService()
        self.engine = engine or HeuristicRecommendationEngine()
        self.storage = storage or storage_client

    def _get_session(self, session: Optional[AsyncSession]) -> AsyncSession:
        """Resolve active database session from argument or instance property."""
        active_session = session or self.session
        if active_session is None:
            raise ValueError("An active database session is required.")
        return active_session

    def _to_store_item_response(self, item_dict: Dict[str, Any]) -> StoreItemResponse:
        """Convert store catalog dictionary to StoreItemResponse schema."""
        tags_dict: Dict[str, FacetedTag] = {}
        raw_tags = item_dict.get("tags") or {}
        for facet, tag_data in raw_tags.items():
            if isinstance(tag_data, dict):
                tags_dict[facet] = FacetedTag(
                    label=str(tag_data.get("label", "")),
                    confidence=float(tag_data.get("confidence", 0.99)),
                )
            elif isinstance(tag_data, FacetedTag):
                tags_dict[facet] = tag_data

        return StoreItemResponse(
            sku_id=item_dict["sku_id"],
            name=item_dict["name"],
            price_usd=float(item_dict["price_usd"]),
            product_url=item_dict["product_url"],
            image_url=item_dict["image_url"],
            slot=item_dict["slot"],
            category=item_dict["category"],
            color=item_dict["color"],
            fabric=item_dict["fabric"],
            pattern=item_dict["pattern"],
            neckline=item_dict.get("neckline"),
            sleeve=item_dict.get("sleeve"),
            fit=item_dict.get("fit"),
            tags=tags_dict,
        )

    def _to_transient_wardrobe_item(self, item_dict: Dict[str, Any], user_id: str) -> WardrobeItem:
        """Create an in-memory WardrobeItem representing a shoppable store garment."""
        sku_id = item_dict["sku_id"]
        return WardrobeItem(
            item_id=f"shop-{sku_id}",
            user_id=user_id,
            job_id=None,
            bucket="store",
            object_key=f"store/{sku_id}.jpg",
            source_url=item_dict.get("image_url"),
            status="READY",
            slot=item_dict.get("slot"),
            category=item_dict.get("category"),
            color=item_dict.get("color"),
            fabric=item_dict.get("fabric"),
            pattern=item_dict.get("pattern"),
            neckline=item_dict.get("neckline"),
            sleeve=item_dict.get("sleeve"),
            fit=item_dict.get("fit"),
            tags_json=item_dict.get("tags"),
        )

    def _detect_missing_slots(
        self,
        eligible_user_items: List[WardrobeItem],
        context: DressingContext,
    ) -> List[str]:
        """Identify relevant garment slots that contain zero eligible items."""
        eligible_by_slot: Dict[str, List[WardrobeItem]] = {
            "top": [],
            "bottom": [],
            "one_piece": [],
            "outerwear": [],
            "footwear": [],
            "accessory": [],
        }
        for itm in eligible_user_items:
            s = itm.slot or map_category_to_slot(itm.category)
            if s in eligible_by_slot:
                eligible_by_slot[s].append(itm)

        missing: List[str] = []

        need_outerwear = context.weather in {
            WeatherCondition.FREEZING,
            WeatherCondition.COLD,
            WeatherCondition.RAINY,
        }

        has_tops = len(eligible_by_slot["top"]) > 0
        has_bottoms = len(eligible_by_slot["bottom"]) > 0
        has_one_piece = len(eligible_by_slot["one_piece"]) > 0

        if not has_tops and not has_one_piece:
            missing.append("top")

        if not has_bottoms and not has_one_piece:
            missing.append("bottom")

        if len(eligible_by_slot["footwear"]) == 0:
            missing.append("footwear")

        if need_outerwear and len(eligible_by_slot["outerwear"]) == 0:
            missing.append("outerwear")

        return missing

    def list_store_items(self, slot: Optional[str] = None) -> List[StoreItemResponse]:
        """List store catalog items with optional slot filter."""
        items = self.store_repo.list_items(slot=slot)
        return [self._to_store_item_response(itm) for itm in items]

    async def recommend_purchases(
        self,
        user_id: str,
        context_req: DressingContextRequest,
        top_k: int = 5,
        min_unlock_score: float = 65.0,
        session: Optional[AsyncSession] = None,
    ) -> ShoppingRecommendationResponse:
        """Calculate store purchase recommendations that unlock new outfits for the user."""
        active_session = self._get_session(session)

        # 1. Resolve context
        user = await self.user_repo.get_by_id(active_session, user_id)
        resolved_context = await self.context_service.resolve_context(
            request=context_req,
            user=user,
        )

        # 2. Load user READY wardrobe items
        user_items = await self.wardrobe_repo.list_by_user(
            session=active_session,
            user_id=user_id,
            status="READY",
        )

        # 3. Filter existing items to find missing slot gaps
        eligible_user_items = self.engine._filter_items(user_items, resolved_context)
        missing_slots = self._detect_missing_slots(eligible_user_items, resolved_context)

        # 4. Filter store catalog items using context filters
        all_store_items = self.store_repo.list_items()
        context_store_items: List[Dict[str, Any]] = []
        for itm in all_store_items:
            virtual = self._to_transient_wardrobe_item(itm, user_id)
            if self.engine.filter_item_for_context(virtual, resolved_context):
                context_store_items.append(itm)

        # 5. Extract owned item signatures to prevent duplicate recommendations
        owned_signatures: Set[Tuple[str, str, str, str, str]] = set()
        for itm in user_items:
            s_slot = (itm.slot or map_category_to_slot(itm.category)).lower()
            s_cat = (itm.category or "").lower()
            s_col = (itm.color or "").lower()
            s_fab = (itm.fabric or "").lower()
            s_pat = (itm.pattern or "").lower()
            owned_signatures.add((s_slot, s_cat, s_col, s_fab, s_pat))

        # 6. Evaluate outfit unlock capability for each candidate store item
        candidates: List[ShoppingRecommendationItem] = []

        for candidate in context_store_items:
            c_slot = (candidate.get("slot") or "").lower()
            c_cat = (candidate.get("category") or "").lower()
            c_col = (candidate.get("color") or "").lower()
            c_fab = (candidate.get("fabric") or "").lower()
            c_pat = (candidate.get("pattern") or "").lower()

            # Skip items the user already owns
            if (c_slot, c_cat, c_col, c_fab, c_pat) in owned_signatures:
                continue

            sku_id = candidate["sku_id"]
            virtual_item = self._to_transient_wardrobe_item(candidate, user_id)
            virtual_id = virtual_item.item_id

            # Evaluate outfit combinations with virtual item added
            combined_wardrobe = user_items + [virtual_item]
            generated_outfits = self.engine.recommend(
                wardrobe=combined_wardrobe,
                context=resolved_context,
                top_k=25,
            )

            # Filter for outfits containing this store item and meeting min score
            matching_outfits: List[OutfitCombination] = [
                outfit for outfit in generated_outfits
                if any(garment.item_id == virtual_id for garment in outfit.items.values())
                and outfit.total_score >= min_unlock_score
            ]

            unlocked_count = len(matching_outfits)
            best_score = max((o.total_score for o in matching_outfits), default=0.0)
            is_gap = candidate.get("slot") in missing_slots

            if is_gap:
                reason = (
                    f"Fills a missing {candidate.get('slot')} gap for {resolved_context.weather.value} weather. "
                    f"Unlocks {unlocked_count} outfits with best score {best_score:.1f}/100."
                )
            else:
                reason = (
                    f"Matches your existing garments for {resolved_context.occasion.value}. "
                    f"Unlocks {unlocked_count} outfits with best score {best_score:.1f}/100."
                )

            recommendation_item = ShoppingRecommendationItem(
                store_item=self._to_store_item_response(candidate),
                unlocked_outfits_count=unlocked_count,
                best_outfit_score=best_score,
                is_missing_slot_gap=is_gap,
                reason=reason,
                sample_unlocked_outfits=matching_outfits[:2],
            )
            candidates.append(recommendation_item)

        # 7. Rank candidates by (is_missing_slot_gap, unlocked_outfits_count, best_outfit_score) descending
        candidates.sort(
            key=lambda item: (
                item.is_missing_slot_gap,
                item.unlocked_outfits_count,
                item.best_outfit_score,
            ),
            reverse=True,
        )

        return ShoppingRecommendationResponse(
            user_id=user_id,
            resolved_context=resolved_context,
            missing_slots=missing_slots,
            recommendations=candidates[:top_k],
        )

    async def add_store_item_to_wardrobe(
        self,
        user_id: str,
        sku_id: str,
        session: Optional[AsyncSession] = None,
    ) -> WardrobeItemResponse:
        """Add a store item directly to user wardrobe with READY status."""
        active_session = self._get_session(session)

        # 1. Fetch store item
        store_item = self.store_repo.get_by_sku(sku_id)
        if not store_item:
            raise ValueError(f"Store item with SKU '{sku_id}' was not found.")

        # 2. Ensure user exists
        await self.user_repo.create_or_get(active_session, user_id=user_id)

        # 3. Generate identifiers and storage location
        item_id = f"item-{uuid.uuid4().hex[:12]}"
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        bucket = settings.MINIO_RAW_BUCKET
        object_key = f"users/{user_id}/items/{item_id}.jpg"

        # 4. Upload placeholder or downloaded image bytes
        image_url = store_item["image_url"]
        try:
            image_bytes = download_or_synthesize_garment_image(image_url)
            self.storage.upload_bytes(
                bucket_name=bucket,
                object_name=object_key,
                data=image_bytes,
                content_type="image/jpeg",
            )
        except Exception as exc:
            logger.warning(
                f"Could not upload image bytes for store item {sku_id}: {exc}"
            )

        # 5. Create COMPLETED job record
        job_result = [{"sku_id": sku_id, "source": "store_catalog"}]
        new_job = Job(
            id=job_id,
            mode="stage_1",
            status="COMPLETED",
            bucket=bucket,
            object_key=object_key,
            user_id=user_id,
            item_id=item_id,
            result=job_result,
        )
        await self.job_repo.create(active_session, new_job)

        # 6. Create READY wardrobe item record
        new_item = WardrobeItem(
            item_id=item_id,
            user_id=user_id,
            job_id=job_id,
            bucket=bucket,
            object_key=object_key,
            source_url=image_url,
            status="READY",
            slot=store_item["slot"],
            category=store_item["category"],
            color=store_item["color"],
            fabric=store_item["fabric"],
            pattern=store_item["pattern"],
            neckline=store_item.get("neckline"),
            sleeve=store_item.get("sleeve"),
            fit=store_item.get("fit"),
            tags_json=store_item.get("tags"),
        )
        await self.wardrobe_repo.create(active_session, new_item)
        await active_session.commit()

        return _to_wardrobe_item_response(new_item)
