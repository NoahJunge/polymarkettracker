"""DCA (Dollar-Cost Averaging) service — recurring daily bets with historical backfill."""

import logging
import uuid
from collections import OrderedDict
from datetime import datetime, timezone

from core.es_client import ESClient
from models.dca import CreateDCARequest, DCASubscription, DCAAnalytics

logger = logging.getLogger(__name__)

DCA_INDEX = "dca_subscriptions"
PAPER_TRADES_INDEX = "paper_trades"
SNAPSHOTS_INDEX = "snapshots_wide"
MARKETS_INDEX = "markets"


def group_snapshots_by_day(snapshots: list[dict]) -> OrderedDict:
    """Group snapshots by calendar day (UTC), keeping the first per day."""
    daily = OrderedDict()
    for snap in snapshots:
        date_str = snap["timestamp_utc"][:10]  # YYYY-MM-DD
        if date_str not in daily:
            daily[date_str] = snap
    return daily


def build_backfill_trades(
    dca_id: str,
    market_id: str,
    side: str,
    quantity: float,
    daily_snapshots: OrderedDict,
) -> list[dict]:
    """Build trade documents for each daily snapshot."""
    trades = []
    side_upper = side.upper()
    for _date_str, snap in daily_snapshots.items():
        price = snap["yes_price"] if side_upper == "YES" else snap["no_price"]
        trades.append({
            "trade_id": str(uuid.uuid4()),
            "created_at_utc": snap["timestamp_utc"],
            "market_id": market_id,
            "side": side_upper,
            "action": "OPEN",
            "quantity": quantity,
            "price": price,
            "snapshot_ts_utc": snap["timestamp_utc"],
            "fees": 0.0,
            "metadata": {"dca": True, "dca_id": dca_id},
        })
    return trades


def compute_dca_analytics(
    dca_id: str,
    market_id: str,
    side: str,
    quantity_per_day: float,
    trades: list[dict],
    current_price: float,
    question: str = "",
) -> DCAAnalytics:
    """Compute DCA analytics from a list of trades."""
    if not trades:
        return DCAAnalytics(
            dca_id=dca_id,
            market_id=market_id,
            question=question,
            side=side,
            quantity_per_day=quantity_per_day,
            current_price=current_price,
        )

    total_shares = sum(t["quantity"] for t in trades)
    total_invested = sum(t["quantity"] * t["price"] for t in trades)
    avg_entry = total_invested / total_shares if total_shares > 0 else 0.0
    current_value = total_shares * current_price
    unrealized_pnl = current_value - total_invested
    pnl_pct = (unrealized_pnl / total_invested * 100) if total_invested > 0 else 0.0

    dates = [t["created_at_utc"][:10] for t in trades]

    return DCAAnalytics(
        dca_id=dca_id,
        market_id=market_id,
        question=question,
        side=side,
        quantity_per_day=quantity_per_day,
        total_trades=len(trades),
        total_shares=round(total_shares, 4),
        total_invested=round(total_invested, 4),
        avg_entry_price=round(avg_entry, 6),
        current_price=round(current_price, 6),
        current_value=round(current_value, 4),
        unrealized_pnl=round(unrealized_pnl, 4),
        unrealized_pnl_pct=round(pnl_pct, 2),
        first_trade_date=dates[0] if dates else "",
        last_trade_date=dates[-1] if dates else "",
    )


