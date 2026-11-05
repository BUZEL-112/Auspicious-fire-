import json
import os
from typing import Any, Dict, List, Optional

from fashion_pipeline.config.settings import settings


class StoreRepository:
    """Repository that provides access to the curated store catalog."""

    def __init__(self, catalog_path: Optional[str] = None):
        self.catalog_path = catalog_path or getattr(settings, "STORE_CATALOG_PATH", "data/store_catalog.json")
        self._cached_items: Optional[List[Dict[str, Any]]] = None

    def _resolve_path(self) -> str:
        """Resolve absolute path to catalog file if relative path is not found."""
        if os.path.exists(self.catalog_path):
            return self.catalog_path
        # Look relative to project root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        candidate = os.path.join(project_root, self.catalog_path)
        if os.path.exists(candidate):
            return candidate
        return self.catalog_path

    def _load_catalog(self) -> List[Dict[str, Any]]:
        """Load catalog items from disk."""
        if self._cached_items is None:
            path = self._resolve_path()
            if not os.path.exists(path):
                return []
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    self._cached_items = data
                elif isinstance(data, dict) and "items" in data:
                    self._cached_items = data["items"]
                else:
                    self._cached_items = []
        return self._cached_items

    def list_items(self, slot: Optional[str] = None) -> List[Dict[str, Any]]:
        """List store catalog items with optional slot filter."""
        items = self._load_catalog()
        if slot is not None:
            normalized_slot = slot.lower().strip()
            return [item for item in items if item.get("slot", "").lower() == normalized_slot]
        return list(items)

    def get_by_sku(self, sku_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single store catalog item by SKU identifier."""
        items = self._load_catalog()
        for item in items:
            if item.get("sku_id") == sku_id:
                return item
        return None
