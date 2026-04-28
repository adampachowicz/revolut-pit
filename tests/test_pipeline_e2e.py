"""End-to-end pipeline test with a mock NBP client.

Uses the anonymized fixture CSVs in examples/sample_data/ to verify the
full parse → calculate → PIT-38 → reports flow without hitting the network.
"""

from datetime import date
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
    result = pipeline.run(prior_year_loss=Decimal("0"))

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