class DCAService:
    def __init__(self, es: ESClient):
        self.es = es

    async def create_subscription(self, req: CreateDCARequest) -> dict:
        """Create a DCA subscription and backfill historical trades."""
        dca_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        sub = DCASubscription(
            dca_id=dca_id,
            market_id=req.market_id,
            side=req.side.upper(),
            quantity=req.quantity,
            active=True,
            created_at_utc=now,
        )

        await self.es.index_doc(DCA_INDEX, dca_id, sub.model_dump(mode="json"))
        logger.info("Created DCA subscription %s for %s %s", dca_id, req.side, req.market_id)

        backfill_count = await self._backfill(dca_id, req.market_id, req.side.upper(), req.quantity)

        return {
            "dca_id": dca_id,
            "market_id": req.market_id,
            "side": req.side.upper(),
            "quantity": req.quantity,
            "trades_backfilled": backfill_count,
        }

    async def _backfill(self, dca_id: str, market_id: str, side: str, quantity: float) -> int:
        """Backfill trades for all historical days with snapshot data."""
        result = await self.es.search(
            SNAPSHOTS_INDEX,
            query={"term": {"market_id": market_id}},
            sort=[{"timestamp_utc": {"order": "asc"}}],
            size=10000,
        )
        snapshots = [h["_source"] for h in result["hits"]["hits"]]

        if not snapshots:
            logger.info("No snapshots to backfill for %s", market_id)
            return 0

        daily = group_snapshots_by_day(snapshots)
        trades = build_backfill_trades(dca_id, market_id, side, quantity, daily)

        if trades:
            await self.es.bulk_index(PAPER_TRADES_INDEX, trades, id_field="trade_id")

            last_date = list(daily.keys())[-1]
            await self.es.update(DCA_INDEX, dca_id, {
                "last_executed_date": last_date,
                "total_trades_placed": len(trades),
            })

        logger.info("Backfilled %d trades for DCA %s", len(trades), dca_id)
        return len(trades)

    async def execute_daily(self, today_date: str | None = None) -> dict:
        """Execute daily DCA trades for all active subscriptions."""
        if today_date is None:
            today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        result = await self.es.search(
            DCA_INDEX,
            query={"term": {"active": True}},
            size=10000,
        )
        subs = [h["_source"] for h in result["hits"]["hits"]]

        trades_placed = 0
        for sub in subs:
            if sub.get("last_executed_date") == today_date:
                continue

            market_id = sub["market_id"]
            side = sub["side"]
            quantity = sub["quantity"]
            dca_id = sub["dca_id"]

            # Find latest snapshot for this market
            snap_result = await self.es.search(
                SNAPSHOTS_INDEX,
                query={"term": {"market_id": market_id}},
                sort=[{"timestamp_utc": {"order": "desc"}}],
                size=1,
            )
            snaps = [h["_source"] for h in snap_result["hits"]["hits"]]
            if not snaps:
                logger.warning("No snapshot for DCA %s market %s, skipping", dca_id, market_id)
                continue

            snap = snaps[0]
            price = snap["yes_price"] if side == "YES" else snap["no_price"]

            trade = {
                "trade_id": str(uuid.uuid4()),
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "market_id": market_id,
                "side": side,
                "action": "OPEN",
                "quantity": quantity,
                "price": price,
                "snapshot_ts_utc": snap["timestamp_utc"],
                "fees": 0.0,
                "metadata": {"dca": True, "dca_id": dca_id},
            }

            await self.es.index_doc(PAPER_TRADES_INDEX, trade["trade_id"], trade)

            total = sub.get("total_trades_placed", 0) + 1
            await self.es.update(DCA_INDEX, dca_id, {
                "last_executed_date": today_date,
                "total_trades_placed": total,
            })

            trades_placed += 1
            logger.info("DCA daily trade for %s: %s %s @ %.4f", dca_id, side, market_id, price)

        return {"subscriptions_processed": len(subs), "trades_placed": trades_placed}

    async def get_subscriptions(self, market_id: str | None = None) -> list[dict]:
        """Get all DCA subscriptions, optionally filtered by market."""
        if market_id:
            query = {"term": {"market_id": market_id}}
        else:
            query = {"match_all": {}}

        result = await self.es.search(
            DCA_INDEX,
            query=query,
            sort=[{"created_at_utc": {"order": "desc"}}],
            size=1000,
        )
        subs = [h["_source"] for h in result["hits"]["hits"]]

        # Enrich with market question
        for sub in subs:
            market = await self.es.get(MARKETS_INDEX, sub["market_id"])
            sub["question"] = market.get("question", "") if market else ""

        return subs

    async def cancel_subscription(self, dca_id: str) -> bool:
        """Cancel a DCA subscription (stops future trades, keeps history)."""
        try:
            await self.es.update(DCA_INDEX, dca_id, {"active": False})
            logger.info("Cancelled DCA subscription %s", dca_id)
            return True
        except Exception as e:
            logger.error("Failed to cancel DCA %s: %s", dca_id, e)
            return False

    async def get_analytics(self, dca_id: str) -> DCAAnalytics | None:
        """Compute analytics for a specific DCA subscription."""
        sub = await self.es.get(DCA_INDEX, dca_id)
        if not sub:
            return None

        trades = await self._get_dca_trades_by_id(dca_id)

        # Get current price
        snap_result = await self.es.search(
            SNAPSHOTS_INDEX,
            query={"term": {"market_id": sub["market_id"]}},
            sort=[{"timestamp_utc": {"order": "desc"}}],
            size=1,
        )
        current_price = 0.0
        if snap_result["hits"]["hits"]:
            snap = snap_result["hits"]["hits"][0]["_source"]
            current_price = snap["yes_price"] if sub["side"] == "YES" else snap["no_price"]

        market = await self.es.get(MARKETS_INDEX, sub["market_id"])
        question = market.get("question", "") if market else ""

        return compute_dca_analytics(
            dca_id=dca_id,
            market_id=sub["market_id"],
            side=sub["side"],
            quantity_per_day=sub["quantity"],
            trades=trades,
            current_price=current_price,
            question=question,
        )

    async def get_dca_trades(self, market_id: str | None = None) -> list[dict]:
        """Get all DCA trades, optionally filtered by market."""
        must = [{"term": {"metadata.dca": True}}]
        if market_id:
            must.append({"term": {"market_id": market_id}})

        result = await self.es.search(
            PAPER_TRADES_INDEX,
            query={"bool": {"must": must}},
            sort=[{"created_at_utc": {"order": "asc"}}],
            size=10000,
        )
        return [h["_source"] for h in result["hits"]["hits"]]

    async def _get_dca_trades_by_id(self, dca_id: str) -> list[dict]:
        """Get all trades for a specific DCA subscription."""
        result = await self.es.search(
            PAPER_TRADES_INDEX,
            query={"bool": {"must": [
                {"term": {"metadata.dca": True}},
                {"term": {"metadata.dca_id": dca_id}},
            ]}},
            sort=[{"created_at_utc": {"order": "asc"}}],
            size=10000,
        )
        return [h["_source"] for h in result["hits"]["hits"]]
