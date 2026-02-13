"""Export service — generate CSV/XLSX snapshots for audit trail."""

import logging
import os
from datetime import datetime, timezone

import pandas as pd

from core.es_client import ESClient

logger = logging.getLogger(__name__)

SNAPSHOTS_INDEX = "snapshots_wide"


class ExportService:
    def __init__(self, es: ESClient, export_dir: str = "/exports"):
        self.es = es
        self.export_dir = export_dir
        os.makedirs(export_dir, exist_ok=True)

    async def export_daily_snapshot(self, date: datetime | None = None) -> str | None:
        """Export all snapshots for a given date to CSV. Returns filepath or None."""
        if date is None:
            date = datetime.now(timezone.utc)

        date_str = date.strftime("%Y_%m_%d")
        start = date.strftime("%Y-%m-%dT00:00:00Z")
        end = date.strftime("%Y-%m-%dT23:59:59Z")

        result = await self.es.search(
            SNAPSHOTS_INDEX,
            query={
                "range": {
                    "timestamp_utc": {"gte": start, "lte": end}
                }
            },
            sort=[{"timestamp_utc": {"order": "asc"}}],
            size=10000,
        )

        rows = [hit["_source"] for hit in result["hits"]["hits"]]
        if not rows:
            logger.info("No snapshots to export for %s", date_str)
            return None

        df = pd.DataFrame(rows)
        filepath = os.path.join(self.export_dir, f"snapshot_{date_str}.csv")
        df.to_csv(filepath, index=False)
        logger.info("Exported %d rows to %s", len(rows), filepath)
        return filepath

    async def export_all(self) -> str | None:
        """Export all snapshots to a single CSV in the export directory."""
        result = await self.es.search(
            SNAPSHOTS_INDEX,
            query={"match_all": {}},
            sort=[{"timestamp_utc": {"order": "asc"}}],
            size=10000,
        )

        rows = [hit["_source"] for hit in result["hits"]["hits"]]
        if not rows:
            logger.info("No snapshots to export")
            return None

        now_str = datetime.now(timezone.utc).strftime("%Y_%m_%d_%H%M%S")
        filepath = os.path.join(self.export_dir, f"snapshot_all_{now_str}.csv")
        df = pd.DataFrame(rows)
        df.to_csv(filepath, index=False)
        logger.info("Exported %d rows to %s", len(rows), filepath)
        return filepath

    async def list_exports(self) -> list[dict]:
        """List all export files in the export directory."""
        files = []
        for f in sorted(os.listdir(self.export_dir), reverse=True):
            if f.startswith("snapshot_") and (f.endswith(".csv") or f.endswith(".xlsx")):
                path = os.path.join(self.export_dir, f)
                stat = os.stat(path)
                files.append({
                    "filename": f,
                    "size_bytes": stat.st_size,
                    "created_utc": datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                })
        return files
