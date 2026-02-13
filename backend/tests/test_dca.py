"""Unit tests for DCA service logic — pure computation, no ES dependency."""

import pytest
from collections import OrderedDict

from services.dca_service import (
    group_snapshots_by_day,
    build_backfill_trades,
    compute_dca_analytics,
)


# --- group_snapshots_by_day ---


class TestGroupSnapshotsByDay:
    def test_single_snapshot_per_day(self):
        snapshots = [
            {"timestamp_utc": "2025-01-01T10:00:00Z", "yes_price": 0.5, "no_price": 0.5},
            {"timestamp_utc": "2025-01-02T10:00:00Z", "yes_price": 0.6, "no_price": 0.4},
            {"timestamp_utc": "2025-01-03T10:00:00Z", "yes_price": 0.7, "no_price": 0.3},
        ]
        result = group_snapshots_by_day(snapshots)
        assert len(result) == 3
        assert list(result.keys()) == ["2025-01-01", "2025-01-02", "2025-01-03"]

    def test_multiple_snapshots_per_day_picks_first(self):
        snapshots = [
            {"timestamp_utc": "2025-01-01T08:00:00Z", "yes_price": 0.50, "no_price": 0.50},
            {"timestamp_utc": "2025-01-01T12:00:00Z", "yes_price": 0.55, "no_price": 0.45},
            {"timestamp_utc": "2025-01-01T18:00:00Z", "yes_price": 0.60, "no_price": 0.40},
            {"timestamp_utc": "2025-01-02T09:00:00Z", "yes_price": 0.65, "no_price": 0.35},
        ]
        result = group_snapshots_by_day(snapshots)
        assert len(result) == 2
        # First snapshot of Jan 1 is the 08:00 one
        assert result["2025-01-01"]["yes_price"] == 0.50
        assert result["2025-01-02"]["yes_price"] == 0.65

    def test_empty_snapshots(self):
        result = group_snapshots_by_day([])
        assert len(result) == 0

    def test_preserves_order(self):
        snapshots = [
            {"timestamp_utc": "2025-01-05T10:00:00Z", "yes_price": 0.5, "no_price": 0.5},
            {"timestamp_utc": "2025-01-03T10:00:00Z", "yes_price": 0.6, "no_price": 0.4},
            {"timestamp_utc": "2025-01-07T10:00:00Z", "yes_price": 0.7, "no_price": 0.3},
        ]
        result = group_snapshots_by_day(snapshots)
        # OrderedDict preserves insertion order (which matches input order)
        assert list(result.keys()) == ["2025-01-05", "2025-01-03", "2025-01-07"]


# --- build_backfill_trades ---


class TestBuildBackfillTrades:
    def test_creates_correct_number_of_trades(self):
        daily = OrderedDict()
        daily["2025-01-01"] = {"timestamp_utc": "2025-01-01T10:00:00Z", "yes_price": 0.50, "no_price": 0.50}
        daily["2025-01-02"] = {"timestamp_utc": "2025-01-02T10:00:00Z", "yes_price": 0.60, "no_price": 0.40}
        daily["2025-01-03"] = {"timestamp_utc": "2025-01-03T10:00:00Z", "yes_price": 0.70, "no_price": 0.30}

        trades = build_backfill_trades("dca-123", "market-abc", "YES", 5.0, daily)
        assert len(trades) == 3

    def test_yes_side_uses_yes_price(self):
        daily = OrderedDict()
        daily["2025-01-01"] = {"timestamp_utc": "2025-01-01T10:00:00Z", "yes_price": 0.42, "no_price": 0.58}

        trades = build_backfill_trades("dca-1", "m1", "YES", 10.0, daily)
        assert trades[0]["price"] == 0.42
        assert trades[0]["side"] == "YES"

    def test_no_side_uses_no_price(self):
        daily = OrderedDict()
        daily["2025-01-01"] = {"timestamp_utc": "2025-01-01T10:00:00Z", "yes_price": 0.42, "no_price": 0.58}

        trades = build_backfill_trades("dca-1", "m1", "NO", 10.0, daily)
        assert trades[0]["price"] == 0.58
        assert trades[0]["side"] == "NO"

    def test_trade_fields(self):
        daily = OrderedDict()
        daily["2025-01-01"] = {"timestamp_utc": "2025-01-01T10:00:00Z", "yes_price": 0.50, "no_price": 0.50}

        trades = build_backfill_trades("dca-abc", "market-xyz", "YES", 3.0, daily)
        t = trades[0]
        assert t["market_id"] == "market-xyz"
        assert t["side"] == "YES"
        assert t["action"] == "OPEN"
        assert t["quantity"] == 3.0
        assert t["price"] == 0.50
        assert t["metadata"] == {"dca": True, "dca_id": "dca-abc"}
        assert t["fees"] == 0.0
        assert "trade_id" in t
        assert t["snapshot_ts_utc"] == "2025-01-01T10:00:00Z"

    def test_empty_daily_returns_empty(self):
        trades = build_backfill_trades("dca-1", "m1", "YES", 1.0, OrderedDict())
        assert trades == []


