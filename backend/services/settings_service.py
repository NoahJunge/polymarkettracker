"""Settings service — read/write global settings from ES."""

import logging
from datetime import datetime, timezone

from core.es_client import ESClient
from models.settings import Settings, SettingsUpdate

logger = logging.getLogger(__name__)

SETTINGS_INDEX = "settings"
SETTINGS_DOC_ID = "global"


class SettingsService:
    def __init__(self, es: ESClient):
        self.es = es

    async def ensure_defaults(self):
        """Initialize default settings if not present."""
        existing = await self.es.get(SETTINGS_INDEX, SETTINGS_DOC_ID)
        if existing is None:
            defaults = Settings()
            defaults.updated_at_utc = datetime.now(timezone.utc)
            await self.es.index_doc(
                SETTINGS_INDEX, SETTINGS_DOC_ID, defaults.model_dump(mode="json")
            )
            logger.info("Initialized default settings")

    async def get(self) -> Settings:
        """Read settings, returning defaults if missing."""
        doc = await self.es.get(SETTINGS_INDEX, SETTINGS_DOC_ID)
        if doc is None:
            return Settings()
        return Settings(**doc)

    async def update(self, updates: SettingsUpdate) -> Settings:
        """Partial update of global settings."""
        current = await self.get()
        update_data = updates.model_dump(exclude_none=True)
        update_data["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
        merged = current.model_dump(mode="json")
        merged.update(update_data)
        await self.es.index_doc(SETTINGS_INDEX, SETTINGS_DOC_ID, merged)
        logger.info("Updated settings: %s", list(update_data.keys()))
        return Settings(**merged)
