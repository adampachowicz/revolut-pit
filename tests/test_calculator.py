"""Tests for tax calculator."""

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from revolut_pit.calculator import TaxCalculator
from revolut_pit.nbp import NBPClient


class TestTaxCalculator:
    """Test FIFO capital gains calculator."""

    @pytest.fixture
    def calculator(self):
        """Create calculator with mock NBP."""
        nbp = MagicMock(spec=NBPClient)
        # Default rates for testing
        nbp.get_rate.return_value = Decimal("4.00")
        return TaxCalculator(nbp)

    def test_t2_1_single_buy_sell(self, calculator):
        """T2.1: Single buy → single sell"""
        buy_date = datetime(2025, 1, 15)
        sell_date = datetime(2025, 6, 20)

        calculator.nbp.get_rate.side_effect = [
            Decimal("4.00"),  # Buy rate
            Decimal("4.10"),  # Sell rate
        ]

        calculator.add_buy(
            "AAPL", Decimal("10"), Decimal("150"), "USD", buy_date, asset_type="stock"
        )

        result = calculator.calculate_sell(
            "AAPL", Decimal("10"), Decimal("160"), "USD", sell_date, asset_type="stock"
        )

        assert result["symbol"] == "AAPL"
        assert result["quantity"] == Decimal("10")
        # cost = 10 * 150 * 4.00 = 6000
        assert result["cost_basis_pln"] == Decimal("6000.00")
        # proceeds = 10 * 160 * 4.10 = 6560
        assert result["proceeds_pln"] == Decimal("6560.00")
        # gain = 6560 - 6000 = 560
        assert result["gain_pln"] == Decimal("560.00")

    def test_t2_2_multiple_buys_fifo(self, calculator):
        """T2.2: Multiple buys → one sell, FIFO order"""
        calculator.nbp.get_rate.return_value = Decimal("4.00")

        # Buy 5 at 100
        calculator.add_buy(
            "MSFT", Decimal("5"), Decimal("100"), "USD", datetime(2025, 1, 1)
        )
        # Buy 5 at 110
        calculator.add_buy(
            "MSFT", Decimal("5"), Decimal("110"), "USD", datetime(2025, 2, 1)
        )

        # Sell 7 (should use 5 @ 100 + 2 @ 110)
        result = calculator.calculate_sell(
            "MSFT", Decimal("7"), Decimal("120"), "USD", datetime(2025, 6, 1)
        )

        assert result["quantity"] == Decimal("7")
        # cost = (5 * 100 + 2 * 110) * 4.00 = 2880
        assert result["cost_basis_pln"] == Decimal("2880.00")
        # proceeds = 7 * 120 * 4.00 = 3360
        assert result["proceeds_pln"] == Decimal("3360.00")
        # gain = 480
        assert result["gain_pln"] == Decimal("480.00")

        # Check FIFO order in trades
        assert len(result["trades"]) == 2
        assert result["trades"][0]["quantity"] == Decimal("5")  # First lot
        assert result["trades"][1]["quantity"] == Decimal("2")  # Partial second lot

    def test_t2_3_partial_sale(self, calculator):
        """T2.3: Partial sale leaves remainder in FIFO."""
        calculator.nbp.get_rate.return_value = Decimal("4.00")

        calculator.add_buy("TSLA", Decimal("100"), Decimal("200"), "USD", datetime(2025, 1, 1))
        calculator.calculate_sell(
            "TSLA", Decimal("60"), Decimal("250"), "USD", datetime(2025, 6, 1)
        )

        # 40 units should remain
        fifo = calculator.stock_fifo["TSLA"]
        assert len(fifo) == 1
        assert fifo[0]["quantity"] == Decimal("40")

    def test_t2_4_different_years_different_rates(self, calculator):
        """T2.4: Buy 2024, sell 2025 — different NBP rates per leg"""
        buy_rate = Decimal("3.90")
        sell_rate = Decimal("4.15")

        calculator.nbp.get_rate.side_effect = [buy_rate, sell_rate]

        calculator.add_buy(
            "GOOG", Decimal("10"), Decimal("140"), "USD", datetime(2024, 12, 15)
        )

        result = calculator.calculate_sell(
            "GOOG", Decimal("10"), Decimal("155"), "USD", datetime(2025, 1, 15)
        )

        # cost = 10 * 140 * 3.90 = 5460
        assert result["cost_basis_pln"] == Decimal("5460.00")
        # proceeds = 10 * 155 * 4.15 = 6432.50
        assert result["proceeds_pln"] == Decimal("6432.50")
        # gain = 972.50
        assert result["gain_pln"] == Decimal("972.50")

    def test_t2_5_stock_split(self, calculator):
        """T2.5: Stock split (10:1) — quantity ×10, cost ÷10"""
        calculator.nbp.get_rate.return_value = Decimal("4.00")

        # Buy 10 shares at 100
        calculator.add_buy(
            "SPLIT", Decimal("10"), Decimal("100"), "USD", datetime(2025, 1, 1)
        )

        # Simulate 10:1 split: manually adjust FIFO
        split_lot = calculator.stock_fifo["SPLIT"][0]
        split_lot["quantity"] *= 10
        split_lot["cost_per_unit"] /= 10

        # Sell 50 shares (5 of original)
        result = calculator.calculate_sell(
            "SPLIT", Decimal("50"), Decimal("15"), "USD", datetime(2025, 6, 1)
        )

        assert result["quantity"] == Decimal("50")
        # cost = 50 * 10 * 4.00 = 2000
        assert result["cost_basis_pln"] == Decimal("2000.00")

    def test_t2_6_commission_in_cost(self, calculator):
        """T2.6: Commission/fee added to cost (or subtracted from proceeds)."""
        calculator.nbp.get_rate.return_value = Decimal("4.00")

        # Buy 10 at 100 + 10 USD commission
        cost_per_unit = Decimal("100") + (Decimal("10") / Decimal("10"))
        calculator.add_buy("COMMISION", Decimal("10"), cost_per_unit, "USD", datetime(2025, 1, 1))

        result = calculator.calculate_sell(
            "COMMISION", Decimal("10"), Decimal("120"), "USD", datetime(2025, 6, 1)
        )

        # cost should include commission
        assert result["cost_basis_pln"] > Decimal("4000.00")

    def test_t2_7_open_position_no_tax(self, calculator):
        """T2.7: Open position at year-end → no taxable event"""
        calculator.nbp.get_rate.return_value = Decimal("4.00")

        calculator.add_buy("OPEN", Decimal("100"), Decimal("50"), "USD", datetime(2025, 1, 1))

        # Never sell it - should not throw error
        fifo = calculator.stock_fifo["OPEN"]
        assert len(fifo) == 1
        assert fifo[0]["quantity"] == Decimal("100")

    def test_t2_8_loss_transaction(self, calculator):
        """T2.8: Loss on transaction (sold below cost)"""
        calculator.nbp.get_rate.return_value = Decimal("4.00")

        calculator.add_buy("LOSS", Decimal("10"), Decimal("100"), "USD", datetime(2025, 1, 1))

        result = calculator.calculate_sell(
            "LOSS", Decimal("10"), Decimal("90"), "USD", datetime(2025, 6, 1)
        )

        # cost = 4000, proceeds = 3600, loss = -400
        assert result["gain_pln"] == Decimal("-400.00")

    def test_t2_9_crypto_separate_fifo(self, calculator):
        """T2.9: Crypto FIFO bucket separate from stocks"""
        calculator.nbp.get_rate.return_value = Decimal("1.00")  # For crypto

        calculator.add_buy(
            "BTC", Decimal("1"), Decimal("50000"), "USD", datetime(2025, 1, 1), asset_type="crypto"
        )
        calculator.add_buy(
            "BTC", Decimal("0.5"), Decimal("60000"), "USD", datetime(2025, 2, 1), asset_type="crypto"
        )

        result = calculator.calculate_sell(
            "BTC", Decimal("1"), Decimal("65000"), "USD", datetime(2025, 6, 1), asset_type="crypto"
        )

        assert result["quantity"] == Decimal("1")
        # FIFO: 1 BTC @ 50k
        assert result["cost_basis_pln"] == Decimal("50000.00")
        assert result["proceeds_pln"] == Decimal("65000.00")
        assert result["gain_pln"] == Decimal("15000.00")

    def test_t2_10_dividend_with_wht(self, calculator):
        """T2.10: Dividend with US WHT 15% (covered in dividends module)"""
        # This is tested in test_dividends.py
        pass

    def test_rounding_to_grosz(self, calculator):
        """Verify rounding to 2 decimal places (grosz) with .5 rounding up"""
        assert calculator.round_to_grosz(Decimal("1.234")) == Decimal("1.23")
        assert calculator.round_to_grosz(Decimal("1.235")) == Decimal("1.24")
        assert calculator.round_to_grosz(Decimal("1.245")) == Decimal("1.25")
