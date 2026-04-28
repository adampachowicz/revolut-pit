"""Regression tests for PDF audit report generation."""

from decimal import Decimal
from pathlib import Path

from revolut_pit import pdf_audit


def test_pdf_audit_uses_bundled_polish_font(tmp_path):
    """The audit PDF must embed a Unicode font that supports Polish text."""
    assert pdf_audit._FONT_REGULAR == "DejaVuSans-Bundled"
    assert pdf_audit._FONT_BOLD == "DejaVuSans-Bundled-Bold"

    font_dir = Path(pdf_audit.__file__).resolve().parent / "assets" / "fonts"
    assert (font_dir / "DejaVuSans.ttf").is_file()
    assert (font_dir / "DejaVuSans-Bold.ttf").is_file()

    result = {
        "rok_podatkowy": 2025,
        "czesc_C": {
            "przychod_pln": Decimal("1234.56"),
            "koszt_pln": Decimal("1000.00"),
            "dochod_pln": Decimal("234.56"),
        },
        "czesc_D": {
            "przychod_pln": Decimal("10.00"),
            "podatek_zagraniczny": Decimal("1.00"),
            "podatek_do_zaplaty": Decimal("0.90"),
        },
        "czesc_E": {
            "przychod_pln": Decimal("0"),
            "koszt_pln": Decimal("0"),
            "dochod_pln": Decimal("0"),
        },
        "czesc_G": {"strata_z_lat_ubieglych": Decimal("0")},
        "dochod_razem": Decimal("234.56"),
        "podatek_do_zaplaty": Decimal("45.47"),
        "warnings": ["Zażółć gęślą jaźń: księgową, złożeniem, Część, średniego."],
        "_detail": {},
    }

    output_path = tmp_path / "pit38_audyt.pdf"
    pdf_audit.generate_audit_pdf(
        result,
        output_path,
        user_identifier="Zażółć gęślą jaźń",
        tax_year=2025,
    )

    assert output_path.is_file()
    assert output_path.stat().st_size > 10_000
