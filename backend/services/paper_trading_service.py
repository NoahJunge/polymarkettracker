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
    EquityCurvePoint,
    PortfolioStats,
    EquityCurveResponse,
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

    async def get_equity_curve(self) -> EquityCurveResponse:
        """Compute equity curve with mark-to-market unrealized P&L."""
        import asyncio
        from datetime import date as date_cls, timedelta

        trades = await self._get_all_trades()
        if not trades:
            return EquityCurveResponse(curve=[], stats=PortfolioStats())

        market_ids = list(set(t["market_id"] for t in trades))

        # Determine date range: first trade date → today
        first_date = trades[0]["created_at_utc"][:10]
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        start = date_cls.fromisoformat(first_date)
        end = date_cls.fromisoformat(today)
        dates: list[str] = []
        d = start
        while d <= end:
            dates.append(d.isoformat())
            d += timedelta(days=1)

        # Fetch latest snapshot per market for each date using collapse
        async def fetch_day_prices(date_str: str) -> tuple[str, dict]:
            result = await self.es.search(
                SNAPSHOTS_INDEX,
                query={
                    "bool": {
                        "must": [
                            {"terms": {"market_id": market_ids}},
                            {"range": {"timestamp_utc": {"lte": f"{date_str}T23:59:59Z"}}},
                        ]
                    }
                },
                sort=[{"timestamp_utc": {"order": "desc"}}],
                size=len(market_ids),
                collapse="market_id",
            )
            prices = {}
            for hit in result["hits"]["hits"]:
                s = hit["_source"]
                prices[s["market_id"]] = {
                    "yes_price": float(s["yes_price"]),
                    "no_price": float(s["no_price"]),
                }
            return date_str, prices

        daily_prices: dict[str, dict] = {}
        # Batch 10 concurrent queries at a time
        for i in range(0, len(dates), 10):
            batch = dates[i : i + 10]
            results = await asyncio.gather(*(fetch_day_prices(d) for d in batch))
            for date_str, prices in results:
                if prices:
                    daily_prices[date_str] = prices

        curve = self._compute_equity_curve(trades, daily_prices)
        stats = self._compute_portfolio_stats(trades, curve)
        return EquityCurveResponse(curve=curve, stats=stats)

    @staticmethod
    def _compute_equity_curve(
        trades: list[dict],
        daily_prices: dict[str, dict[str, dict]],
    ) -> list[EquityCurvePoint]:
        """Replay trades chronologically and mark-to-market using daily snapshot prices.

        Args:
            trades: list of trade dicts sorted by created_at_utc asc
            daily_prices: date -> {market_id -> {yes_price, no_price}}
        """
        if not trades:
            return []

        # Group trades by date
        trades_by_date: dict[str, list[dict]] = defaultdict(list)
        for t in trades:
            date = t.get("created_at_utc", "")[:10]
            if date:
                trades_by_date[date].append(t)

        # All dates with either trades or snapshot prices
        all_dates = sorted(set(list(trades_by_date.keys()) + list(daily_prices.keys())))

        open_tracker: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
        cumulative_invested = 0.0
        cumulative_realized = 0.0
        total_opens = 0
        total_closes = 0
        last_known_prices: dict[str, dict] = {}  # market_id -> {yes_price, no_price}

        curve: list[EquityCurvePoint] = []

        for date in all_dates:
            # 1. Process trades for this date
            for t in trades_by_date.get(date, []):
                key = (t["market_id"], t["side"])
                qty = float(t["quantity"])
                price = float(t["price"])

                if t["action"] == "OPEN":
                    open_tracker[key].append((qty, price))
                    cumulative_invested += qty * price
                    total_opens += 1
                elif t["action"] == "CLOSE":
                    remaining = qty
                    while remaining > 0 and open_tracker[key]:
                        open_qty, open_price = open_tracker[key][0]
                        matched = min(remaining, open_qty)
                        cumulative_realized += matched * (price - open_price)
                        remaining -= matched
                        if matched >= open_qty:
                            open_tracker[key].pop(0)
                        else:
                            open_tracker[key][0] = (open_qty - matched, open_price)
                    total_closes += 1

            # 2. Update latest known prices from snapshots
            if date in daily_prices:
                for mid, prices in daily_prices[date].items():
                    last_known_prices[mid] = prices

            # 3. Compute unrealized P&L from open positions at current prices
            unrealized = 0.0
            portfolio_value = 0.0
            for (mid, side), lots in open_tracker.items():
                total_qty = sum(q for q, _ in lots)
                if total_qty <= 0:
                    continue
                prices = last_known_prices.get(mid)
                if prices:
                    cp = prices["yes_price"] if side == "YES" else prices["no_price"]
                else:
                    # Fallback: use average entry price (no snapshot yet)
                    cp = sum(q * p for q, p in lots) / total_qty
                pv = total_qty * cp
                cost = sum(q * p for q, p in lots)
                unrealized += pv - cost
                portfolio_value += pv

            total_pnl = unrealized + cumulative_realized

            curve.append(EquityCurvePoint(
                date=date,
                total_pnl=round(total_pnl, 4),
                unrealized_pnl=round(unrealized, 4),
                realized_pnl=round(cumulative_realized, 4),
                cumulative_invested=round(cumulative_invested, 4),
                portfolio_value=round(portfolio_value, 4),
                total_open_trades=total_opens,
                total_close_trades=total_closes,
            ))

        return curve

    @staticmethod
    def _compute_portfolio_stats(trades: list[dict], curve: list[EquityCurvePoint]) -> PortfolioStats:
        """Compute portfolio statistics from trades and equity curve."""
        stats = PortfolioStats()

        if not trades and not curve:
            return stats

        # Compute per-close P&L using FIFO (for win/loss stats)
        open_tracker: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
        close_pnls: list[float] = []

        for t in trades:
            key = (t["market_id"], t["side"])
            qty = float(t["quantity"])
            price = float(t["price"])

            if t["action"] == "OPEN":
                open_tracker[key].append((qty, price))
            elif t["action"] == "CLOSE":
                remaining = qty
                trade_pnl = 0.0
                while remaining > 0 and open_tracker[key]:
                    open_qty, open_price = open_tracker[key][0]
                    matched = min(remaining, open_qty)
                    trade_pnl += matched * (price - open_price)
                    remaining -= matched
                    if matched >= open_qty:
                        open_tracker[key].pop(0)
                    else:
                        open_tracker[key][0] = (open_qty - matched, open_price)
                close_pnls.append(trade_pnl)

        # Win/loss stats from closed trades
        if close_pnls:
            wins = [p for p in close_pnls if p > 0]
            losses = [p for p in close_pnls if p < 0]
            stats.total_wins = len(wins)
            stats.total_losses = len(losses)
            stats.win_rate = round(len(wins) / len(close_pnls) * 100, 2)
            stats.avg_win = round(sum(wins) / len(wins), 4) if wins else 0.0
            stats.avg_loss = round(sum(losses) / len(losses), 4) if losses else 0.0
            total_win_amount = sum(wins) if wins else 0.0
            total_loss_amount = abs(sum(losses)) if losses else 0.0
            stats.profit_factor = round(total_win_amount / total_loss_amount, 4) if total_loss_amount > 0 else None

        # Sharpe ratio from daily changes in total P&L (unrealized + realized)
        if len(curve) >= 2:
            daily_changes = [
                curve[i].total_pnl - curve[i - 1].total_pnl
                for i in range(1, len(curve))
            ]
            import numpy as np
            arr = np.array(daily_changes)
            mean_change = float(np.mean(arr))
            std_change = float(np.std(arr, ddof=1))
            if std_change > 0:
                stats.sharpe_ratio = round(mean_change / std_change, 4)

        # Max drawdown on total P&L
        if curve:
            pnl_values = [pt.total_pnl for pt in curve]
            peak = pnl_values[0]
            max_dd = 0.0
            for v in pnl_values:
                if v > peak:
                    peak = v
                dd = peak - v
                if dd > max_dd:
                    max_dd = dd
            stats.max_drawdown = round(max_dd, 4)

        # Linear regression on total P&L
        if len(curve) >= 3:
            import numpy as np
            from scipy.stats import linregress
            x = np.arange(len(curve), dtype=float)
            y = np.array([pt.total_pnl for pt in curve])
            result = linregress(x, y)
            stats.regression_slope = round(float(result.slope), 6)
            stats.regression_r_squared = round(float(result.rvalue ** 2), 4)
            stats.regression_p_value = round(float(result.pvalue), 6)
            stats.trend_significant = bool(result.pvalue < 0.05)
            if stats.trend_significant:
                stats.trend_direction = "up" if result.slope > 0 else "down"
            else:
                stats.trend_direction = "none"

        return stats

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
