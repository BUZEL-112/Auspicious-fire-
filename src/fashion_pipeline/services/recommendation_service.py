import itertools
import logging
from typing import Dict, List, Optional, Set, Tuple

from fashion_pipeline.db.models import WardrobeItem
from fashion_pipeline.repositories.wardrobe_repository import (
    WardrobeRepository,
    map_category_to_slot,
)
from fashion_pipeline.schemas.context import (
    DressingContext,
    FormalityLevel,
    OccasionType,
    StyleMood,
    WeatherCondition,
)
from fashion_pipeline.schemas.wardrobe import (
    OutfitCombination,
    RecommendationResponse,
    WardrobeItemResponse,
)

logger = logging.getLogger(__name__)

NEUTRAL_COLORS: Set[str] = {
    "black",
    "white",
    "grey",
    "navy",
    "beige",
    "brown",
}

ACCENT_COLORS: Set[str] = {
    "red",
    "blue",
    "green",
    "yellow",
    "pink",
    "purple",
    "orange",
}

CLASHING_COLOR_PAIRS: Set[Tuple[str, str]] = {
    ("orange", "purple"),
    ("purple", "orange"),
    ("pink", "orange"),
    ("orange", "pink"),
    ("green", "red"),
    ("red", "green"),
    ("yellow", "pink"),
    ("pink", "yellow"),
}