# --- compute_dca_analytics ---


class TestComputeDcaAnalytics:
    def test_basic_analytics(self):
        trades = [
            {"quantity": 10, "price": 0.40, "created_at_utc": "2025-01-01T10:00:00Z"},
            {"quantity": 10, "price": 0.50, "created_at_utc": "2025-01-02T10:00:00Z"},
            {"quantity": 10, "price": 0.60, "created_at_utc": "2025-01-03T10:00:00Z"},
        ]
        result = compute_dca_analytics(
            dca_id="dca-1",
            market_id="m1",
            side="YES",
            quantity_per_day=10,
            trades=trades,
            current_price=0.70,
        )
        assert result.total_trades == 3
        assert result.total_shares == 30
        # total_invested = 10*0.4 + 10*0.5 + 10*0.6 = 15.0
        assert result.total_invested == 15.0
        # avg_entry = 15.0 / 30 = 0.5
        assert result.avg_entry_price == 0.5
        # current_value = 30 * 0.70 = 21.0
        assert result.current_value == 21.0
        # pnl = 21.0 - 15.0 = 6.0
        assert result.unrealized_pnl == 6.0
        # pnl% = 6.0 / 15.0 * 100 = 40.0
        assert result.unrealized_pnl_pct == 40.0

    def test_negative_pnl(self):
        trades = [
            {"quantity": 10, "price": 0.80, "created_at_utc": "2025-01-01T10:00:00Z"},
            {"quantity": 10, "price": 0.70, "created_at_utc": "2025-01-02T10:00:00Z"},
        ]
        result = compute_dca_analytics(
            dca_id="dca-2",
            market_id="m2",
            side="YES",
            quantity_per_day=10,
            trades=trades,
            current_price=0.50,
        )
        assert result.total_invested == 15.0  # 8 + 7
        assert result.current_value == 10.0   # 20 * 0.50
        assert result.unrealized_pnl == -5.0
        assert result.unrealized_pnl_pct == pytest.approx(-33.33, abs=0.01)

    def test_empty_trades(self):
        result = compute_dca_analytics(
            dca_id="dca-3",
            market_id="m3",
            side="YES",
            quantity_per_day=1,
            trades=[],
            current_price=0.50,
        )
        assert result.total_trades == 0
        assert result.total_shares == 0
        assert result.total_invested == 0
        assert result.unrealized_pnl == 0

    def test_single_trade(self):
        trades = [
            {"quantity": 1, "price": 0.50, "created_at_utc": "2025-06-15T12:00:00Z"},
        ]
        result = compute_dca_analytics(
            dca_id="dca-4",
            market_id="m4",
            side="NO",
            quantity_per_day=1,
            trades=trades,
            current_price=0.60,
        )
        assert result.total_trades == 1
        assert result.total_shares == 1
        assert result.total_invested == 0.50
        assert result.current_value == 0.60
        assert result.unrealized_pnl == pytest.approx(0.10, abs=0.001)
        assert result.first_trade_date == "2025-06-15"
        assert result.last_trade_date == "2025-06-15"

    def test_date_range(self):
        trades = [
            {"quantity": 1, "price": 0.40, "created_at_utc": "2025-01-10T10:00:00Z"},
            {"quantity": 1, "price": 0.45, "created_at_utc": "2025-01-15T10:00:00Z"},
            {"quantity": 1, "price": 0.50, "created_at_utc": "2025-01-20T10:00:00Z"},
        ]
        result = compute_dca_analytics(
            dca_id="dca-5",
            market_id="m5",
            side="YES",
            quantity_per_day=1,
            trades=trades,
            current_price=0.50,
        )
        assert result.first_trade_date == "2025-01-10"
        assert result.last_trade_date == "2025-01-20"

    def test_price_unchanged(self):
        trades = [
            {"quantity": 5, "price": 0.50, "created_at_utc": "2025-01-01T10:00:00Z"},
            {"quantity": 5, "price": 0.50, "created_at_utc": "2025-01-02T10:00:00Z"},
        ]
        result = compute_dca_analytics(
            dca_id="dca-6",
            market_id="m6",
            side="YES",
            quantity_per_day=5,
            trades=trades,
            current_price=0.50,
        )
        assert result.unrealized_pnl == 0.0
        assert result.unrealized_pnl_pct == 0.0
