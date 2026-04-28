"""Generate formal PDF audit report for accountant review.

This module creates a comprehensive PDF that an accountant can review to verify
every PIT-38 calculation. Each calculation is shown with:
- Source data (from Revolut CSV)
- NBP rate used (with date and source URL)
- Math step-by-step
- Legal reference

Output: a multi-page PDF with executive summary, methodology, transaction
detail, NBP rates appendix, and legal references appendix.
"""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
)

from .legal_refs import LEGAL_REFS


# Register a Unicode font for Polish diacritics (ą, ć, ę, ł, ń, ó, ś, ź, ż)
_FONT_REGULAR = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"


def _register_polish_font() -> None:
    """Try to find a system TTF with full Polish diacritic support."""
    global _FONT_REGULAR, _FONT_BOLD

    bundled_fonts = Path(__file__).resolve().parent / "assets" / "fonts"
    candidates = [
        # Bundled fonts, used on Streamlit Cloud and other minimal hosts.
        (bundled_fonts / "DejaVuSans.ttf",
         bundled_fonts / "DejaVuSans-Bold.ttf",
         "DejaVuSans-Bundled", "DejaVuSans-Bundled-Bold"),
        # DejaVu (most Linux distros)
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "DejaVuSans", "DejaVuSans-Bold"),
        # Liberation
        ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
         "LiberationSans", "LiberationSans-Bold"),
        # macOS / others
        ("/Library/Fonts/Arial Unicode.ttf",
         "/Library/Fonts/Arial Unicode.ttf",
         "ArialUnicode", "ArialUnicode"),
        ("/System/Library/Fonts/Helvetica.ttc",
         "/System/Library/Fonts/Helvetica.ttc",
         "Helvetica-System", "Helvetica-System"),
    ]
    for reg_path, bold_path, reg_name, bold_name in candidates:
        try:
            reg_path = Path(reg_path)
            bold_path = Path(bold_path)
            if reg_path.exists():
                pdfmetrics.registerFont(TTFont(reg_name, str(reg_path)))
                if reg_path != bold_path and bold_path.exists():
                    pdfmetrics.registerFont(TTFont(bold_name, str(bold_path)))
                else:
                    bold_name = reg_name
                _FONT_REGULAR = reg_name
                _FONT_BOLD = bold_name
                return
        except Exception:
            continue


_register_polish_font()


def _money(amount, currency: str = "PLN") -> str:
    """Format Decimal as money string."""
    if amount is None:
        return "—"
    if isinstance(amount, (int, float)):
        amount = Decimal(str(amount))
    return f"{amount:,.2f} {currency}"


def _rate(rate) -> str:
    """Format NBP rate (4 decimals)."""
    if rate is None:
        return "—"
    if isinstance(rate, (int, float)):
        rate = Decimal(str(rate))
    return f"{rate:.4f}"


def _date(d) -> str:
    """Format date as YYYY-MM-DD."""
    if d is None:
        return "—"
    if hasattr(d, "strftime"):
        return d.strftime("%Y-%m-%d")
    return str(d)[:10]


def _build_styles():
    """Build paragraph styles, using a Unicode font for Polish diacritics."""
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "title", parent=base["Title"],
            fontName=_FONT_BOLD, fontSize=22, spaceAfter=12,
            textColor=colors.HexColor("#1a1a1a"),
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"],
            fontName=_FONT_BOLD, fontSize=16, spaceBefore=14, spaceAfter=8,
            textColor=colors.HexColor("#1a3a8a"),
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"],
            fontName=_FONT_BOLD, fontSize=13, spaceBefore=10, spaceAfter=6,
            textColor=colors.HexColor("#2a4a9a"),
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"],
            fontName=_FONT_REGULAR, fontSize=10, leading=14, spaceAfter=4,
        ),
        "small": ParagraphStyle(
            "small", parent=base["BodyText"],
            fontName=_FONT_REGULAR, fontSize=8, leading=11,
            textColor=colors.HexColor("#666666"),
        ),
        "warning": ParagraphStyle(
            "warning", parent=base["BodyText"],
            fontName=_FONT_REGULAR, fontSize=10, leading=14,
            textColor=colors.HexColor("#aa3333"),
            backColor=colors.HexColor("#fff5f5"),
            borderPadding=6,
        ),
    }
    return styles


