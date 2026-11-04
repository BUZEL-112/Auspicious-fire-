from typing import Any, Dict, List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from fashion_pipeline.db.models import WardrobeItem


CATEGORY_TO_SLOT_MAP: Dict[str, str] = {
    "top": "top",
    "t-shirt": "top",
    "shirt": "top",
    "blouse": "top",
    "sweater": "top",
    "hoodie": "top",
    "jacket": "outerwear",
    "coat": "outerwear",
    "blazer": "outerwear",
    "pants": "bottom",
    "jeans": "bottom",
    "shorts": "bottom",
    "skirt": "bottom",
    "dress": "one_piece",
    "shoes": "footwear",
    "sneakers": "footwear",
    "boots": "footwear",
    "sandals": "footwear",
    "bag": "accessory",
    "hat": "accessory",
    "scarf": "accessory",
}


def map_category_to_slot(category: Optional[str]) -> str:
    """Map taxonomy category name to garment slot."""
    if not category:
        return "accessory"
    normalized = category.lower().strip()
    return CATEGORY_TO_SLOT_MAP.get(normalized, "top")


class WardrobeRepository:
    """Repository handling database operations for WardrobeItem records."""

    async def get_by_id(self, session: AsyncSession, item_id: str) -> Optional[WardrobeItem]:
        """Fetch a wardrobe item by primary key."""
        stmt = select(WardrobeItem).where(WardrobeItem.item_id == item_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_job_id(self, session: AsyncSession, job_id: str) -> Optional[WardrobeItem]:
        """Fetch a wardrobe item mapped to a vision job."""
        stmt = select(WardrobeItem).where(WardrobeItem.job_id == job_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        session: AsyncSession,
        user_id: str,
        status: Optional[str] = None,
        slot: Optional[str] = None,
    ) -> List[WardrobeItem]:
        """List wardrobe items for a given user with optional status and slot filters."""
        stmt = select(WardrobeItem).where(WardrobeItem.user_id == user_id)
        if status:
            stmt = stmt.where(WardrobeItem.status == status)
        if slot:
            stmt = stmt.where(WardrobeItem.slot == slot)
        stmt = stmt.order_by(WardrobeItem.created_at.desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, session: AsyncSession, item: WardrobeItem) -> WardrobeItem:
        """Persist a new wardrobe item key map."""
        session.add(item)
        await session.flush()
        return item

    async def update_tags_and_status(
        self,
        session: AsyncSession,
        item_id: str,
        status: str,
        slot: Optional[str] = None,
        category: Optional[str] = None,
        color: Optional[str] = None,
        fabric: Optional[str] = None,
        pattern: Optional[str] = None,
        neckline: Optional[str] = None,
        sleeve: Optional[str] = None,
        fit: Optional[str] = None,
        tags_json: Optional[Dict[str, Any]] = None,
    ) -> Optional[WardrobeItem]:
        """Update wardrobe item status and extracted visual tags."""
        values: Dict[str, Any] = {"status": status}
        if slot is not None:
            values["slot"] = slot
        if category is not None:
            values["category"] = category
        if color is not None:
            values["color"] = color
        if fabric is not None:
            values["fabric"] = fabric
        if pattern is not None:
            values["pattern"] = pattern
        if neckline is not None:
            values["neckline"] = neckline
        if sleeve is not None:
            values["sleeve"] = sleeve
        if fit is not None:
            values["fit"] = fit
        if tags_json is not None:
            values["tags_json"] = tags_json

        stmt = (
            update(WardrobeItem)
            .where(WardrobeItem.item_id == item_id)
            .values(**values)
            .execution_options(synchronize_session="fetch")
        )
        await session.execute(stmt)
        return await self.get_by_id(session, item_id)