class HeuristicRecommendationEngine:
    """Heuristic engine implementing Stage 2 Hard Context Filters and Stage 3 Compatibility Scoring."""

    def filter_item_for_context(self, item: WardrobeItem, context: DressingContext) -> bool:
        """Evaluate whether a single garment satisfies hard thermal and formality rules."""
        category = (item.category or "").lower()
        fabric = (item.fabric or "").lower()
        sleeve = (item.sleeve or "").lower()
        neckline = (item.neckline or "").lower()
        pattern = (item.pattern or "").lower()
        fit = (item.fit or "").lower()
        slot = item.slot or map_category_to_slot(category)

        # 1. Thermal Hard Filters
        if context.weather == WeatherCondition.HOT:
            if fabric in {"wool", "velvet", "leather"}:
                return False
            if sleeve == "long sleeve" and slot == "top" and fabric not in {"linen", "silk"}:
                return False
            if neckline == "turtleneck":
                return False
            if category == "coat":
                return False
            if category == "boots":
                return False

        elif context.weather in {WeatherCondition.COLD, WeatherCondition.FREEZING}:
            if category in {"shorts", "sandals"}:
                return False
            if sleeve == "sleeveless" and slot in {"top", "one_piece"}:
                return False

        elif context.weather == WeatherCondition.RAINY:
            if category == "sandals":
                return False
            if fabric in {"silk", "chiffon"}:
                return False

        # 2. Formality Hard Filters
        if context.formality in {
            FormalityLevel.BUSINESS_FORMAL,
            FormalityLevel.SEMI_FORMAL,
            FormalityLevel.BLACK_TIE,
        }:
            if category in {"shorts", "hoodie", "sandals", "sneakers", "t-shirt"}:
                return False
            if pattern in {"camo", "graphic"}:
                return False
            if fit == "oversized":
                return False

        if context.occasion == OccasionType.WORKOUT_ACTIVE:
            if category in {"blazer", "coat", "dress"}:
                return False
            if fabric in {"silk", "leather", "wool", "velvet"}:
                return False
            if category in {"boots", "sandals"}:
                return False

        return True

    def score_color_harmony(self, items: List[WardrobeItem], style_mood: StyleMood) -> float:
        """Compute color harmony score between 0.0 and 30.0."""
        colors = [item.color.lower() for item in items if item.color]
        if not colors:
            return 22.0

        unique_colors = set(colors)

        # Monochromatic or tone-on-tone palette
        if len(unique_colors) == 1:
            return 30.0

        # Check for direct clashing color pairs
        for c1, c2 in itertools.combinations(colors, 2):
            if (c1, c2) in CLASHING_COLOR_PAIRS:
                return 10.0

        # Check neutral foundation with single accent
        neutrals = [c for c in colors if c in NEUTRAL_COLORS]
        accents = [c for c in colors if c in ACCENT_COLORS]

        if len(accents) <= 1:
            if style_mood == StyleMood.CLEAN_MINIMALIST:
                return 28.0
            return 27.0

        if len(accents) == 2 and style_mood == StyleMood.BOLD_EXPRESSIVE:
            return 26.0

        if len(neutrals) == len(colors):
            return 28.0

        return 22.0

    def score_pattern_balance(self, items: List[WardrobeItem]) -> float:
        """Compute pattern clash prevention score between 0.0 and 25.0."""
        patterns = [item.pattern.lower() for item in items if item.pattern]
        if not patterns:
            return 22.0

        non_solid = [p for p in patterns if p != "solid"]

        # All solid pieces
        if len(non_solid) == 0:
            return 25.0

        # One patterned statement piece with solid anchors
        if len(non_solid) == 1:
            return 25.0

        # Multiple busy patterns cause visual clash
        return 8.0

    def score_silhouette_balance(
        self,
        top_or_dress: WardrobeItem,
        bottom: Optional[WardrobeItem],
        style_mood: StyleMood,
    ) -> float:
        """Compute silhouette and fit balance score between 0.0 and 20.0."""
        top_fit = (top_or_dress.fit or "regular fit").lower()

        if bottom is None:
            # One-piece dress
            if top_fit in {"slim fit", "regular fit"}:
                return 19.0
            return 17.0

        bottom_fit = (bottom.fit or "regular fit").lower()

        # Proportional contrast rule: oversized top with slim/regular bottom
        if "loose" in top_fit or "oversized" in top_fit:
            if "slim" in bottom_fit or "regular" in bottom_fit:
                return 20.0
            if "loose" in bottom_fit or "oversized" in bottom_fit:
                return 18.0 if style_mood == StyleMood.RELAXED_COMFORT else 12.0

        # Fitted top with relaxed bottom
        if "slim" in top_fit or "tight" in top_fit:
            if "loose" in bottom_fit or "regular" in bottom_fit:
                return 20.0

        # Regular with regular
        if "regular" in top_fit and "regular" in bottom_fit:
            return 18.0

        return 16.0

    def score_fabric_consistency(self, items: List[WardrobeItem]) -> float:
        """Compute fabric texture harmony score between 0.0 and 15.0."""
        fabrics = [item.fabric.lower() for item in items if item.fabric]
        if not fabrics:
            return 12.0

        # Clashing seasonal combinations (e.g. wool with linen)
        if "wool" in fabrics and "linen" in fabrics:
            return 6.0

        # Synergistic combinations
        if ("cotton" in fabrics and "denim" in fabrics) or ("silk" in fabrics and "knit" in fabrics):
            return 15.0

        return 13.0

    def score_confidence(self, items: List[WardrobeItem]) -> float:
        """Compute confidence score contribution between 0.0 and 10.0."""
        confidences: List[float] = []
        for item in items:
            if item.tags_json and isinstance(item.tags_json, dict):
                for facet_data in item.tags_json.values():
                    if isinstance(facet_data, dict) and "confidence" in facet_data:
                        confidences.append(float(facet_data["confidence"]))
        if not confidences:
            return 9.0
        avg_conf = sum(confidences) / len(confidences)
        return round(min(10.0, max(0.0, avg_conf * 10.0)), 2)

    def evaluate_outfit(
        self,
        candidate_items: Dict[str, WardrobeItem],
        context: DressingContext,
    ) -> OutfitCombination:
        """Score an assembled outfit across all heuristic dimensions."""
        items_list = list(candidate_items.values())

        top_or_dress = candidate_items.get("top") or candidate_items.get("one_piece")
        bottom = candidate_items.get("bottom")

        color_score = self.score_color_harmony(items_list, context.style_mood)
        pattern_score = self.score_pattern_balance(items_list)
        silhouette_score = (
            self.score_silhouette_balance(top_or_dress, bottom, context.style_mood)
            if top_or_dress
            else 15.0
        )
        fabric_score = self.score_fabric_consistency(items_list)
        conf_score = self.score_confidence(items_list)

        total_score = round(
            color_score + pattern_score + silhouette_score + fabric_score + conf_score,
            1,
        )
        total_score = min(100.0, max(0.0, total_score))

        breakdown = {
            "color_harmony": color_score,
            "pattern_balance": pattern_score,
            "silhouette_balance": silhouette_score,
            "fabric_consistency": fabric_score,
            "tag_confidence": conf_score,
        }

        # Format items response dict
        response_items: Dict[str, WardrobeItemResponse] = {}
        for slot_key, itm in candidate_items.items():
            response_items[slot_key] = WardrobeItemResponse(
                item_id=itm.item_id,
                user_id=itm.user_id,
                job_id=itm.job_id,
                bucket=itm.bucket,
                object_key=itm.object_key,
                source_url=itm.source_url,
                status=itm.status,
                slot=itm.slot,
                category=itm.category,
                color=itm.color,
                fabric=itm.fabric,
                pattern=itm.pattern,
                neckline=itm.neckline,
                sleeve=itm.sleeve,
                fit=itm.fit,
                tags_json=itm.tags_json,
                created_at=itm.created_at.isoformat() if itm.created_at else "",
                updated_at=itm.updated_at.isoformat() if itm.updated_at else "",
            )

        rationale = (
            f"Outfit scored {total_score}/100 with color harmony {color_score}/30 "
            f"for {context.occasion.value} in {context.weather.value} weather."
        )

        outfit_id = f"outfit-{'-'.join([itm.item_id[:8] for itm in items_list])}"

        return OutfitCombination(
            outfit_id=outfit_id,
            items=response_items,
            total_score=total_score,
            score_breakdown=breakdown,
            rationale=rationale,
        )

    def generate_recommendations(
        self,
        wardrobe: List[WardrobeItem],
        context: DressingContext,
        top_k: int = 5,
    ) -> List[OutfitCombination]:
        """Filter wardrobe items, assemble candidate outfits, and rank top recommendations."""
        # 1. Apply Hard Context Filters
        filtered_items = [item for item in wardrobe if self.filter_item_for_context(item, context)]

        # If strict filtering removes all items, use entire wardrobe as fallback
        candidates_pool = filtered_items if len(filtered_items) >= 2 else wardrobe

        # 2. Group by Garment Slot
        slots: Dict[str, List[WardrobeItem]] = {
            "top": [],
            "bottom": [],
            "one_piece": [],
            "outerwear": [],
            "footwear": [],
            "accessory": [],
        }
        for itm in candidates_pool:
            s = itm.slot or map_category_to_slot(itm.category)
            if s in slots:
                slots[s].append(itm)

        outfits: List[OutfitCombination] = []

        # Determine if outerwear is needed or preferred
        need_outerwear = context.weather in {
            WeatherCondition.FREEZING,
            WeatherCondition.COLD,
            WeatherCondition.RAINY,
        }

        # Formula A: Top + Bottom (+ Footwear) (+ Outerwear)
        for top in slots["top"]:
            for btm in slots["bottom"]:
                base: Dict[str, WardrobeItem] = {"top": top, "bottom": btm}

                # Add footwear if available
                footwear_options = slots["footwear"] if slots["footwear"] else [None]
                for fw in footwear_options:
                    combo = dict(base)
                    if fw is not None:
                        combo["footwear"] = fw

                    if need_outerwear and slots["outerwear"]:
                        for ow in slots["outerwear"]:
                            combo_with_ow = dict(combo)
                            combo_with_ow["outerwear"] = ow
                            outfits.append(self.evaluate_outfit(combo_with_ow, context))
                    else:
                        outfits.append(self.evaluate_outfit(combo, context))

        # Formula B: One-piece (+ Footwear) (+ Outerwear)
        for dress in slots["one_piece"]:
            base = {"one_piece": dress}
            footwear_options = slots["footwear"] if slots["footwear"] else [None]
            for fw in footwear_options:
                combo = dict(base)
                if fw is not None:
                    combo["footwear"] = fw

                if need_outerwear and slots["outerwear"]:
                    for ow in slots["outerwear"]:
                        combo_with_ow = dict(combo)
                        combo_with_ow["outerwear"] = ow
                        outfits.append(self.evaluate_outfit(combo_with_ow, context))
                else:
                    outfits.append(self.evaluate_outfit(combo, context))

        # Sort descending by total heuristic score
        outfits.sort(key=lambda x: x.total_score, reverse=True)
        return outfits[:top_k]


class RecommendationService:
    """Service orchestrating wardrobe retrieval, context gathering, and heuristic recommendations."""

    def __init__(
        self,
        wardrobe_repo: Optional[WardrobeRepository] = None,
        engine: Optional[HeuristicRecommendationEngine] = None,
    ):
        self.wardrobe_repo = wardrobe_repo or WardrobeRepository()
        self.engine = engine or HeuristicRecommendationEngine()

    async def get_recommendations_for_user(
        self,
        wardrobe_items: List[WardrobeItem],
        user_id: str,
        context: DressingContext,
        top_k: int = 5,
    ) -> RecommendationResponse:
        """Generate ranked outfit recommendations for a user given their resolved context."""
        outfits = self.engine.generate_recommendations(
            wardrobe=wardrobe_items,
            context=context,
            top_k=top_k,
        )

        return RecommendationResponse(
            user_id=user_id,
            resolved_context=context,
            outfits=outfits,
        )
