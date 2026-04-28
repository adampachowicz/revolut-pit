"""Tests for PIT-38 form generation.

Covers the post-2026-04-28 audit refactor: per-source loss carry-forward
(C and E tracked independently per art. 9 ust. 6 PIT), current-year loss
reporting (art. 9 ust. 3), and the corrected `dochod_razem` semantics
(dividends excluded per art. 30a ust. 7).
"""

from decimal import Decimal

import pytest

from revolut_pit.pit38 import PIT38Generator


class TestPIT38Generator:
    """Test PIT-38 form structure generation."""

    @pytest.fixture
    def generator(self):
        return PIT38Generator(tax_year=2025)

    def test_empty_calculation(self, generator):
        """Empty calculation generates zeroed sections."""
        result = generator.generate(stocks=[], crypto=[], dividends=[])

        assert result["rok_podatkowy"] == 2025
        assert result["czesc_C"]["dochod_pln"] == Decimal("0")
        assert result["czesc_C"]["strata_pln"] == Decimal("0")
        assert result["czesc_E"]["dochod_pln"] == Decimal("0")
        assert result["czesc_E"]["strata_pln"] == Decimal("0")
        assert result["czesc_D"]["przychod_pln"] == Decimal("0")
        assert result["podatek_do_zaplaty"] == Decimal("0")

    def test_stocks_only(self, generator):
        """PIT-38 with only stock gains."""
        stocks = [
            {
                "symbol": "AAPL",
                "quantity": Decimal("10"),
                "cost_basis_pln": Decimal("4000"),
                "proceeds_pln": Decimal("4500"),
                "gain_pln": Decimal("500"),
            },
        ]

        result = generator.generate(stocks=stocks, crypto=[], dividends=[])

        assert result["czesc_C"]["przychod_pln"] == Decimal("4500")
        assert result["czesc_C"]["koszt_pln"] == Decimal("4000")
        assert result["czesc_C"]["dochod_pln"] == Decimal("500")
        assert result["czesc_C"]["strata_pln"] == Decimal("0")
        # Tax = 500 * 0.19 = 95
        assert result["podatek_do_zaplaty"] == Decimal("95.00")

    def test_crypto_only(self, generator):
        """PIT-38 with only crypto gains (selling to fiat, not SWAPs)."""
        crypto = [
            {
                "symbol": "BTC",
                "quantity": Decimal("1"),
                "cost_basis_pln": Decimal("100000"),
                "proceeds_pln": Decimal("120000"),
                "gain_pln": Decimal("20000"),
            },
        ]

        result = generator.generate(stocks=[], crypto=crypto, dividends=[])

        assert result["czesc_E"]["dochod_pln"] == Decimal("20000")
        # Tax = 20000 * 0.19 = 3800
        assert result["podatek_do_zaplaty"] == Decimal("3800.00")

    def test_dividends_only(self, generator):
        """PIT-38 with only dividends."""
        dividends = [
            {
                "symbol": "AAPL",
                "country_code": "US",
                "gross_pln": Decimal("1000"),
                "wht_paid_pln": Decimal("150"),
                "polish_tax_19": Decimal("190"),
                "treaty_rate": Decimal("0.15"),
                "tax_credit": Decimal("150"),
                "tax_to_pay": Decimal("40"),
            },
        ]

        result = generator.generate(stocks=[], crypto=[], dividends=dividends)

        assert result["czesc_D"]["przychod_pln"] == Decimal("1000")
        assert result["czesc_D"]["podatek_do_zaplaty"] == Decimal("40")
        assert result["podatek_do_zaplaty"] == Decimal("40")

    def test_combined_all_sections(self, generator):
        """All sections combined.

        Regression for Bug #4 (post-2026-04-28 audit):
        `dochod_razem` is the C+E capital-gains base only.
        Dividend income (Part D) is taxed separately under art. 30a
        and must NOT inflate `dochod_razem` (art. 30a ust. 7 PIT).
        """
        stocks = [
            {
                "cost_basis_pln": Decimal("4000"),
                "proceeds_pln": Decimal("4500"),
            },
        ]
        crypto = [
            {
                "cost_basis_pln": Decimal("100000"),
                "proceeds_pln": Decimal("120000"),
            },
        ]
        dividends = [
            {
                "gross_pln": Decimal("1000"),
                "wht_paid_pln": Decimal("150"),
                "tax_to_pay": Decimal("40"),
                "country_code": "US",
            },
        ]

        result = generator.generate(stocks=stocks, crypto=crypto, dividends=dividends)

        # Capital-gains income = 500 + 20000 = 20500 (NOT 21500 — dividends excluded)
        assert result["dochod_razem"] == Decimal("20500")
        # Tax = (500 + 20000) * 0.19 + 40 = 3895 + 40 = 3935
        assert result["podatek_do_zaplaty"] == Decimal("3935.00")