def _table_style(header_bg: str = "#e8eaf6") -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1a1a1a")),
            ("FONTNAME", (0, 0), (-1, 0), _FONT_BOLD),
            ("FONTNAME", (0, 1), (-1, -1), _FONT_REGULAR),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
    )


def _legal_ref_block(ref_keys: List[str], styles) -> List:
    """Build a legal references block."""
    out = [Paragraph("<b>Podstawa prawna</b>", styles["h2"])]
    for key in ref_keys:
        ref = LEGAL_REFS.get(key)
        if ref is None:
            continue
        out.append(
            Paragraph(
                f"<b>{ref.article}</b> ({ref.act}) — {ref.description_pl}<br/>"
                f'<font size="8" color="#666"><u>{ref.url}</u></font>',
                styles["body"],
            )
        )
    out.append(Spacer(1, 6))
    return out


def generate_audit_pdf(
    pit38_result: Dict,
    output_path: Path,
    user_identifier: Optional[str] = None,
    tax_year: Optional[int] = None,
) -> Path:
    """
    Generate formal audit PDF for accountant review.

    Args:
        pit38_result: PIT-38 result from PIT38Generator (must include _detail with
                      stocks, crypto, dividends, nbp_rates_used)
        output_path: target PDF file path
        user_identifier: free-text user identifier (e.g. "Adam P., NIP: ...")
        tax_year: tax year (defaults to result["rok_podatkowy"])

    Returns:
        Path to generated PDF
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    year = tax_year or pit38_result.get("rok_podatkowy", "?")
    detail = pit38_result.get("_detail", {})
    stocks = detail.get("stocks", [])
    crypto = detail.get("crypto", [])
    dividends = detail.get("dividends", [])
    nbp_rates = detail.get("nbp_rates_used", {})

    styles = _build_styles()
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        title=f"PIT-38 Audyt {year}",
        author="revolut-pit",
    )

    flow = []

    # ========== Cover ==========
    flow.append(Paragraph("Audyt PIT-38", styles["title"]))
    flow.append(Paragraph(f"<b>Rok podatkowy:</b> {year}", styles["body"]))
    flow.append(
        Paragraph(
            f"<b>Wygenerowano:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            styles["body"],
        )
    )
    if user_identifier:
        flow.append(Paragraph(f"<b>Podatnik:</b> {user_identifier}", styles["body"]))
    flow.append(
        Paragraph(
            f"<b>Narzędzie:</b> revolut-pit (open-source, MIT)",
            styles["body"],
        )
    )
    flow.append(Spacer(1, 12))
    flow.append(
        Paragraph(
            "Niniejszy raport audytowy zawiera kompletny wykaz transakcji i obliczeń "
            "podatkowych dla deklaracji PIT-38. Każda kwota w PLN jest możliwa do ręcznej "
            "weryfikacji przeciw publicznemu API NBP. Raport przeznaczony jest do "
            "weryfikacji przez doradcę podatkowego / księgową przed złożeniem deklaracji.",
            styles["body"],
        )
    )
    flow.append(Spacer(1, 12))

    # ========== Executive summary ==========
    flow.append(Paragraph("1. Podsumowanie wykonawcze", styles["h1"]))

    c = pit38_result["czesc_C"]
    e = pit38_result["czesc_E"]
    d = pit38_result["czesc_D"]
    g = pit38_result["czesc_G"]

    summary_data = [
        ["Sekcja PIT-38", "Przychód", "Koszt / WHT", "Dochód", "Podatek"],
        [
            "Część C — papiery wartościowe",
            _money(c["przychod_pln"]),
            _money(c["koszt_pln"]),
            _money(c["dochod_pln"]),
            _money(c["dochod_pln"] * Decimal("0.19")),
        ],
        [
            "Część D — dywidendy",
            _money(d["przychod_pln"]),
            _money(d.get("podatek_zagraniczny", Decimal(0))),
            "—",
            _money(d["podatek_do_zaplaty"]),
        ],
        [
            "Część E — kryptowaluty",
            _money(e["przychod_pln"]),
            _money(e["koszt_pln"]),
            _money(e["dochod_pln"]),
            _money(e["dochod_pln"] * Decimal("0.19")),
        ],
        [
            "Część G — straty z lat ubiegłych",
            "—",
            _money(g.get("strata_z_lat_ubieglych", Decimal(0))),
            "—",
            "—",
        ],
        [
            "RAZEM",
            "",
            "",
            _money(pit38_result.get("dochod_razem", Decimal(0))),
            _money(pit38_result.get("podatek_do_zaplaty", Decimal(0))),
        ],
    ]
    t = Table(summary_data, colWidths=[6.5 * cm, 3 * cm, 3 * cm, 3 * cm, 3 * cm])
    t.setStyle(_table_style())
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fff8e1")),
                ("FONTNAME", (0, -1), (-1, -1), _FONT_BOLD),
            ]
        )
    )
    flow.append(t)
    flow.append(Spacer(1, 8))

    if pit38_result.get("warnings"):
        flow.append(Paragraph("Ostrzeżenia:", styles["h2"]))
        for w in pit38_result["warnings"]:
            flow.append(Paragraph(f"- {w}", styles["warning"]))

    flow.append(PageBreak())

    # ========== Methodology ==========
    flow.append(Paragraph("2. Metodologia", styles["h1"]))
    flow.append(
        Paragraph(
            "Każda transakcja w walucie obcej została przeliczona na PLN według kursu "
            "średniego NBP z ostatniego dnia roboczego poprzedzającego dzień transakcji "
            "(zasada D-1, art. 11a ust. 1 i 3 ustawy o PIT). Polskie święta zostały "
            "uwzględnione przy określaniu dnia roboczego. Wszystkie obliczenia wykonane "
            "z precyzją Decimal; finalny wynik zaokrąglony do grosza zgodnie z art. 63 § 1 "
            "Ordynacji podatkowej (ROUND_HALF_UP).",
            styles["body"],
        )
    )
    flow.append(Spacer(1, 6))
    flow.append(Paragraph("Zastosowane przepisy:", styles["h2"]))
    flow.extend(
        _legal_ref_block(
            [
                "nbp_d_minus_1",
                "fifo_method",
                "capital_gains_19_percent",
                "dividend_19_percent",
                "foreign_tax_credit",
                "crypto_crypto_exempt",
                "loss_carry_forward",
                "grosz_rounding",
                "pit38_deadline",
            ],
            styles,
        )
    )
    flow.append(PageBreak())

    # ========== Stocks detail ==========
    if stocks:
        flow.append(Paragraph("3. Akcje i ETF — szczegóły FIFO", styles["h1"]))
        flow.append(
            Paragraph(
                f"Ilość zamkniętych pozycji: <b>{len(stocks)}</b>. Każda pozycja "
                f"przeliczona na PLN wg kursu NBP D-1 osobno dla daty zakupu i sprzedaży.",
                styles["body"],
            )
        )
        rows = [
            [
                "#",
                "Symbol",
                "Kraj",
                "Kupno",
                "Sprzedaż",
                "Wal.",
                "Koszt orig.",
                "Kurs NBP\nzakupu",
                "Koszt PLN",
                "Sprzedaż\norig.",
                "Kurs NBP\nsprz.",
                "Przych. PLN",
                "Zysk PLN",
            ]
        ]
        for i, s in enumerate(stocks, 1):
            rows.append(
                [
                    str(i),
                    s.get("symbol", ""),
                    s.get("country_code", "") or "—",
                    _date(s.get("date_acquired")),
                    _date(s.get("date_sold")),
                    s.get("currency", "USD"),
                    _money(s.get("cost_basis_foreign"), s.get("currency", "USD")),
                    _rate(s.get("cost_rate_nbp")),
                    _money(s.get("cost_basis_pln")),
                    _money(s.get("proceeds_foreign"), s.get("currency", "USD")),
                    _rate(s.get("sell_rate_nbp")),
                    _money(s.get("proceeds_pln")),
                    _money(s.get("gain_pln")),
                ]
            )
        # Totals
        rows.append(
            [
                "",
                "SUMA",
                "",
                "",
                "",
                "",
                "",
                "",
                _money(c["koszt_pln"]),
                "",
                "",
                _money(c["przychod_pln"]),
                _money(c["dochod_pln"]),
            ]
        )

        col_widths = [
            0.6 * cm,  # #
            1.3 * cm,
            0.7 * cm,
            1.5 * cm,
            1.5 * cm,
            0.7 * cm,
            1.6 * cm,
            1.0 * cm,
            1.6 * cm,
            1.6 * cm,
            1.0 * cm,
            1.6 * cm,
            1.5 * cm,
        ]
        t = Table(rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(_table_style())
        t.setStyle(
            TableStyle(
                [
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fff8e1")),
                    ("FONTNAME", (0, -1), (-1, -1), _FONT_BOLD),
                ]
            )
        )
        flow.append(t)
        flow.append(Spacer(1, 6))
        flow.extend(_legal_ref_block(["fifo_method", "capital_gains_19_percent"], styles))
        flow.append(PageBreak())

    # ========== Dividends detail ==========
    if dividends:
        flow.append(Paragraph("4. Dywidendy + kredyt zagraniczny WHT", styles["h1"]))
        flow.append(
            Paragraph(
                "Limit kredytu = brutto × stawka traktatowa. Kredyt = min(WHT zapłacony, limit). "
                "Podatek do zapłaty = polski 19% − kredyt. Nadpłata WHT za granicą "
                "(WHT > limit) NIE jest odliczana w PL.",
                styles["body"],
            )
        )
        rows = [
            ["#", "Data", "Symbol", "Kraj", "Brutto PLN", "WHT zapłacony", "Limit (treaty %)", "Kredyt", "Do zapłaty"]
        ]
        for i, dv in enumerate(dividends, 1):
            treaty_str = f"{dv.get('treaty_rate', Decimal(0)) * 100:.0f}%"
            rows.append(
                [
                    str(i),
                    _date(dv.get("date")),
                    dv.get("symbol", ""),
                    dv.get("country_code", "") or "—",
                    _money(dv.get("gross_pln")),
                    _money(dv.get("wht_paid_pln")),
                    f"{_money(dv.get('treaty_cap'))} ({treaty_str})",
                    _money(dv.get("tax_credit")),
                    _money(dv.get("tax_to_pay")),
                ]
            )
        rows.append(
            [
                "",
                "SUMA",
                "",
                "",
                _money(d["przychod_pln"]),
                _money(d.get("podatek_zagraniczny", Decimal(0))),
                "",
                "",
                _money(d["podatek_do_zaplaty"]),
            ]
        )

        col_widths = [0.6 * cm, 1.8 * cm, 1.4 * cm, 1.0 * cm, 1.8 * cm, 1.8 * cm, 2.4 * cm, 1.6 * cm, 1.8 * cm]
        t = Table(rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(_table_style())
        t.setStyle(
            TableStyle(
                [
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fff8e1")),
                    ("FONTNAME", (0, -1), (-1, -1), _FONT_BOLD),
                ]
            )
        )
        flow.append(t)
        flow.append(Spacer(1, 6))
        flow.extend(
            _legal_ref_block(
                ["dividend_19_percent", "foreign_tax_credit", "treaty_pl_us", "treaty_pl_de"],
                styles,
            )
        )
        flow.append(PageBreak())

    # ========== Crypto detail ==========
    if crypto:
        flow.append(Paragraph("5. Kryptowaluty", styles["h1"]))
        flow.append(
            Paragraph(
                "SWAP-y (wymiana crypto-to-crypto) zostały WYKLUCZONE jako "
                "nieopodatkowane (art. 17 ust. 1f ustawy o PIT). Poniżej tylko realne "
                "sprzedaże za fiat.",
                styles["body"],
            )
        )
        rows = [
            [
                "#",
                "Symbol",
                "Kupno",
                "Sprzedaż",
                "Ilość",
                "Wal.",
                "Koszt orig.",
                "Kurs NBP\nzakupu",
                "Koszt PLN",
                "Sprzedaż\norig.",
                "Kurs NBP\nsprz.",
                "Przych. PLN",
                "Zysk PLN",
            ]
        ]
        for i, cr in enumerate(crypto, 1):
            rows.append(
                [
                    str(i),
                    cr.get("symbol", ""),
                    _date(cr.get("date_acquired")),
                    _date(cr.get("date_sold")),
                    str(cr.get("quantity", "")),
                    cr.get("currency", "USD"),
                    _money(cr.get("cost_basis_foreign"), cr.get("currency", "USD")),
                    _rate(cr.get("cost_rate_nbp")),
                    _money(cr.get("cost_basis_pln")),
                    _money(cr.get("proceeds_foreign"), cr.get("currency", "USD")),
                    _rate(cr.get("sell_rate_nbp")),
                    _money(cr.get("proceeds_pln")),
                    _money(cr.get("gain_pln")),
                ]
            )
        col_widths = [0.6, 1.2, 1.5, 1.5, 1.5, 0.7, 1.6, 1.0, 1.6, 1.6, 1.0, 1.6, 1.5]
        col_widths = [w * cm for w in col_widths]
        t = Table(rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(_table_style())
        t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 7)]))
        flow.append(t)
        flow.append(Spacer(1, 6))
        flow.extend(_legal_ref_block(["crypto_crypto_exempt"], styles))
        flow.append(PageBreak())

    # ========== NBP rates appendix ==========
    if nbp_rates:
        flow.append(Paragraph("6. Załącznik — kursy NBP użyte w obliczeniach", styles["h1"]))
        flow.append(
            Paragraph(
                f"Wszystkie kursy pochodzą z Tabeli A NBP (kursy średnie). "
                f"Każda data jest dniem roboczym (z uwzględnieniem polskich świąt). "
                f"Łącznie pobrano {len(nbp_rates)} unikalnych kursów. Każdy kurs jest "
                f"weryfikowalny ręcznie pod adresem URL podanym obok.",
                styles["body"],
            )
        )

        rate_rows = [["Waluta", "Data D-1", "Kurs średni", "URL weryfikacji NBP"]]
        for key, rate in sorted(nbp_rates.items()):
            try:
                cur, date_str = key.split("_", 1)
            except ValueError:
                continue
            url = f"https://api.nbp.pl/api/exchangerates/rates/A/{cur}/{date_str}/?format=json"
            rate_rows.append([cur, date_str, _rate(rate), url])

        t = Table(
            rate_rows,
            colWidths=[1.5 * cm, 2.5 * cm, 2.5 * cm, 11 * cm],
            repeatRows=1,
        )
        t.setStyle(_table_style())
        t.setStyle(TableStyle([("FONTSIZE", (3, 1), (3, -1), 6)]))
        flow.append(t)
        flow.append(Spacer(1, 6))
        flow.extend(_legal_ref_block(["nbp_d_minus_1", "nbp_d_minus_1_definition"], styles))
        flow.append(PageBreak())

    # ========== Disclaimer ==========
    flow.append(Paragraph("7. Zastrzeżenia / Disclaimer", styles["h1"]))
    flow.append(
        Paragraph(
            "<b>Niniejszy raport NIE stanowi porady podatkowej.</b> Został wygenerowany "
            "automatycznie na podstawie danych eksportu z platformy Revolut. Pomimo "
            "automatycznych testów i wielowarstwowej weryfikacji, narzędzie <b>nie "
            "zwalnia podatnika z odpowiedzialności</b> za prawidłowość deklaracji. "
            "Przed złożeniem PIT-38 zalecamy weryfikację przez uprawnionego doradcę "
            "podatkowego lub księgową. W przypadku staking rewards z kryptowalut, "
            "transakcji CFD, opcji lub instrumentów strukturyzowanych — narzędzie "
            "nie obsługuje tych przypadków.",
            styles["warning"],
        )
    )
    flow.append(Spacer(1, 6))
    flow.append(
        Paragraph(
            "<b>Open-source:</b> kod źródłowy narzędzia oraz cała logika obliczeniowa "
            "są publicznie dostępne i podlegają audytowi społeczności (licencja MIT).",
            styles["body"],
        )
    )

    doc.build(flow)
    return output_path
