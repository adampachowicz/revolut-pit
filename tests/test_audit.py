"""Tests for audit trail and validation functions."""

from decimal import Decimal
from datetime import datetime

import pytest

from revolut_pit.audit import (
    validate_fifo_against_revolut,
    cross_validate_stocks,
)


class TestFIFOValidation:
    """Test FIFO reconstruction and validation against Revolut P&L."""

    def test_validate_fifo_perfect_match(self):
        """Validate FIFO when our reconstruction matches Revolut P&L perfectly."""
        account_statement = [
            {"symbol": "AAPL", "type": "BUY", "quantity": Decimal("10"), "price": Decimal("100"), "date": "2025-01-01"},
            {"symbol": "AAPL", "type": "SELL", "quantity": Decimal("10"), "price": Decimal("150"), "date": "2025-06-01"},
        ]

        revolut_pnl = [
            {"symbol": "AAPL", "quantity": Decimal("10"), "cost_basis": Decimal("1000"), "proceeds": Decimal("1500"), "date_sold": "2025-06-01"},
        ]

        mismatches = validate_fifo_against_revolut(account_statement, revolut_pnl)

        assert len(mismatches) == 0

    def test_validate_fifo_quantity_mismatch(self):
        """Detect quantity mismatch in FIFO reconstruction."""
        account_statement = [
            {"symbol": "AAPL", "type": "BUY", "quantity": Decimal("10"), "price": Decimal("100"), "date": "2025-01-01"},
            {"symbol": "AAPL", "type": "SELL", "quantity": Decimal("8"), "price": Decimal("150"), "date": "2025-06-01"},
        ]

        revolut_pnl = [
            {"symbol": "AAPL", "quantity": Decimal("10"), "cost_basis": Decimal("1000"), "proceeds": Decimal("1500"), "date_sold": "2025-06-01"},
        ]

        mismatches = validate_fifo_against_revolut(account_statement, revolut_pnl)

        # Should detect quantity mismatch (and possibly cost basis)
        assert len(mismatches) >= 1
        qty_mismatch = [m for m in mismatches if m["type"] == "quantity_mismatch"]
        assert len(qty_mismatch) >= 1
        assert qty_mismatch[0]["revolut_value"] == Decimal("10")
        assert qty_mismatch[0]["our_value"] == Decimal("8")

    def test_validate_fifo_cost_basis_mismatch(self):
        """Detect cost basis mismatch in FIFO reconstruction."""
        account_statement = [
            {"symbol": "AAPL", "type": "BUY", "quantity": Decimal("10"), "price": Decimal("100"), "date": "2025-01-01"},
            {"symbol": "AAPL", "type": "BUY", "quantity": Decimal("5"), "price": Decimal("110"), "date": "2025-03-01"},
            # Sell 15: 10 @ 100 + 5 @ 110 = 1000 + 550 = 1550
            {"symbol": "AAPL", "type": "SELL", "quantity": Decimal("15"), "price": Decimal("150"), "date": "2025-06-01"},
        ]

        # Our FIFO would be: (10 × 100) + (5 × 110) = 1000 + 550 = 1550
        # But Revolut reports 1000
        revolut_pnl = [
            {"symbol": "AAPL", "quantity": Decimal("15"), "cost_basis": Decimal("1000"), "proceeds": Decimal("2250"), "date_sold": "2025-06-01"},
        ]

        mismatches = validate_fifo_against_revolut(account_statement, revolut_pnl)

        # Should detect cost basis mismatch
        cost_mismatch = [m for m in mismatches if m["type"] == "cost_basis_mismatch"]
        assert len(cost_mismatch) > 0
        assert cost_mismatch[0]["revolut_value"] == Decimal("1000")
        assert cost_mismatch[0]["our_value"] == Decimal("1550")

    def test_validate_fifo_multi_lot_partial(self):
        """Validate FIFO with partial lots."""
        account_statement = [
            {"symbol": "AAPL", "type": "BUY", "quantity": Decimal("5"), "price": Decimal("100"), "date": "2025-01-01"},
            {"symbol": "AAPL", "type": "BUY", "quantity": Decimal("5"), "price": Decimal("110"), "date": "2025-03-01"},
            # Sell 7: 5 @ 100 + 2 @ 110 = 500 + 220 = 720
            {"symbol": "AAPL", "type": "SELL", "quantity": Decimal("7"), "price": Decimal("150"), "date": "2025-06-01"},
        ]

        revolut_pnl = [
            {"symbol": "AAPL", "quantity": Decimal("7"), "cost_basis": Decimal("720"), "proceeds": Decimal("1050"), "date_sold": "2025-06-01"},
        ]

        mismatches = validate_fifo_against_revolut(account_statement, revolut_pnl)

        # Should match perfectly with correct FIFO calculation
        assert len(mismatches) == 0