class TestLossCarryForwardPerSource:
    """Regression tests for Bug #1 and #3: per-source loss carry-forward.

    Polish law (art. 22 ust. 14 + art. 9 ust. 6 PIT) requires that securities
    losses (Part C) only offset securities gains, and crypto losses (Part E)
    only offset crypto gains. They are SEPARATE income sources.
    """

    @pytest.fixture
    def generator(self):
        return PIT38Generator(tax_year=2025)

    def test_stock_prior_loss_does_not_offset_crypto_gain(self, generator):
        """Crypto loss carried from prior years cannot reduce stock income.

        Pre-fix bug: a single `prior_year_loss` was applied to combined C+E
        income. With C=100k, E=0, prior_loss_e=50k the tool would tax 50k
        (zaniżenie podatku o 9 500 PLN — REVIEW-MODEL-QA Bug #3).
        """
        stocks = [
            {
                "cost_basis_pln": Decimal("0"),
                "proceeds_pln": Decimal("100000"),
            },
        ]
        result = generator.generate(
            stocks=stocks,
            crypto=[],
            dividends=[],
            prior_year_loss_e=Decimal("50000"),  # crypto-only carry-forward
        )

        # E section has no income, so the loss cannot be applied this year.
        assert result["czesc_C"]["dochod_pln"] == Decimal("100000")
        assert result["czesc_E"]["dochod_pln"] == Decimal("0")
        assert result["czesc_G"]["applied_loss_e"] == Decimal("0")
        # Crypto loss is carried fully into next year.
        assert result["czesc_G"]["remaining_loss_carryforward_e"] == Decimal("50000")
        # Stock tax is full 19% of 100k.
        assert result["podatek_do_zaplaty"] == Decimal("19000.00")

    def test_crypto_prior_loss_offsets_only_crypto(self, generator):
        crypto = [
            {
                "cost_basis_pln": Decimal("0"),
                "proceeds_pln": Decimal("80000"),
            },
        ]
        result = generator.generate(
            stocks=[],
            crypto=crypto,
            dividends=[],
            prior_year_loss_e=Decimal("30000"),
        )

        assert result["czesc_G"]["applied_loss_e"] == Decimal("30000")
        assert result["czesc_G"]["remaining_loss_carryforward_e"] == Decimal("0")
        # Crypto income reduced 80k → 50k.
        assert result["dochod_razem"] == Decimal("50000")
        assert result["podatek_do_zaplaty"] == Decimal("9500.00")

    def test_stock_prior_loss_offsets_only_stocks(self, generator):
        stocks = [
            {
                "cost_basis_pln": Decimal("0"),
                "proceeds_pln": Decimal("80000"),
            },
        ]
        result = generator.generate(
            stocks=stocks,
            crypto=[],
            dividends=[],
            prior_year_loss_c=Decimal("30000"),
        )

        assert result["czesc_G"]["applied_loss_c"] == Decimal("30000")
        assert result["dochod_razem"] == Decimal("50000")
        assert result["podatek_do_zaplaty"] == Decimal("9500.00")


