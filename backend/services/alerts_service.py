"""Alert service — create, check, and manage price alerts."""

import logging
import uuid
from datetime import datetime, timezone

from core.es_client import ESClient

logger = logging.getLogger(__name__)

ALERTS_INDEX = "alerts"
SNAPSHOTS_INDEX = "snapshots_wide"
MARKETS_INDEX = "markets"


class AlertsService:
    def __init__(self, es: ESClient):
        self.es = es

    async def create_alert(
        self,
        market_id: str,
        side: str,
        condition: str,
        threshold: float,
        note: str = "",
    ) -> dict:
        """Create a new price alert."""
        alert_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "alert_id": alert_id,
            "market_id": market_id,
            "side": side.upper(),
            "condition": condition.upper(),
            "threshold": threshold,
            "active": True,
            "triggered": False,
            "triggered_at_utc": None,
            "triggered_price": None,
            "created_at_utc": now,
            "note": note,
        }
        await self.es.index_doc(ALERTS_INDEX, alert_id, doc)
        return doc

    async def get_alerts(self, active_only: bool = False) -> list[dict]:
        """Get all alerts, optionally filtered to active only."""
        if active_only:
            query = {"bool": {"must": [
                {"term": {"active": True}},
                {"term": {"triggered": False}},
            ]}}
        else:
            query = {"match_all": {}}

        result = await self.es.search(
            ALERTS_INDEX,
            query=query,
            sort=[{"created_at_utc": {"order": "desc"}}],
            size=1000,
        )
        alerts = [h["_source"] for h in result["hits"]["hits"]]

        # Enrich with market question
        for alert in alerts:
            market = await self.es.get(MARKETS_INDEX, alert["market_id"])
            if market:
                alert["question"] = market.get("question", "")

        return alerts

    async def delete_alert(self, alert_id: str) -> bool:
        """Delete an alert."""
        return await self.es.delete(ALERTS_INDEX, alert_id)

    async def dismiss_alert(self, alert_id: str) -> bool:
        """Mark a triggered alert as inactive (dismissed)."""
        try:
            await self.es.update(ALERTS_INDEX, alert_id, {"active": False})
            return True
        except Exception:
            return False

    async def check_alerts(self) -> list[dict]:
        """Check all active alerts against latest prices. Returns newly triggered alerts."""
        # Get all active, untriggered alerts
        result = await self.es.search(
            ALERTS_INDEX,
            query={"bool": {"must": [
                {"term": {"active": True}},
                {"term": {"triggered": False}},
            ]}},
            size=10000,
        )
        alerts = [h["_source"] for h in result["hits"]["hits"]]
        if not alerts:
            return []

        triggered = []
        now = datetime.now(timezone.utc).isoformat()

        for alert in alerts:
            mid = alert["market_id"]
            # Get latest snapshot for this market
            snap_result = await self.es.search(
                SNAPSHOTS_INDEX,
                query={"term": {"market_id": mid}},
                sort=[{"timestamp_utc": {"order": "desc"}}],
                size=1,
            )
            if not snap_result["hits"]["hits"]:
                continue

            snap = snap_result["hits"]["hits"][0]["_source"]
            price = snap.get("yes_price", 0) if alert["side"] == "YES" else snap.get("no_price", 0)

            condition_met = False
            if alert["condition"] == "ABOVE" and price >= alert["threshold"]:
                condition_met = True
            elif alert["condition"] == "BELOW" and price <= alert["threshold"]:
                condition_met = True

            if condition_met:
                await self.es.update(ALERTS_INDEX, alert["alert_id"], {
                    "triggered": True,
                    "triggered_at_utc": now,
                    "triggered_price": price,
                })
                alert["triggered"] = True
                alert["triggered_at_utc"] = now
                alert["triggered_price"] = price
                triggered.append(alert)

        if triggered:
            logger.info("Triggered %d alerts", len(triggered))

        return triggered

    async def get_triggered_alerts(self) -> list[dict]:
        """Get all triggered but still active alerts (unread notifications)."""
        result = await self.es.search(
            ALERTS_INDEX,
            query={"bool": {"must": [
                {"term": {"active": True}},
                {"term": {"triggered": True}},
            ]}},
            sort=[{"triggered_at_utc": {"order": "desc"}}],
            size=100,
        )
        alerts = [h["_source"] for h in result["hits"]["hits"]]

        for alert in alerts:
            market = await self.es.get(MARKETS_INDEX, alert["market_id"])
            if market:
                alert["question"] = market.get("question", "")

        return alerts