class TestStocksVolumeWeightedValidation:
    """Test volume-weighted cross-validation of stocks."""

    def test_cross_validate_single_position(self):
        """Validate single position using volume-weighted rate."""
        closed_positions = [
            {
                "symbol": "AAPL",
                "proceeds_pln": Decimal("4000"),
                "proceeds_foreign": Decimal("1000"),
                "sell_rate_nbp": Decimal("4.0"),
            },
        ]

        drift, is_warning, message = cross_validate_stocks(closed_positions)

        # drift_pct = |1000 - 1000| / 1000 * 100 = 0 (no revolut total provided)
        assert drift == Decimal("0")
        assert "not provided" in message.lower()

    def test_cross_validate_multiple_positions_volume_weighted(self):
        """Validate multiple positions using volume-weighted rate."""
        closed_positions = [
            {
                "symbol": "AAPL",
                "proceeds_pln": Decimal("4000"),
                "proceeds_foreign": Decimal("1000"),
                "sell_rate_nbp": Decimal("4.0"),
            },
            {
                "symbol": "MSFT",
                "proceeds_pln": Decimal("4000"),
                "proceeds_foreign": Decimal("1000"),
                "sell_rate_nbp": Decimal("4.0"),
            },
        ]

        # Total: 8000 PLN / ((4000/4.0) + (4000/4.0)) = 8000 / 2000 = 4.0 (volume-weighted rate)
        drift, is_warning, message = cross_validate_stocks(closed_positions)

        assert drift == Decimal("0")
        assert "not provided" in message.lower()

    def test_cross_validate_with_revolut_data_small_drift(self):
        """Validate against Revolut data with small drift (< 0.5%)."""
        closed_positions = [
            {
                "symbol": "AAPL",
                "proceeds_pln": Decimal("4050"),
                "sell_rate_nbp": Decimal("4.05"),
            },
        ]

        revolut_totals = {
            "total_proceeds_foreign": Decimal("1000"),
        }

        drift, is_warning, message = cross_validate_stocks(closed_positions, revolut_totals)

        # Our calc: 4050 / 4.05 ≈ 1000
        # Drift: |1000 - 1000| / 1000 = 0%
        assert drift < Decimal("0.5")
        assert not is_warning

    def test_cross_validate_with_revolut_data_large_drift(self):
        """Validate against Revolut data with large drift (> 0.5%)."""
        closed_positions = [
            {
                "symbol": "AAPL",
                "proceeds_pln": Decimal("4050"),
                "sell_rate_nbp": Decimal("4.05"),
            },
        ]

        revolut_totals = {
            "total_proceeds_foreign": Decimal("900"),  # Significant difference
        }

        drift, is_warning, message = cross_validate_stocks(closed_positions, revolut_totals)

        # Our calc: 4050 / 4.05 ≈ 1000
        # Revolut: 900
        # Drift: |1000 - 900| / 900 = 11%
        assert drift > Decimal("0.5")
        assert is_warning
        assert "drift" in message.lower()

    def test_cross_validate_empty_positions(self):
        """Handle empty position list gracefully."""
        closed_positions = []

        drift, is_warning, message = cross_validate_stocks(closed_positions)

        assert drift == Decimal("0")
        assert not is_warning
        assert "no stock positions" in message.lower()

    def test_cross_validate_zero_proceeds(self):
        """Handle zero proceeds gracefully."""
        closed_positions = [
            {
                "symbol": "AAPL",
                "proceeds_pln": Decimal("0"),
                "sell_rate_nbp": Decimal("4.0"),
            },
        ]

        drift, is_warning, message = cross_validate_stocks(closed_positions)

        assert drift == Decimal("0")
        assert not is_warning
        assert "no proceeds" in message.lower()

    def test_cross_validate_no_rates(self):
        """Handle positions with no NBP rates gracefully."""
        closed_positions = [
            {
                "symbol": "AAPL",
                "proceeds_pln": Decimal("4000"),
                # Missing sell_rate_nbp
            },
        ]

        drift, is_warning, message = cross_validate_stocks(closed_positions)

        assert drift == Decimal("0")
        assert "no foreign proceeds" in message.lower()
