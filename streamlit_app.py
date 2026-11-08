"""Interactive Streamlit Showcase for Fashion Vision Pipeline and Wardrobe Recommendations.

Operates in Direct In-Memory Engine Mode or Backend API Mode.
Follows ASD-STE-100 technical documentation rules.
"""

import json
import logging
import os
import uuid
from typing import Any, Dict, List, Tuple

import httpx
import streamlit as st

from fashion_pipeline.db.models import WardrobeItem
from fashion_pipeline.ml.engine import FashionVisionEngine
from fashion_pipeline.repositories.store_repository import StoreRepository
from fashion_pipeline.repositories.wardrobe_repository import map_category_to_slot
from fashion_pipeline.schemas.context import (
    DressingContext,
    FormalityLevel,
    OccasionType,
    StyleMood,
    TimeSetting,
    WeatherCondition,
)
from fashion_pipeline.schemas.job import PieceResult
from fashion_pipeline.schemas.wardrobe import OutfitCombination
from fashion_pipeline.services.recommendation_service import HeuristicRecommendationEngine
from fashion_pipeline.utils.outfit_visualizer import build_stacked_outfit_image

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Fashion Vision Pipeline - MVP Showcase",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for clean presentation without emojis
st.markdown(
    """
    <style>
    .main-header {
        font-size: 26px;
        font-weight: 700;
        margin-bottom: 6px;
        color: #0f172a;
    }
    .sub-header {
        font-size: 14px;
        color: #64748b;
        margin-bottom: 24px;
    }
    .metric-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: 600;
        background-color: #f1f5f9;
        color: #1e293b;
        margin-right: 6px;
    }
    .score-card {
        padding: 16px;
        border-radius: 8px;
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        margin-bottom: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_cached_vision_engine() -> FashionVisionEngine:
    """Initialize and cache the FashionVisionEngine in memory."""
    return FashionVisionEngine()


@st.cache_data
def load_cached_dummy_manifest() -> Dict[str, Any]:
    """Load pre-packaged user personas from JSON manifest."""
    manifest_path = os.path.join("tests", "dummy", "dummy_wardrobes.json")
    if not os.path.exists(manifest_path):
        return {"users": []}
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_cached_store_catalog() -> List[Dict[str, Any]]:
    """Load store catalog items."""
    repo = StoreRepository()
    return repo.list_items()


def check_backend_api_health(api_url: str = "http://localhost:8000") -> bool:
    """Verify if the FastAPI backend service is responding."""
    try:
        resp = httpx.get(f"{api_url}/healthz", timeout=1.0)
        return resp.status_code == 200
    except Exception:
        return False


def convert_manifest_user_to_wardrobe_items(user_data: Dict[str, Any]) -> List[WardrobeItem]:
    """Convert manifest user garment entries into database-compatible WardrobeItem objects."""
    items: List[WardrobeItem] = []
    user_id = user_data.get("user_id", "user_001")
    for raw in user_data.get("items", []):
        hints = raw.get("hints", {})
        tags_dict = {k: {"label": str(v), "confidence": 0.95} for k, v in hints.items()}
        item = WardrobeItem(
            item_id=raw.get("item_id"),
            user_id=user_id,
            bucket="dummy",
            object_key=f"dummy/{raw.get('item_id')}.jpg",
            source_url=raw.get("image_url"),
            status="READY",
            slot=hints.get("slot"),
            category=hints.get("category"),
            color=hints.get("color"),
            fabric=hints.get("fabric"),
            pattern=hints.get("pattern"),
            neckline=hints.get("neckline"),
            sleeve=hints.get("sleeve"),
            fit=hints.get("fit"),
            tags_json=tags_dict,
        )
        items.append(item)
    return items


def convert_piece_result_to_wardrobe_item(
    piece: PieceResult,
    user_id: str,
    image_bytes: bytes,
) -> Tuple[WardrobeItem, str]:
    """Convert vision inference piece result into an active wardrobe item."""
    tags = piece.tags or {}
    category_tag = tags.get("category")
    category = category_tag.label if category_tag else piece.label
    slot = map_category_to_slot(category)

    color_tag = tags.get("color")
    color = color_tag.label if color_tag else "neutral"

    fabric_tag = tags.get("fabric")
    fabric = fabric_tag.label if fabric_tag else "cotton"

    pattern_tag = tags.get("pattern")
    pattern = pattern_tag.label if pattern_tag else "solid"

    neckline_tag = tags.get("neckline")
    neckline = neckline_tag.label if neckline_tag else None

    sleeve_tag = tags.get("sleeve")
    sleeve = sleeve_tag.label if sleeve_tag else None

    fit_tag = tags.get("fit")
    fit = fit_tag.label if fit_tag else "regular fit"

    tags_dict = {k: {"label": v.label, "confidence": v.confidence} for k, v in tags.items()}

    item_id = f"custom-{uuid.uuid4().hex[:8]}"
    item = WardrobeItem(
        item_id=item_id,
        user_id=user_id,
        bucket="custom",
        object_key=f"custom/{item_id}.png",
        source_url=None,
        status="READY",
        slot=slot,
        category=category,
        color=color,
        fabric=fabric,
        pattern=pattern,
        neckline=neckline,
        sleeve=sleeve,
        fit=fit,
        tags_json=tags_dict,
    )
    return item, item_id


# Initialize session state collections
if "active_wardrobe" not in st.session_state:
    st.session_state.active_wardrobe = []

if "custom_crops" not in st.session_state:
    st.session_state.custom_crops = {}

if "active_user_id" not in st.session_state:
    st.session_state.active_user_id = "user_001"

if "initialized_persona" not in st.session_state:
    manifest_data = load_cached_dummy_manifest()
    users = manifest_data.get("users", [])
    if users:
        first_user = users[0]
        st.session_state.active_wardrobe = convert_manifest_user_to_wardrobe_items(first_user)
        st.session_state.active_user_id = first_user.get("user_id", "user_001")
    st.session_state.initialized_persona = True


# Sidebar Configuration
st.sidebar.title("Configuration")

api_is_online = check_backend_api_health("http://localhost:8000")
default_mode_index = 1 if api_is_online else 0

execution_mode = st.sidebar.radio(
    "System Execution Mode",
    options=["Direct In-Memory Engine (Standalone)", "Backend API (http://localhost:8000)"],
    index=default_mode_index,
    help="Direct In-Memory executes algorithms directly without external containers. Backend API connects to FastAPI.",
)

if execution_mode.startswith("Direct"):
    st.sidebar.success("Direct In-Memory Mode active. Zero external dependencies required.")
else:
    if api_is_online:
        st.sidebar.success("Backend API is online and responding.")
    else:
        st.sidebar.warning("Backend API not reachable. Fallback to In-Memory Engine is active.")

st.sidebar.markdown("---")
st.sidebar.subheader("Active Wardrobe Inventory")
st.sidebar.write(f"Total garments: {len(st.session_state.active_wardrobe)}")

slots_count: Dict[str, int] = {}
for item in st.session_state.active_wardrobe:
    s = item.slot or "other"
    slots_count[s] = slots_count.get(s, 0) + 1

for s_name, c_val in sorted(slots_count.items()):
    st.sidebar.write(f"- {s_name.replace('_', ' ').title()}: {c_val}")

if st.sidebar.button("Clear Active Wardrobe", use_container_width=True):
    st.session_state.active_wardrobe = []
    st.session_state.custom_crops = {}
    st.rerun()

# Main Header
st.markdown('<div class="main-header">Fashion Vision Pipeline & Recommendation Showcase</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">End-to-end two-stage visual parsing, multi-facet tagging, and context-aware outfit lookbook generation.</div>',
    unsafe_allow_html=True,
)

# Tabs for Step 1 and Step 2
tab_step1, tab_step2 = st.tabs([
    "Step 1: Vision Tagging & Wardrobe Input",
    "Step 2: Context Input & Stacked Recommendations",
])


# ==============================================================================
# STEP 1: VISION TAGGING & WARDROBE INPUT LAYER
# ==============================================================================
with tab_step1:
    st.subheader("Wardrobe Garment Ingestion")
    st.write(
        "Choose to inspect pre-packaged user wardrobe personas or upload custom garment images for visual inference."
    )

    opt_choice = st.radio(
        "Select Input Source",
        options=["Option A: Pre-Demo Persona Dataset", "Option B: Upload Your Own Garment / Outfit Image"],
        horizontal=True,
    )

    if opt_choice.startswith("Option A"):
        manifest_data = load_cached_dummy_manifest()
        users_list = manifest_data.get("users", [])

        if not users_list:
            st.warning("No user personas found in dummy dataset.")
        else:
            persona_labels = [
                f"{u.get('user_id')}: {u.get('display_name')} ({u.get('default_city')}, {u.get('default_style')})"
                for u in users_list
            ]
            selected_idx = st.selectbox(
                "Choose Persona",
                options=range(len(users_list)),
                format_func=lambda i: persona_labels[i],
            )
            selected_persona = users_list[selected_idx]

            col_btn, col_info = st.columns([1, 3])
            with col_btn:
                if st.button("Load This Persona into Active Wardrobe", use_container_width=True):
                    st.session_state.active_wardrobe = convert_manifest_user_to_wardrobe_items(selected_persona)
                    st.session_state.active_user_id = selected_persona.get("user_id", "user_001")
                    st.success(f"Loaded {len(st.session_state.active_wardrobe)} garments for {selected_persona.get('display_name')}.")
                    st.rerun()

            with col_info:
                st.info(
                    f"Active User: {selected_persona.get('display_name')} | "
                    f"City: {selected_persona.get('default_city')} | "
                    f"Style: {selected_persona.get('default_style')} | "
                    f"Garments in Persona: {len(selected_persona.get('items', []))}"
                )

            # Display persona garment gallery
            st.markdown("#### Persona Garment Gallery")
            items_to_display = selected_persona.get("items", [])
            cols_per_row = 4
            for row_start in range(0, len(items_to_display), cols_per_row):
                cols = st.columns(cols_per_row)
                for col_idx, item_data in enumerate(items_to_display[row_start : row_start + cols_per_row]):
                    hints = item_data.get("hints", {})
                    category = hints.get("category", "garment").title()
                    color = hints.get("color", "").title()
                    slot = hints.get("slot", "").upper()
                    fabric = hints.get("fabric", "").title()
                    img_url = item_data.get("image_url", "")

                    with cols[col_idx]:
                        st.markdown(f"**{category}** ({color})")
                        st.caption(f"Slot: {slot} | Fabric: {fabric}")
                        if img_url:
                            st.image(img_url, width=160)

    else:
        # Option B: Upload Custom Image
        st.markdown("#### Upload Garment or Outfit Image")
        st.write("Upload an image file to trigger computer vision feature extraction.")

        uploaded_files = st.file_uploader(
            "Upload image file (JPG, PNG, WEBP)",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
        )

        stage_choice = st.radio(
            "Select Vision Pipeline Stage",
            options=[
                "Stage 1: Single Garment Tagging",
                "Stage 2: Full-Body Multi-Garment Segmentation & Tagging",
            ],
            index=0,
            help="Stage 1 tags a single centered garment. Stage 2 parses full outfits into individual components.",
        )

        if uploaded_files:
            if st.button("Run Vision Inference", type="primary"):
                vision_engine = get_cached_vision_engine()
                user_id = st.session_state.active_user_id

                for uploaded_file in uploaded_files:
                    file_bytes = uploaded_file.read()
                    st.markdown(f"### Results for {uploaded_file.name}")

                    col_preview, col_results = st.columns([1, 2])
                    with col_preview:
                        st.image(file_bytes, caption="Uploaded Image", use_container_width=True)

                    with col_results:
                        with st.spinner("Processing vision model inference..."):
                            if stage_choice.startswith("Stage 1"):
                                piece_results = vision_engine.process_stage1(file_bytes)
                                crop_artifacts = [(piece_results[0].piece_id, file_bytes)]
                            else:
                                try:
                                    piece_results, crop_artifacts = vision_engine.process_stage2(file_bytes)
                                except Exception as exc:
                                    st.error(f"Stage 2 parsing error: {exc}. Falling back to Stage 1.")
                                    piece_results = vision_engine.process_stage1(file_bytes)
                                    crop_artifacts = [(piece_results[0].piece_id, file_bytes)]

                        st.success(f"Detected {len(piece_results)} garment piece(s).")
                        crop_dict = {p_id: b for p_id, b in crop_artifacts}

                        for idx, piece in enumerate(piece_results):
                            st.markdown(f"#### Piece {idx + 1}: {piece.label.title()}")
                            piece_crop_bytes = crop_dict.get(piece.piece_id, file_bytes)

                            crop_col, tags_col = st.columns([1, 2])
                            with crop_col:
                                st.image(piece_crop_bytes, caption=f"Crop: {piece.piece_id}", width=180)

                            with tags_col:
                                for facet_name, facet_tag in (piece.tags or {}).items():
                                    conf_val = float(facet_tag.confidence)
                                    st.write(f"**{facet_name.title()}**: {facet_tag.label.title()} ({int(conf_val * 100)}%)")
                                    st.progress(min(1.0, max(0.0, conf_val)))

                            # Add to active wardrobe
                            new_wardrobe_item, new_item_id = convert_piece_result_to_wardrobe_item(
                                piece=piece,
                                user_id=user_id,
                                image_bytes=piece_crop_bytes,
                            )
                            st.session_state.custom_crops[new_item_id] = piece_crop_bytes
                            st.session_state.active_wardrobe.append(new_wardrobe_item)
                            st.info(f"Added '{new_wardrobe_item.category}' to active wardrobe as {new_wardrobe_item.slot}.")


# ==============================================================================
# STEP 2: CONTEXT INPUT & STACKED OUTFIT RECOMMENDATIONS
# ==============================================================================
with tab_step2:
    st.subheader("Dressing Context & Lookbook Recommendations")
    st.write(
        "Specify the context parameters. The heuristic recommendation engine applies thermal constraints, formality filters, and harmonic scoring."
    )

    # 5 Context Dimensions
    c1, c2, c3 = st.columns(3)
    with c1:
        occasion_choice = st.selectbox(
            "1. Occasion",
            options=[e.value for e in OccasionType],
            index=0,
            format_func=lambda x: x.replace("_", " ").title(),
        )
        weather_choice = st.selectbox(
            "2. Weather Condition",
            options=[e.value for e in WeatherCondition],
            index=2,
            format_func=lambda x: x.replace("_", " ").title(),
        )

    with c2:
        formality_choice = st.selectbox(
            "3. Formality Level",
            options=[e.value for e in FormalityLevel],
            index=1,
            format_func=lambda x: x.replace("_", " ").title(),
        )
        time_choice = st.selectbox(
            "4. Time & Setting",
            options=[e.value for e in TimeSetting],
            index=0,
            format_func=lambda x: x.replace("_", " ").title(),
        )

    with c3:
        mood_choice = st.selectbox(
            "5. Style Mood",
            options=[e.value for e in StyleMood],
            index=0,
            format_func=lambda x: x.replace("_", " ").title(),
        )
        top_k_val = st.slider("Top Recommendations Count", min_value=1, max_value=5, value=3)

    st.markdown("---")

    context_obj = DressingContext(
        occasion=OccasionType(occasion_choice),
        formality=FormalityLevel(formality_choice),
        weather=WeatherCondition(weather_choice),
        time_setting=TimeSetting(time_choice),
        style_mood=StyleMood(mood_choice),
    )

    btn_recommend = st.button("Generate Outfit Recommendations", type="primary", use_container_width=True)

    if btn_recommend or len(st.session_state.active_wardrobe) > 0:
        if not st.session_state.active_wardrobe:
            st.warning("Active wardrobe is empty. Please load a persona or upload garments in Step 1.")
        else:
            rec_engine = HeuristicRecommendationEngine()
            with st.spinner("Scoring candidate outfit combinations..."):
                recommended_outfits: List[OutfitCombination] = rec_engine.generate_recommendations(
                    wardrobe=st.session_state.active_wardrobe,
                    context=context_obj,
                    top_k=top_k_val,
                )

            if not recommended_outfits:
                st.warning("No outfits satisfied the hard context filters for this wardrobe.")
            else:
                st.markdown(f"### Recommended Outfits ({len(recommended_outfits)} Found)")

                for idx, outfit in enumerate(recommended_outfits):
                    st.markdown(f"#### Outfit Combination #{idx + 1}")

                    col_lookbook, col_scores = st.columns([1, 1])

                    with col_lookbook:
                        # Build lookbook stacked composite image
                        lookbook_img = build_stacked_outfit_image(
                            outfit_items=outfit.items,
                            canvas_width=420,
                            garment_images=st.session_state.custom_crops,
                        )
                        st.image(lookbook_img, caption=f"Outfit #{idx + 1} Lookbook Composition", width=380)

                    with col_scores:
                        st.markdown(
                            f'<div class="score-card">'
                            f'<div style="font-size: 22px; font-weight: 700; color: #1e293b;">'
                            f'Total Score: {outfit.total_score:.1f} / 100</div>'
                            f'<div style="font-size: 13px; color: #475569; margin-top: 4px;">{outfit.rationale}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                        breakdown = outfit.score_breakdown or {}
                        st.write("**Score Breakdown**")
                        c_col1, c_col2 = st.columns(2)
                        with c_col1:
                            st.write(f"- Color Harmony: {breakdown.get('color_harmony', 0):.1f} / 30")
                            st.write(f"- Pattern Balance: {breakdown.get('pattern_balance', 0):.1f} / 25")
                            st.write(f"- Silhouette: {breakdown.get('silhouette_balance', 0):.1f} / 20")
                        with c_col2:
                            st.write(f"- Fabric Consistency: {breakdown.get('fabric_consistency', 0):.1f} / 15")
                            st.write(f"- Tag Confidence: {breakdown.get('tag_confidence', 0):.1f} / 10")

                        st.write("**Garments in Combination**")
                        for slot_k, item_resp in outfit.items.items():
                            slot_title = slot_k.replace("_", " ").title()
                            cat_name = getattr(item_resp, "category", "") or ""
                            color_name = getattr(item_resp, "color", "") or ""
                            fabric_name = getattr(item_resp, "fabric", "") or ""
                            st.write(f"- **{slot_title}**: {cat_name.title()} ({color_name.title()}, {fabric_name.title()})")

                    st.markdown("---")

    # ==============================================================================
    # SHOPPING RECOMMENDATIONS EXPANDER
    # ==============================================================================
    with st.expander("Shopping Recommendations & Wardrobe Gap Analysis", expanded=False):
        st.write(
            "Analyzes gaps in the active wardrobe for the specified context and recommends curated store items that unlock complete outfits."
        )

        store_items = load_cached_store_catalog()
        engine = HeuristicRecommendationEngine()

        # Check missing slots in active wardrobe
        present_slots = {
            item.slot or map_category_to_slot(item.category)
            for item in st.session_state.active_wardrobe
        }

        missing_slots: List[str] = []
        for s_check in ["top", "bottom", "footwear", "outerwear"]:
            if s_check not in present_slots:
                missing_slots.append(s_check)

        if missing_slots:
            st.info(f"Identified missing wardrobe slots for this context: {', '.join(missing_slots)}")
        else:
            st.info("Wardrobe has base coverage. Showing curated upgrade recommendations.")

        # Filter store items
        candidate_store_items = [
            itm for itm in store_items
            if (missing_slots and itm.get("slot") in missing_slots) or not missing_slots
        ]

        if not candidate_store_items:
            candidate_store_items = store_items[:4]

        top_store_candidates = candidate_store_items[:3]

        for s_idx, store_item in enumerate(top_store_candidates):
            sku_id = store_item.get("sku_id")
            name = store_item.get("name")
            price = store_item.get("price_usd", 0.0)
            slot = store_item.get("slot")
            category = store_item.get("category")
            color = store_item.get("color")
            fabric = store_item.get("fabric")
            image_url = store_item.get("image_url")

            st.markdown(f"#### Store Recommendation #{s_idx + 1}: {name}")
            col_store_info, col_store_preview = st.columns([1, 1])

            with col_store_info:
                if image_url:
                    st.image(image_url, width=180)
                st.write(f"**Price**: ${price:.2f} USD")
                st.write(f"**Category**: {category.title()} | **Slot**: {slot.title()}")
                st.write(f"**Color**: {color.title()} | **Fabric**: {fabric.title()}")

                btn_add_store = st.button(
                    f"Add {category.title()} to Wardrobe",
                    key=f"btn_store_add_{sku_id}",
                )
                if btn_add_store:
                    tags_dict = {
                        k: {"label": v.get("label", ""), "confidence": v.get("confidence", 0.9)}
                        for k, v in store_item.get("tags", {}).items()
                    }
                    store_wardrobe_item = WardrobeItem(
                        item_id=f"shop-{sku_id}",
                        user_id=st.session_state.active_user_id,
                        bucket="store",
                        object_key=f"store/{sku_id}.jpg",
                        source_url=image_url,
                        status="READY",
                        slot=slot,
                        category=category,
                        color=color,
                        fabric=fabric,
                        pattern=store_item.get("pattern", "solid"),
                        neckline=store_item.get("neckline"),
                        sleeve=store_item.get("sleeve"),
                        fit=store_item.get("fit", "regular fit"),
                        tags_json=tags_dict,
                    )
                    st.session_state.active_wardrobe.append(store_wardrobe_item)
                    st.success(f"Added {name} to active wardrobe.")
                    st.rerun()

            with col_store_preview:
                # Synthesize preview with this item
                preview_transient = WardrobeItem(
                    item_id=f"shop-{sku_id}",
                    user_id=st.session_state.active_user_id,
                    bucket="store",
                    object_key=f"store/{sku_id}.jpg",
                    source_url=image_url,
                    status="READY",
                    slot=slot,
                    category=category,
                    color=color,
                    fabric=fabric,
                    pattern=store_item.get("pattern", "solid"),
                    neckline=store_item.get("neckline"),
                    sleeve=store_item.get("sleeve"),
                    fit=store_item.get("fit", "regular fit"),
                    tags_json=store_item.get("tags"),
                )

                test_wardrobe = [preview_transient] + st.session_state.active_wardrobe
                simulated_outfits = engine.generate_recommendations(
                    wardrobe=test_wardrobe,
                    context=context_obj,
                    top_k=1,
                )

                if simulated_outfits:
                    sim_outfit = simulated_outfits[0]
                    st.caption(f"Unlocked Lookbook (Score: {sim_outfit.total_score:.1f}/100)")
                    sim_img = build_stacked_outfit_image(
                        outfit_items=sim_outfit.items,
                        canvas_width=320,
                        garment_images=st.session_state.custom_crops,
                    )
                    st.image(sim_img, width=280)
                else:
                    st.caption("No combined outfit available.")

            st.markdown("---")