class TestCurrentYearLossReporting:
    """Regression tests for Bug #2: current-year losses must be reported
    so the user can carry them forward into the next 5 years (art. 9 ust. 3)."""

    @pytest.fixture
    def generator(self):
        return PIT38Generator(tax_year=2025)

    def test_stock_loss_is_reported(self, generator):
        stocks = [
            {
                "cost_basis_pln": Decimal("60000"),
                "proceeds_pln": Decimal("50000"),
            },
        ]
        result = generator.generate(stocks=stocks, crypto=[], dividends=[])

        assert result["czesc_C"]["dochod_pln"] == Decimal("0")
        # The 10k loss MUST be exposed for the user to carry into 2026.
        assert result["czesc_C"]["strata_pln"] == Decimal("10000")
        assert result["czesc_C"]["bilans_pln"] == Decimal("-10000")
        assert any("Strata bieżącego roku" in w for w in result["warnings"])
        assert result["podatek_do_zaplaty"] == Decimal("0")

    def test_crypto_loss_is_reported(self, generator):
        crypto = [
            {
                "cost_basis_pln": Decimal("100000"),
                "proceeds_pln": Decimal("70000"),
            },
        ]
        result = generator.generate(stocks=[], crypto=crypto, dividends=[])

        assert result["czesc_E"]["strata_pln"] == Decimal("30000")
        assert any("art. 22 ust. 16" in w for w in result["warnings"])


class TestLossCarryForwardCap:
    """Test 5M PLN annual loss cap (art. 9 ust. 3 zd. 2 PIT)."""

    @pytest.fixture
    def generator(self):
        return PIT38Generator(tax_year=2025)

    def test_loss_cap_applied_5M(self, generator):
        """Loss exceeding 5M PLN cap is capped and remainder carried forward."""
        stocks = [
            {
                "cost_basis_pln": Decimal("5000000"),
                "proceeds_pln": Decimal("15000000"),
            },
        ]

        result = generator.generate(
            stocks=stocks,
            crypto=[],
            dividends=[],
            prior_year_loss_c=Decimal("8000000"),
        )

        # Income: 10M, Applied loss: 5M (cap), Remaining: 3M
        assert result["czesc_G"]["strata_z_lat_ubieglych_c"] == Decimal("8000000")
        assert result["czesc_G"]["applied_loss_c"] == Decimal("5000000")
        assert result["czesc_G"]["remaining_loss_carryforward_c"] == Decimal("3000000")

        # Income after cap = 10M - 5M = 5M
        assert result["dochod_razem"] == Decimal("5000000")
        # Tax = 5M * 0.19 = 950k
        assert result["podatek_do_zaplaty"] == Decimal("950000.00")
        # Warning about exceeding cap
        assert any("przekracza roczny limit" in w for w in result["warnings"])

    def test_loss_below_cap(self, generator):
        stocks = [
            {
                "cost_basis_pln": Decimal("100000"),
                "proceeds_pln": Decimal("300000"),
            },
        ]

        result = generator.generate(
            stocks=stocks,
            crypto=[],
            dividends=[],
            prior_year_loss_c=Decimal("100000"),
        )

        assert result["czesc_G"]["applied_loss_c"] == Decimal("100000")
        assert result["czesc_G"]["remaining_loss_carryforward_c"] == Decimal("0")
        assert result["dochod_razem"] == Decimal("100000")
        assert not any("przekracza roczny limit" in w for w in result["warnings"])

    def test_loss_cap_zero_income(self, generator):
        """No income → no loss applied, full prior loss carried forward."""
        result = generator.generate(
            stocks=[],
            crypto=[],
            dividends=[],
            prior_year_loss_c=Decimal("8000000"),
        )

        assert result["czesc_G"]["applied_loss_c"] == Decimal("0")
        assert result["czesc_G"]["remaining_loss_carryforward_c"] == Decimal("8000000")
        assert result["dochod_razem"] == Decimal("0")


class TestPITZG:
    """PIT/ZG attachment is built from foreign dividends only."""

    @pytest.fixture
    def generator(self):
        return PIT38Generator(tax_year=2025)

    def test_pit_zg_attachment(self, generator):
        dividends = [
            {
                "gross_pln": Decimal("1000"),
                "wht_paid_pln": Decimal("150"),
                "tax_to_pay": Decimal("40"),
                "country_code": "US",
            },
            {
                "gross_pln": Decimal("500"),
                "wht_paid_pln": Decimal("75"),
                "tax_to_pay": Decimal("20"),
                "country_code": "DE",
            },
        ]

        result = generator.generate(stocks=[], crypto=[], dividends=dividends)

        pit_zg = result["pit_zg"]
        assert len(pit_zg) == 2
        assert pit_zg[0]["kraj"] == "US"
        assert pit_zg[0]["dochod_pln"] == Decimal("1000")
        assert pit_zg[1]["kraj"] == "DE"
        assert pit_zg[1]["podatek_zagraniczny_pln"] == Decimal("75")
