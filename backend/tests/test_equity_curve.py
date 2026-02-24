"""Tests for equity curve computation and portfolio statistics."""

import pytest
from collections import defaultdict

from services.paper_trading_service import PaperTradingService
from models.paper_trade import EquityCurvePoint, PortfolioStats


class TestComputeEquityCurve:
    """Test _compute_equity_curve static method with mark-to-market pricing."""

    def test_empty_trades(self):
        result = PaperTradingService._compute_equity_curve([], {})
        assert result == []

    def test_single_open_no_price_change(self):
        """One OPEN trade with same snapshot price → unrealized P&L = 0."""
        trades = [
            {"market_id": "m1", "side": "YES", "action": "OPEN",
             "quantity": 10, "price": 0.40, "created_at_utc": "2026-01-15T12:00:00Z"},
        ]
        daily_prices = {
            "2026-01-15": {"m1": {"yes_price": 0.40, "no_price": 0.60}},
        }
        curve = PaperTradingService._compute_equity_curve(trades, daily_prices)
        assert len(curve) == 1
        assert curve[0].date == "2026-01-15"
        assert curve[0].cumulative_invested == pytest.approx(4.0)
        assert curve[0].total_pnl == pytest.approx(0.0)
        assert curve[0].unrealized_pnl == pytest.approx(0.0)
        assert curve[0].portfolio_value == pytest.approx(4.0)
        assert curve[0].total_open_trades == 1
        assert curve[0].total_close_trades == 0

    def test_unrealized_gain(self):
        """Price goes up → positive unrealized P&L."""
        trades = [
            {"market_id": "m1", "side": "YES", "action": "OPEN",
             "quantity": 10, "price": 0.40, "created_at_utc": "2026-01-15T12:00:00Z"},
        ]
        daily_prices = {
            "2026-01-15": {"m1": {"yes_price": 0.40, "no_price": 0.60}},
            "2026-01-16": {"m1": {"yes_price": 0.60, "no_price": 0.40}},
        }
        curve = PaperTradingService._compute_equity_curve(trades, daily_prices)
        assert len(curve) == 2
        # Day 1: price unchanged
        assert curve[0].total_pnl == pytest.approx(0.0)
        assert curve[0].portfolio_value == pytest.approx(4.0)
        # Day 2: price up to 0.60, unrealized = 10*(0.60-0.40) = 2.0
        assert curve[1].total_pnl == pytest.approx(2.0)
        assert curve[1].unrealized_pnl == pytest.approx(2.0)
        assert curve[1].portfolio_value == pytest.approx(6.0)

    def test_unrealized_loss(self):
        """Price goes down → negative unrealized P&L."""
        trades = [
            {"market_id": "m1", "side": "YES", "action": "OPEN",
             "quantity": 10, "price": 0.80, "created_at_utc": "2026-01-10T12:00:00Z"},
        ]
        daily_prices = {
            "2026-01-10": {"m1": {"yes_price": 0.80, "no_price": 0.20}},
            "2026-01-11": {"m1": {"yes_price": 0.50, "no_price": 0.50}},
        }
        curve = PaperTradingService._compute_equity_curve(trades, daily_prices)
        # Day 2: unrealized = 10*(0.50-0.80) = -3.0
        assert curve[1].total_pnl == pytest.approx(-3.0)
        assert curve[1].unrealized_pnl == pytest.approx(-3.0)

    def test_multi_day_price_movement(self):
        """Price changes across multiple days produce daily curve updates."""
        trades = [
            {"market_id": "m1", "side": "YES", "action": "OPEN",
             "quantity": 10, "price": 0.40, "created_at_utc": "2026-01-10T12:00:00Z"},
        ]
        daily_prices = {
            "2026-01-10": {"m1": {"yes_price": 0.40, "no_price": 0.60}},
            "2026-01-11": {"m1": {"yes_price": 0.50, "no_price": 0.50}},
            "2026-01-12": {"m1": {"yes_price": 0.45, "no_price": 0.55}},
        }
        curve = PaperTradingService._compute_equity_curve(trades, daily_prices)
        assert len(curve) == 3
        assert curve[0].total_pnl == pytest.approx(0.0)   # 0.40 → 0.40
        assert curve[1].total_pnl == pytest.approx(1.0)   # 10*(0.50-0.40)
        assert curve[2].total_pnl == pytest.approx(0.5)   # 10*(0.45-0.40)

    def test_no_side(self):
        """NO side uses no_price for mark-to-market."""
        trades = [
            {"market_id": "m1", "side": "NO", "action": "OPEN",
             "quantity": 10, "price": 0.60, "created_at_utc": "2026-01-10T12:00:00Z"},
        ]
        daily_prices = {
            "2026-01-10": {"m1": {"yes_price": 0.40, "no_price": 0.60}},
            "2026-01-11": {"m1": {"yes_price": 0.30, "no_price": 0.70}},
        }
        curve = PaperTradingService._compute_equity_curve(trades, daily_prices)
        # NO price went 0.60 → 0.70, unrealized = 10*(0.70-0.60) = 1.0
        assert curve[1].total_pnl == pytest.approx(1.0)

    def test_multiple_markets(self):
        """Positions across markets are valued independently."""
        trades = [
            {"market_id": "m1", "side": "YES", "action": "OPEN",
             "quantity": 10, "price": 0.40, "created_at_utc": "2026-01-10T12:00:00Z"},
            {"market_id": "m2", "side": "NO", "action": "OPEN",
             "quantity": 5, "price": 0.30, "created_at_utc": "2026-01-10T13:00:00Z"},
        ]
        daily_prices = {
            "2026-01-10": {
                "m1": {"yes_price": 0.40, "no_price": 0.60},
                "m2": {"yes_price": 0.70, "no_price": 0.30},
            },
            "2026-01-11": {
                "m1": {"yes_price": 0.60, "no_price": 0.40},
                "m2": {"yes_price": 0.80, "no_price": 0.20},
            },
        }
        curve = PaperTradingService._compute_equity_curve(trades, daily_prices)
        # m1 YES: 10*(0.60-0.40) = 2.0
        # m2 NO:  5*(0.20-0.30) = -0.5
        assert curve[1].total_pnl == pytest.approx(1.5)

    def test_close_trade_realized_plus_unrealized(self):
        """Closed trades contribute realized P&L; open ones contribute unrealized."""
        trades = [
            {"market_id": "m1", "side": "YES", "action": "OPEN",
             "quantity": 10, "price": 0.40, "created_at_utc": "2026-01-10T12:00:00Z"},
            {"market_id": "m1", "side": "YES", "action": "CLOSE",
             "quantity": 5, "price": 0.60, "created_at_utc": "2026-01-11T12:00:00Z"},
        ]
        daily_prices = {
            "2026-01-10": {"m1": {"yes_price": 0.40, "no_price": 0.60}},
            "2026-01-11": {"m1": {"yes_price": 0.60, "no_price": 0.40}},
        }
        curve = PaperTradingService._compute_equity_curve(trades, daily_prices)
        # Day 2: realized = 5*(0.60-0.40)=1.0, remaining 5 shares unrealized = 5*(0.60-0.40)=1.0
        assert curve[1].realized_pnl == pytest.approx(1.0)
        assert curve[1].unrealized_pnl == pytest.approx(1.0)
        assert curve[1].total_pnl == pytest.approx(2.0)

    def test_price_carry_forward(self):
        """If no snapshot for a date, last known price carries forward."""
        trades = [
            {"market_id": "m1", "side": "YES", "action": "OPEN",
             "quantity": 10, "price": 0.40, "created_at_utc": "2026-01-10T12:00:00Z"},
        ]
        daily_prices = {
            "2026-01-10": {"m1": {"yes_price": 0.50, "no_price": 0.50}},
            # No data on 2026-01-11 — price should carry forward
            "2026-01-12": {"m1": {"yes_price": 0.60, "no_price": 0.40}},
        }
        curve = PaperTradingService._compute_equity_curve(trades, daily_prices)
        # 3 dates: 10, 11 (from trades_by_date empty but daily_prices missing),
        # actually only 10 and 12 in all_dates since 11 has neither trade nor price
        assert len(curve) == 2
        assert curve[0].total_pnl == pytest.approx(1.0)  # 10*(0.50-0.40)
        assert curve[1].total_pnl == pytest.approx(2.0)  # 10*(0.60-0.40)


