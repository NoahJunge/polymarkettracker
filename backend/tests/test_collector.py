"""Tests for collector snapshot building and market normalization."""

import pytest

from utils.filters import normalize_yes_no_prices


class TestSnapshotBuilding:
    """Test the snapshot document construction logic."""

    def _build_snapshot(self, yes_price: float, no_price: float) -> dict:
        """Simulate building a snapshot doc from prices."""
        return {
            "yes_price": round(yes_price, 6),
            "no_price": round(no_price, 6),
            "yes_cents": round(yes_price * 100),
            "no_cents": round(no_price * 100),
            "spread": round(abs(yes_price - no_price), 6),
        }

    def test_standard_prices(self):
        snap = self._build_snapshot(0.65, 0.35)
        assert snap["yes_cents"] == 65
        assert snap["no_cents"] == 35
        assert snap["spread"] == pytest.approx(0.3)

    def test_high_confidence(self):
        snap = self._build_snapshot(0.95, 0.05)
        assert snap["yes_cents"] == 95
        assert snap["no_cents"] == 5
        assert snap["spread"] == pytest.approx(0.9)

    def test_even_split(self):
        snap = self._build_snapshot(0.50, 0.50)
        assert snap["yes_cents"] == 50
        assert snap["no_cents"] == 50
        assert snap["spread"] == pytest.approx(0.0)

    def test_rounding(self):
        snap = self._build_snapshot(0.666, 0.334)
        assert snap["yes_cents"] == 67
        assert snap["no_cents"] == 33
        assert snap["yes_price"] == 0.666
        assert snap["no_price"] == 0.334

    def test_extreme_values(self):
        snap = self._build_snapshot(0.99, 0.01)
        assert snap["yes_cents"] == 99
        assert snap["no_cents"] == 1

    def test_zero_price(self):
        snap = self._build_snapshot(1.0, 0.0)
        assert snap["yes_cents"] == 100
        assert snap["no_cents"] == 0
        assert snap["spread"] == pytest.approx(1.0)


class TestOutcomePriceNormalization:
    """Test that we correctly map outcome prices to yes/no regardless of API order."""

    def test_yes_first_order(self):
        outcomes = ["Yes", "No"]
        prices = ["0.70", "0.30"]
        yes_p, no_p = normalize_yes_no_prices(outcomes, prices)
        assert yes_p == 0.70
        assert no_p == 0.30

    def test_no_first_order(self):
        outcomes = ["No", "Yes"]
        prices = ["0.30", "0.70"]
        yes_p, no_p = normalize_yes_no_prices(outcomes, prices)
        assert yes_p == 0.70
        assert no_p == 0.30

    def test_float_prices(self):
        outcomes = ["Yes", "No"]
        prices = [0.55, 0.45]
        yes_p, no_p = normalize_yes_no_prices(outcomes, prices)
        assert yes_p == 0.55
        assert no_p == 0.45
