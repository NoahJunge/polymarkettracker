"""Tracking service — manage market tracking configuration."""

import logging
from datetime import datetime, timezone

from core.es_client import ESClient
from models.tracking import TrackedMarketUpdate

logger = logging.getLogger(__name__)

TRACKED_INDEX = "tracked_markets"


class TrackingService:
    def __init__(self, es: ESClient):
        self.es = es

    async def get_tracked_markets(self, size: int = 10000) -> list[dict]:
        """Get all tracked market configurations."""
        result = await self.es.search(
            TRACKED_INDEX,
            query={"term": {"is_tracked": True}},
            size=size,
        )
        return [hit["_source"] for hit in result["hits"]["hits"]]

    async def get_tracking(self, market_id: str) -> dict | None:
        """Get tracking config for a single market."""
        return await self.es.get(TRACKED_INDEX, market_id)

    async def set_tracking(self, market_id: str, update: TrackedMarketUpdate) -> dict:
        """Create or update tracking configuration for a market."""
        now = datetime.now(timezone.utc).isoformat()

        existing = await self.es.get(TRACKED_INDEX, market_id)
        if existing:
            doc = existing
            doc.update(update.model_dump(exclude_none=True))
            doc["updated_at_utc"] = now
        else:
            doc = update.model_dump(exclude_none=True)
            doc["market_id"] = market_id
            doc["created_at_utc"] = now
            doc["updated_at_utc"] = now

        await self.es.index_doc(TRACKED_INDEX, market_id, doc)
        logger.info("Updated tracking for %s: is_tracked=%s", market_id, doc.get("is_tracked"))
        return doc

    async def untrack(self, market_id: str) -> bool:
        """Set is_tracked=false for a market."""
        existing = await self.es.get(TRACKED_INDEX, market_id)
        if not existing:
            return False
        existing["is_tracked"] = False
        existing["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
        await self.es.index_doc(TRACKED_INDEX, market_id, existing)
        return True