class TestComputePortfolioStats:
    """Test _compute_portfolio_stats static method."""

    def _make_curve(self, total_pnl_values):
        """Helper to build a minimal curve from a list of total P&L values."""
        curve = []
        for i, pnl in enumerate(total_pnl_values):
            curve.append(EquityCurvePoint(
                date=f"2026-01-{10 + i:02d}",
                total_pnl=pnl,
                unrealized_pnl=pnl,
                realized_pnl=0.0,
                cumulative_invested=10.0,
                portfolio_value=10.0 + pnl,
                total_open_trades=i + 1,
                total_close_trades=0,
            ))
        return curve

    def test_empty_trades(self):
        stats = PaperTradingService._compute_portfolio_stats([], [])
        assert stats.win_rate is None
        assert stats.profit_factor is None

    def test_win_rate(self):
        """3 wins out of 4 closes = 75%."""
        trades = [
            {"market_id": "m1", "side": "YES", "action": "OPEN", "quantity": 10, "price": 0.40, "created_at_utc": "2026-01-10T00:00:00Z"},
            {"market_id": "m2", "side": "YES", "action": "OPEN", "quantity": 10, "price": 0.40, "created_at_utc": "2026-01-10T00:00:00Z"},
            {"market_id": "m3", "side": "YES", "action": "OPEN", "quantity": 10, "price": 0.40, "created_at_utc": "2026-01-10T00:00:00Z"},
            {"market_id": "m4", "side": "YES", "action": "OPEN", "quantity": 10, "price": 0.40, "created_at_utc": "2026-01-10T00:00:00Z"},
            {"market_id": "m1", "side": "YES", "action": "CLOSE", "quantity": 10, "price": 0.60, "created_at_utc": "2026-01-11T00:00:00Z"},
            {"market_id": "m2", "side": "YES", "action": "CLOSE", "quantity": 10, "price": 0.50, "created_at_utc": "2026-01-11T00:00:00Z"},
            {"market_id": "m3", "side": "YES", "action": "CLOSE", "quantity": 10, "price": 0.55, "created_at_utc": "2026-01-11T00:00:00Z"},
            {"market_id": "m4", "side": "YES", "action": "CLOSE", "quantity": 10, "price": 0.30, "created_at_utc": "2026-01-11T00:00:00Z"},
        ]
        curve = self._make_curve([0.0, 2.5])
        stats = PaperTradingService._compute_portfolio_stats(trades, curve)
        assert stats.win_rate == 75.0
        assert stats.total_wins == 3
        assert stats.total_losses == 1

    def test_profit_factor(self):
        """Profit factor = total wins / total losses."""
        trades = [
            {"market_id": "m1", "side": "YES", "action": "OPEN", "quantity": 10, "price": 0.40, "created_at_utc": "2026-01-10T00:00:00Z"},
            {"market_id": "m2", "side": "YES", "action": "OPEN", "quantity": 10, "price": 0.60, "created_at_utc": "2026-01-10T00:00:00Z"},
            {"market_id": "m1", "side": "YES", "action": "CLOSE", "quantity": 10, "price": 0.60, "created_at_utc": "2026-01-11T00:00:00Z"},
            {"market_id": "m2", "side": "YES", "action": "CLOSE", "quantity": 10, "price": 0.50, "created_at_utc": "2026-01-11T00:00:00Z"},
        ]
        curve = self._make_curve([0.0, 1.0])
        stats = PaperTradingService._compute_portfolio_stats(trades, curve)
        assert stats.profit_factor == pytest.approx(2.0)

    def test_max_drawdown(self):
        """Max drawdown is the largest peak-to-trough decline in total P&L."""
        # total_pnl: 1, 3, 2, 0, 4 → max drawdown = 3 (peak 3 to trough 0)
        curve = self._make_curve([1.0, 3.0, 2.0, 0.0, 4.0])
        stats = PaperTradingService._compute_portfolio_stats([], curve)
        assert stats.max_drawdown == pytest.approx(3.0)

    def test_max_drawdown_no_drawdown(self):
        """Monotonically increasing curve has 0 drawdown."""
        curve = self._make_curve([1.0, 2.0, 3.0])
        stats = PaperTradingService._compute_portfolio_stats([], curve)
        assert stats.max_drawdown == pytest.approx(0.0)

    def test_sharpe_ratio(self):
        """Sharpe = mean(daily P&L changes) / std(daily P&L changes)."""
        import numpy as np
        # total_pnl values: 0, 1, 3, 4.5, 5, 7
        # daily changes: 1, 2, 1.5, 0.5, 2
        pnl_values = [0.0, 1.0, 3.0, 4.5, 5.0, 7.0]
        curve = self._make_curve(pnl_values)
        stats = PaperTradingService._compute_portfolio_stats([], curve)
        daily_changes = [1.0, 2.0, 1.5, 0.5, 2.0]
        arr = np.array(daily_changes)
        expected_sharpe = float(np.mean(arr) / np.std(arr, ddof=1))
        assert stats.sharpe_ratio == pytest.approx(expected_sharpe, rel=1e-3)

    def test_regression_significant_uptrend(self):
        """Strongly increasing total P&L → significant upward trend."""
        curve = self._make_curve([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        stats = PaperTradingService._compute_portfolio_stats([], curve)
        assert stats.trend_significant is True
        assert stats.trend_direction == "up"
        assert stats.regression_slope > 0
        assert stats.regression_p_value < 0.05
        assert stats.regression_r_squared > 0.9

    def test_regression_no_data(self):
        """With fewer than 3 points, no regression is computed."""
        curve = self._make_curve([1.0, 2.0])
        stats = PaperTradingService._compute_portfolio_stats([], curve)
        assert stats.regression_slope is None
        assert stats.trend_significant is False

    def test_no_closes_no_win_rate(self):
        """Only opens, no closes → win rate not computed."""
        trades = [
            {"market_id": "m1", "side": "YES", "action": "OPEN", "quantity": 10, "price": 0.40, "created_at_utc": "2026-01-10T00:00:00Z"},
        ]
        curve = self._make_curve([0.0])
        stats = PaperTradingService._compute_portfolio_stats(trades, curve)
        assert stats.win_rate is None
        assert stats.total_wins == 0
        assert stats.total_losses == 0

    def test_avg_win_and_loss(self):
        """Average win and average loss computed from individual close P&Ls."""
        trades = [
            {"market_id": "m1", "side": "YES", "action": "OPEN", "quantity": 10, "price": 0.40, "created_at_utc": "2026-01-10T00:00:00Z"},
            {"market_id": "m2", "side": "YES", "action": "OPEN", "quantity": 10, "price": 0.60, "created_at_utc": "2026-01-10T00:00:00Z"},
            {"market_id": "m1", "side": "YES", "action": "CLOSE", "quantity": 10, "price": 0.60, "created_at_utc": "2026-01-11T00:00:00Z"},
            {"market_id": "m2", "side": "YES", "action": "CLOSE", "quantity": 10, "price": 0.50, "created_at_utc": "2026-01-11T00:00:00Z"},
        ]
        curve = self._make_curve([0.0, 1.0])
        stats = PaperTradingService._compute_portfolio_stats(trades, curve)
        assert stats.avg_win == pytest.approx(2.0)
        assert stats.avg_loss == pytest.approx(-1.0)
