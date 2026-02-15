"""Paper trading service — open/close trades, compute positions and P&L."""

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from core.es_client import ESClient
from models.paper_trade import (
    OpenTradeRequest,
    CloseTradeRequest,
    PaperTrade,
    Position,
    PortfolioSummary,
)

logger = logging.getLogger(__name__)

PAPER_TRADES_INDEX = "paper_trades"
SNAPSHOTS_INDEX = "snapshots_wide"
MARKETS_INDEX = "markets"


class PaperTradingService:
    def __init__(self, es: ESClient):
        self.es = es

    async def open_trade(self, req: OpenTradeRequest) -> PaperTrade:
        """Open a paper trade: record a BUY at the nearest snapshot price."""
        snapshot = await self._nearest_snapshot(req.market_id, req.at_timestamp)
        if not snapshot:
            raise ValueError(f"No snapshot found for market {req.market_id}")

        price = snapshot["yes_price"] if req.side.upper() == "YES" else snapshot["no_price"]

        trade = PaperTrade(
            trade_id=str(uuid.uuid4()),
            created_at_utc=datetime.now(timezone.utc),
            market_id=req.market_id,
            side=req.side.upper(),
            action="OPEN",
            quantity=req.quantity,
            price=price,
            snapshot_ts_utc=snapshot.get("timestamp_utc"),
            fees=req.fees,
            metadata={},
        )

        await self.es.index_doc(
            PAPER_TRADES_INDEX, trade.trade_id, trade.model_dump(mode="json")
        )
        logger.info("Opened trade %s: %s %s @ %.4f", trade.trade_id, req.side, req.market_id, price)
        return trade

    async def close_trade(self, req: CloseTradeRequest) -> PaperTrade:
        """Close (sell) a paper position by recording a CLOSE trade."""
        snapshot = await self._nearest_snapshot(req.market_id, req.at_timestamp)
        if not snapshot:
            raise ValueError(f"No snapshot found for market {req.market_id}")

        price = snapshot["yes_price"] if req.side.upper() == "YES" else snapshot["no_price"]

        # Determine quantity: if not specified, close the full open position
        quantity = req.quantity
        if quantity is None:
            positions = await self._aggregate_positions()
            key = (req.market_id, req.side.upper())
            pos = positions.get(key)
            if not pos or pos["net_quantity"] <= 0:
                raise ValueError(f"No open position for {req.market_id} {req.side}")
            quantity = pos["net_quantity"]

        trade = PaperTrade(
            trade_id=str(uuid.uuid4()),
            created_at_utc=datetime.now(timezone.utc),
            market_id=req.market_id,
            side=req.side.upper(),
            action="CLOSE",
            quantity=quantity,
            price=price,
            snapshot_ts_utc=snapshot.get("timestamp_utc"),
            fees=req.fees,
            metadata={},
        )

        await self.es.index_doc(
            PAPER_TRADES_INDEX, trade.trade_id, trade.model_dump(mode="json")
        )
        logger.info("Closed trade %s: %s %s @ %.4f", trade.trade_id, req.side, req.market_id, price)
        return trade

    async def get_open_positions(self) -> list[Position]:
        """Compute current open positions with mark-to-market values."""
        positions_data = await self._aggregate_positions()

        # Filter to positions with net quantity > 0
        open_positions = {
            k: v for k, v in positions_data.items() if v["net_quantity"] > 0
        }
        if not open_positions:
            return []

        # Batch fetch: all unique market_ids
        market_ids = list(set(mid for mid, _ in open_positions.keys()))

        # One query: latest snapshot per market using collapse
        snap_result = await self.es.search(
            SNAPSHOTS_INDEX,
            query={"terms": {"market_id": market_ids}},
            sort=[{"timestamp_utc": {"order": "desc"}}],
            size=len(market_ids),
            collapse="market_id",
        )
        snap_map = {}
        for hit in snap_result["hits"]["hits"]:
            s = hit["_source"]
            snap_map[s["market_id"]] = s

        # One mget: all market metadata
        market_map = await self.es.mget(MARKETS_INDEX, market_ids)

        result = []
        for (market_id, side), pos in open_positions.items():
            snapshot = snap_map.get(market_id)
            current_price = 0.0
            if snapshot:
                current_price = snapshot["yes_price"] if side == "YES" else snapshot["no_price"]

            market = market_map.get(market_id)
            question = market.get("question", "") if market else ""
            is_closed = bool(market.get("closed")) if market else False

            market_value = pos["net_quantity"] * current_price
            cost_basis = pos["net_quantity"] * pos["avg_entry_price"]
            unrealized_pnl = market_value - cost_basis
            pnl_pct = (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0.0

            result.append(
                Position(
                    market_id=market_id,
                    question=question,
                    side=side,
                    net_quantity=pos["net_quantity"],
                    avg_entry_price=pos["avg_entry_price"],
                    current_price=current_price,
                    market_value=round(market_value, 4),
                    unrealized_pnl=round(unrealized_pnl, 4),
                    unrealized_pnl_pct=round(pnl_pct, 2),
                    last_trade_date=pos["last_trade_date"],
                    closed=is_closed,
                )
            )

        return result

    async def get_portfolio_summary(self) -> PortfolioSummary:
        """Compute total portfolio summary."""
        positions = await self.get_open_positions()
        all_trades = await self._get_all_trades()

        total_unrealized = sum(p.unrealized_pnl for p in positions)
        total_equity = sum(p.market_value for p in positions)
        total_cost = sum(p.net_quantity * p.avg_entry_price for p in positions)

        # Realized P&L: sum of (close_price - avg_open_price) * close_quantity for each closed portion
        realized_pnl = await self._compute_realized_pnl(all_trades)

        return PortfolioSummary(
            total_equity=round(total_equity, 4),
            total_cost_basis=round(total_cost, 4),
            total_unrealized_pnl=round(total_unrealized, 4),
            total_realized_pnl=round(realized_pnl, 4),
            open_position_count=len(positions),
            total_trades=len(all_trades),
        )

    async def get_all_trades(self) -> list[dict]:
        """Get all paper trades, newest first, enriched with market questions."""
        result = await self.es.search(
            PAPER_TRADES_INDEX,
            query={"match_all": {}},
            sort=[{"created_at_utc": {"order": "desc"}}],
            size=10000,
        )
        trades = [hit["_source"] for hit in result["hits"]["hits"]]

        # Batch fetch market questions
        market_ids = list(set(t["market_id"] for t in trades if t.get("market_id")))
        if market_ids:
            market_map = await self.es.mget(MARKETS_INDEX, market_ids)
            for t in trades:
                m = market_map.get(t["market_id"])
                t["question"] = m.get("question", "") if m else ""

        return trades

    async def _nearest_snapshot(
        self, market_id: str, timestamp: datetime | None = None
    ) -> dict | None:
        """Find the nearest snapshot at or before the given timestamp (or latest)."""
        must_clauses = [{"term": {"market_id": market_id}}]
        if timestamp:
            must_clauses.append(
                {"range": {"timestamp_utc": {"lte": timestamp.isoformat()}}}
            )

        result = await self.es.search(
            SNAPSHOTS_INDEX,
            query={"bool": {"must": must_clauses}},
            sort=[{"timestamp_utc": {"order": "desc"}}],
            size=1,
        )

        hits = result["hits"]["hits"]
        return hits[0]["_source"] if hits else None

    async def _get_all_trades(self) -> list[dict]:
        """Get all trades from ES."""
        result = await self.es.search(
            PAPER_TRADES_INDEX,
            query={"match_all": {}},
            sort=[{"created_at_utc": {"order": "asc"}}],
            size=10000,
        )
        return [hit["_source"] for hit in result["hits"]["hits"]]

    async def _aggregate_positions(self) -> dict[tuple[str, str], dict]:
        """Aggregate trades into net positions per (market_id, side)."""
        trades = await self._get_all_trades()
        positions: dict[tuple[str, str], dict] = defaultdict(
            lambda: {"open_quantity": 0.0, "open_cost": 0.0, "close_quantity": 0.0, "close_revenue": 0.0, "last_trade_date": ""}
        )

        for t in trades:
            key = (t["market_id"], t["side"])
            qty = float(t["quantity"])
            price = float(t["price"])

            if t["action"] == "OPEN":
                positions[key]["open_quantity"] += qty
                positions[key]["open_cost"] += qty * price
            elif t["action"] == "CLOSE":
                positions[key]["close_quantity"] += qty
                positions[key]["close_revenue"] += qty * price

            # Track latest trade date
            trade_date = t.get("created_at_utc", "")[:10]
            if trade_date > positions[key]["last_trade_date"]:
                positions[key]["last_trade_date"] = trade_date

        # Compute net quantities and avg entry prices
        result = {}
        for key, pos in positions.items():
            net_qty = pos["open_quantity"] - pos["close_quantity"]
            avg_entry = (
                pos["open_cost"] / pos["open_quantity"]
                if pos["open_quantity"] > 0
                else 0.0
            )
            result[key] = {
                "net_quantity": net_qty,
                "avg_entry_price": avg_entry,
                "open_quantity": pos["open_quantity"],
                "open_cost": pos["open_cost"],
                "close_quantity": pos["close_quantity"],
                "close_revenue": pos["close_revenue"],
                "last_trade_date": pos["last_trade_date"],
            }

        return result

    async def _compute_realized_pnl(self, trades: list[dict]) -> float:
        """Compute realized P&L from closed trades."""
        # Group trades by (market_id, side), compute avg entry, then realized on closes
        open_tracker: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
        realized = 0.0

        for t in trades:
            key = (t["market_id"], t["side"])
            qty = float(t["quantity"])
            price = float(t["price"])

            if t["action"] == "OPEN":
                open_tracker[key].append((qty, price))
            elif t["action"] == "CLOSE":
                # FIFO: close against earliest opens
                remaining = qty
                while remaining > 0 and open_tracker[key]:
                    open_qty, open_price = open_tracker[key][0]
                    matched = min(remaining, open_qty)
                    realized += matched * (price - open_price)
                    remaining -= matched
                    if matched >= open_qty:
                        open_tracker[key].pop(0)
                    else:
                        open_tracker[key][0] = (open_qty - matched, open_price)

        return realized
