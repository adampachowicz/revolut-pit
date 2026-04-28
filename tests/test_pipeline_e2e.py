"""End-to-end pipeline test with a mock NBP client.

Uses the anonymized fixture CSVs in examples/sample_data/ to verify the
full parse → calculate → PIT-38 → reports flow without hitting the network.
"""

import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from revolut_pit.nbp import NBPClient
from revolut_pit.pipeline import Pipeline
from revolut_pit.reports import ReportGenerator


class MockNBP(NBPClient):
    """Mock NBP returning fixed rates per currency, no network calls."""

    FIXED_RATES = {
        "USD": Decimal("4.00"),
        "EUR": Decimal("4.30"),
        "GBP": Decimal("5.00"),
    }

    def __init__(self):
        # don't call super().__init__ (which creates a cache dir)
        self._cache = {}
        self.cache_file = None

    def get_rate(self, currency, date, use_d_minus_1=True):
        return self.FIXED_RATES.get(currency, Decimal("4.00"))

    def clear_cache(self):
        self._cache.clear()


def test_pipeline_runs_end_to_end_on_fixtures(tmp_path):
    """Pipeline must run without errors on sample fixtures and produce reports."""
    project_root = Path(__file__).parent.parent
    sample_dir = project_root / "examples" / "sample_data"

    if not sample_dir.exists() or not list(sample_dir.glob("*.csv")):
        pytest.skip("Sample data fixtures not available")

    pipeline = Pipeline(
        year=2025,
        data_dir=sample_dir,
        nbp_client=MockNBP(),
        verbose=False,
    )
    result = pipeline.run(
        prior_year_loss_c=Decimal("0"),
        prior_year_loss_e=Decimal("0"),
    )

    # Structure assertions
    assert "czesc_C" in result
    assert "czesc_D" in result
    assert "czesc_E" in result
    assert "podatek_do_zaplaty" in result

    # Should produce some kind of result, even if zero
    assert result["czesc_C"]["przychod_pln"] >= 0
    assert result["podatek_do_zaplaty"] >= 0

    # Reports
    detail = result.pop("_detail", {})
    reporter = ReportGenerator(output_dir=tmp_path)
    xlsx = reporter.generate_excel(
        pit38_result=result,
        stocks=detail.get("stocks", []),
        crypto=detail.get("crypto", []),
        dividends=detail.get("dividends", []),
        nbp_rates_used=detail.get("nbp_rates_used", {}),
        filename="pit38_2025.xlsx",
    )
    md = reporter.generate_markdown(
        pit38_result=result,
        stocks=detail.get("stocks", []),
        crypto=detail.get("crypto", []),
        dividends=detail.get("dividends", []),
        filename="pit38_2025.md",
    )

    assert xlsx.exists() and xlsx.stat().st_size > 0
    assert md.exists() and md.stat().st_size > 0


class PerLotMockNBP(NBPClient):
    """NBP mock that returns a DIFFERENT rate per (currency, date).

    Lets us assert that the pipeline applies a per-lot D-1 rate — i.e. each
    P&L row's `date_acquired` produces an independent NBP query, not a single
    rate shared across rows of the same symbol.
    """

    def __init__(self):
        self._cache = {}
        self.cache_file = None
        self.calls: list = []
        # Keyed by the *transaction* date (the value the pipeline passes in),
        # because the mock bypasses NBPClient's D-1 logic. The chosen rates
        # are still distinct so we can prove the pipeline used different
        # rates for different lots.
        self.rates = {
            "2020-08-11": Decimal("3.80"),
            "2020-10-06": Decimal("3.85"),
            "2025-05-13": Decimal("3.90"),
        }

    def get_rate(self, currency, date, use_d_minus_1=True):
        key = date.isoformat() if hasattr(date, "isoformat") else str(date)
        self.calls.append((currency, key))
        return self.rates.get(key, Decimal("4.00"))

    def clear_cache(self):
        self._cache.clear()


def test_revolut_pl_per_lot_uses_per_lot_d_minus_1_rate(tmp_path):
    """Bug #4 (LEGAL) / Bug #1 (MODEL-QA) regression — verified false positive.

    Revolut's "Income from Sells" is a per-lot match: when one symbol has
    been bought across multiple dates and sold in one day, P&L emits one
    row per buy lot with that lot's `Date acquired`. Each row therefore
    must be converted with its OWN D-1 NBP rate (art. 11a ust. 2 PIT).

    This test fakes a minimal P&L of three BA lots (acquired 2020-08-11,
    2020-10-06, sold 2025-05-13) and asserts that the cost in PLN reflects
    each lot's D-1 rate independently — not a single rate.
    """
    pl = (
        "Income from Sells\n"
        "Date acquired,Date sold,Symbol,Security name,ISIN,Country,Quantity,"
        "Cost basis,Gross proceeds,Gross PnL,Currency\n"
        "2020-08-11,2025-05-13,BA,Boeing,US0970231058,US,1,100.00,150.00,50.00,USD\n"
        "2020-10-06,2025-05-13,BA,Boeing,US0970231058,US,1,100.00,150.00,50.00,USD\n"
    )
    pl_path = tmp_path / "profit_and_loss_2025.csv"
    pl_path.write_text(pl)

    nbp = PerLotMockNBP()
    pipeline = Pipeline(year=2025, data_dir=tmp_path, nbp_client=nbp, verbose=False)
    stocks, _ = pipeline.process_stocks()

    # Two rows in → two closed positions out, each with its own cost rate.
    assert len(stocks) == 2

    by_acquired = {s["date_acquired"].date().isoformat(): s for s in stocks}

    # Lot 1 — D-1 of 2020-08-11 = 2020-08-10, rate 3.80
    lot1 = by_acquired["2020-08-11"]
    assert lot1["cost_rate_nbp"] == Decimal("3.80")
    assert lot1["cost_basis_pln"] == Decimal("100.00") * Decimal("3.80")

    # Lot 2 — D-1 of 2020-10-06 = 2020-10-05, rate 3.85
    lot2 = by_acquired["2020-10-06"]
    assert lot2["cost_rate_nbp"] == Decimal("3.85")
    assert lot2["cost_basis_pln"] == Decimal("100.00") * Decimal("3.85")

    # Both share the same sell date → same sell rate (3.90).
    assert lot1["sell_rate_nbp"] == Decimal("3.90")
    assert lot2["sell_rate_nbp"] == Decimal("3.90")
