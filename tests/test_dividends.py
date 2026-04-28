"""Tests for dividend tax calculations."""

from decimal import Decimal

import pytest

from revolut_pit.dividends import DividendCalculator


class TestDividendCalculator:
    """Test dividend tax with foreign tax credit."""

    @pytest.fixture
    def calc(self):
        return DividendCalculator()

    def test_us_dividend_15_treaty(self, calc):
        """US dividend with 15% treaty rate."""
        result = calc.calculate_dividend(
            gross_pln=Decimal("1000"),
            wht_pln=Decimal("150"),
            country_code="US",
            symbol="AAPL",
        )

        assert result["gross_pln"] == Decimal("1000")
        assert result["wht_paid_pln"] == Decimal("150")
        assert result["polish_tax_19"] == Decimal("190.00")  # 19% of 1000
        assert result["treaty_rate"] == Decimal("0.15")
        assert result["treaty_cap"] == Decimal("150")  # 15% of 1000
        assert result["tax_credit"] == Decimal("150")  # min(150, 150)
        assert result["tax_to_pay"] == Decimal("40.00")  # 190 - 150

    def test_de_dividend_15_treaty(self, calc):
        """German dividend with 15% treaty rate."""
        result = calc.calculate_dividend(
            gross_pln=Decimal("500"),
            wht_pln=Decimal("75"),
            country_code="DE",
            symbol="SAP",
        )

        assert result["treaty_rate"] == Decimal("0.15")
        assert result["tax_to_pay"] == Decimal("20.00")  # (500 * 0.19) - 75

    def test_gb_dividend_10_treaty(self, calc):
        """UK dividend with 10% treaty rate."""
        result = calc.calculate_dividend(
            gross_pln=Decimal("1000"),
            wht_pln=Decimal("100"),
            country_code="GB",
            symbol="SHELL",
        )

        assert result["treaty_rate"] == Decimal("0.10")
        assert result["treaty_cap"] == Decimal("100")  # 10% of 1000
        assert result["tax_credit"] == Decimal("100")
        assert result["tax_to_pay"] == Decimal("90.00")  # (1000 * 0.19) - 100

    def test_unknown_country_default_15(self, calc):
        """Unknown country falls back to 15% treaty rate."""
        result = calc.calculate_dividend(
            gross_pln=Decimal("1000"),
            wht_pln=Decimal("150"),
            country_code="XX",
        )

        assert result["treaty_rate"] == Decimal("0.15")
        assert result["tax_to_pay"] == Decimal("40.00")

    def test_wht_exceeds_treaty_cap_warning(self, calc):
        """WHT paid exceeds treaty cap → warning issued."""
        result = calc.calculate_dividend(
            gross_pln=Decimal("1000"),
            wht_pln=Decimal("200"),  # Exceeds 15% treaty cap of 150
            country_code="US",
            symbol="AAPL",
        )

        assert result["wht_paid_pln"] == Decimal("200")
        assert result["treaty_cap"] == Decimal("150")
        assert result["tax_credit"] == Decimal("150")  # Capped at treaty
        assert result["warning"] is not None
        assert "W-8BEN" in result["warning"]

    def test_zero_wht(self, calc):
        """Dividend with zero WHT (rare but possible)."""
        result = calc.calculate_dividend(
            gross_pln=Decimal("1000"),
            wht_pln=Decimal("0"),
            country_code="US",
        )

        assert result["tax_credit"] == Decimal("0")
        assert result["tax_to_pay"] == Decimal("190.00")  # Full 19% Polish tax

    def test_batch_calculation(self, calc):
        """Batch calculation of multiple dividends."""
        dividends = [
            ("AAPL", "US", Decimal("1000"), Decimal("150")),
            ("SAP", "DE", Decimal("500"), Decimal("75")),
            ("SHELL", "GB", Decimal("2000"), Decimal("200")),
        ]

        results, warnings = calc.calculate_batch(dividends)

        assert len(results) == 3
        assert results[0]["tax_to_pay"] == Decimal("40.00")
        assert results[1]["tax_to_pay"] == Decimal("20.00")
        # UK: (2000 * 0.19) - 200 = 380 - 200 = 180
        assert results[2]["tax_to_pay"] == Decimal("180.00")

    def test_excessive_wht_batch_warnings(self, calc):
        """Batch with excessive WHT generates warnings."""
        dividends = [
            ("STOCK", "US", Decimal("1000"), Decimal("250")),  # Exceeds 15%
        ]

        results, warnings = calc.calculate_batch(dividends)

        assert len(warnings) == 1
        assert "W-8BEN" in warnings[0]
