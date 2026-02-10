"""Tests for paper trading P&L calculations and snapshot selection logic."""

import pytest


def compute_unrealized_pnl(
    quantity: float, avg_entry_price: float, current_price: float
) -> float:
    """Replicate the P&L computation from PaperTradingService."""
    market_value = quantity * current_price
    cost_basis = quantity * avg_entry_price
    return market_value - cost_basis


def compute_realized_pnl_fifo(trades: list[dict]) -> float:
    """Replicate FIFO realized P&L from PaperTradingService._compute_realized_pnl."""
    from collections import defaultdict

    open_tracker: dict[tuple, list[tuple[float, float]]] = defaultdict(list)
    realized = 0.0

    for t in trades:
        key = (t["market_id"], t["side"])
        qty = float(t["quantity"])
        price = float(t["price"])

        if t["action"] == "OPEN":
            open_tracker[key].append((qty, price))
        elif t["action"] == "CLOSE":
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


class TestUnrealizedPnL:
    def test_long_yes_profit(self):
        """Buy YES at 0.40, current price 0.60 → profit."""
        pnl = compute_unrealized_pnl(quantity=10, avg_entry_price=0.40, current_price=0.60)
        assert pnl == pytest.approx(2.0)

    def test_long_yes_loss(self):
        """Buy YES at 0.70, current price 0.50 → loss."""
        pnl = compute_unrealized_pnl(quantity=10, avg_entry_price=0.70, current_price=0.50)
        assert pnl == pytest.approx(-2.0)

    def test_long_no_profit(self):
        """Buy NO at 0.30, NO price rises to 0.50 → profit."""
        pnl = compute_unrealized_pnl(quantity=5, avg_entry_price=0.30, current_price=0.50)
        assert pnl == pytest.approx(1.0)

    def test_breakeven(self):
        pnl = compute_unrealized_pnl(quantity=100, avg_entry_price=0.50, current_price=0.50)
        assert pnl == pytest.approx(0.0)

    def test_full_win(self):
        """Market resolves YES at 1.0, entry at 0.20."""
        pnl = compute_unrealized_pnl(quantity=10, avg_entry_price=0.20, current_price=1.0)
        assert pnl == pytest.approx(8.0)

    def test_total_loss(self):
        """Market resolves NO (YES=0), entry at 0.80."""
        pnl = compute_unrealized_pnl(quantity=10, avg_entry_price=0.80, current_price=0.0)
        assert pnl == pytest.approx(-8.0)


class TestRealizedPnLFifo:
    def test_simple_open_close(self):
        """Open 10 YES at 0.40, close at 0.60 → P&L = 10 * 0.20 = 2.0."""
        trades = [
            {"market_id": "m1", "side": "YES", "action": "OPEN", "quantity": 10, "price": 0.40},
            {"market_id": "m1", "side": "YES", "action": "CLOSE", "quantity": 10, "price": 0.60},
        ]
        assert compute_realized_pnl_fifo(trades) == pytest.approx(2.0)

    def test_partial_close(self):
        """Open 10 at 0.40, close 5 at 0.60 → realized = 5 * 0.20 = 1.0."""
        trades = [
            {"market_id": "m1", "side": "YES", "action": "OPEN", "quantity": 10, "price": 0.40},
            {"market_id": "m1", "side": "YES", "action": "CLOSE", "quantity": 5, "price": 0.60},
        ]
        assert compute_realized_pnl_fifo(trades) == pytest.approx(1.0)

    def test_fifo_order(self):
        """Open 5 at 0.30, open 5 at 0.50, close 5 at 0.60 → FIFO uses 0.30 first."""
        trades = [
            {"market_id": "m1", "side": "YES", "action": "OPEN", "quantity": 5, "price": 0.30},
            {"market_id": "m1", "side": "YES", "action": "OPEN", "quantity": 5, "price": 0.50},
            {"market_id": "m1", "side": "YES", "action": "CLOSE", "quantity": 5, "price": 0.60},
        ]
        # FIFO: close against 0.30 lot → 5 * (0.60 - 0.30) = 1.50
        assert compute_realized_pnl_fifo(trades) == pytest.approx(1.5)

    def test_loss_trade(self):
        """Open at 0.80, close at 0.50 → loss."""
        trades = [
            {"market_id": "m1", "side": "YES", "action": "OPEN", "quantity": 10, "price": 0.80},
            {"market_id": "m1", "side": "YES", "action": "CLOSE", "quantity": 10, "price": 0.50},
        ]
        assert compute_realized_pnl_fifo(trades) == pytest.approx(-3.0)

    def test_no_closes(self):
        """Only opens, no realized P&L."""
        trades = [
            {"market_id": "m1", "side": "YES", "action": "OPEN", "quantity": 10, "price": 0.40},
        ]
        assert compute_realized_pnl_fifo(trades) == pytest.approx(0.0)

    def test_multiple_markets(self):
        """Two different markets with independent P&L."""
        trades = [
            {"market_id": "m1", "side": "YES", "action": "OPEN", "quantity": 10, "price": 0.40},
            {"market_id": "m2", "side": "NO", "action": "OPEN", "quantity": 5, "price": 0.30},
            {"market_id": "m1", "side": "YES", "action": "CLOSE", "quantity": 10, "price": 0.60},
            {"market_id": "m2", "side": "NO", "action": "CLOSE", "quantity": 5, "price": 0.20},
        ]
        # m1: 10 * (0.60 - 0.40) = 2.0
        # m2: 5 * (0.20 - 0.30) = -0.5
        assert compute_realized_pnl_fifo(trades) == pytest.approx(1.5)


class TestNearestSnapshotSelection:
    """Test the logic for selecting the nearest snapshot for pricing.

    Since _nearest_snapshot is an ES query, we test the selection logic
    conceptually: given a sorted list of snapshots, pick the right one.
    """

    def _select_nearest(self, snapshots: list[dict], target_ts=None):
        """Simulate nearest snapshot selection: latest at or before target_ts."""
        if not snapshots:
            return None
        if target_ts is None:
            return snapshots[-1]  # latest
        candidates = [s for s in snapshots if s["ts"] <= target_ts]
        return candidates[-1] if candidates else None

    def test_latest_when_no_timestamp(self):
        snaps = [{"ts": 1, "price": 0.5}, {"ts": 2, "price": 0.6}, {"ts": 3, "price": 0.7}]
        result = self._select_nearest(snaps)
        assert result["price"] == 0.7

    def test_exact_match(self):
        snaps = [{"ts": 1, "price": 0.5}, {"ts": 2, "price": 0.6}, {"ts": 3, "price": 0.7}]
        result = self._select_nearest(snaps, target_ts=2)
        assert result["price"] == 0.6

    def test_before_target(self):
        snaps = [{"ts": 1, "price": 0.5}, {"ts": 3, "price": 0.7}]
        result = self._select_nearest(snaps, target_ts=2)
        assert result["price"] == 0.5

    def test_no_earlier_snapshot(self):
        snaps = [{"ts": 5, "price": 0.5}]
        result = self._select_nearest(snaps, target_ts=2)
        assert result is None

    def test_empty_snapshots(self):
        result = self._select_nearest([], target_ts=2)
        assert result is None
