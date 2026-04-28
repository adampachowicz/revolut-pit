"""Streamlit UI for revolut-pit - 7-Step PIT-38 Tax Wizard.

A comprehensive step-by-step wizard for calculating Polish PIT-38 tax forms
from Revolut brokerage data exports, with legal references at every step.

Features:
- Multi-step wizard with session state tracking
- Legal references (ISAP links) at each step
- Real-time NBP exchange rate fetching
- FIFO stock matching
- Crypto swap detection and exclusion
- Dividend foreign tax credit calculation
- Prior loss carry-forward
- Detailed audit reports
- Excel/JSON export
"""

import os
import io
import json
from decimal import Decimal
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import streamlit as st
import pandas as pd

from revolut_pit import __version__
from revolut_pit.nbp import NBPClient
from revolut_pit.pipeline import Pipeline
from revolut_pit.reports import ReportGenerator
from revolut_pit.parsers import auto_detect
from revolut_pit.i18n import t as i18n, Language
from revolut_pit.audit import (
    cross_validate_stocks,
    nbp_url,
    generate_audit_trail,
)
from revolut_pit.legal_refs import render_legal_legend


# ============================================================================
# Page configuration
# ============================================================================

st.set_page_config(
    page_title="revolut-pit — PIT-38 Wizard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================================
# Session state initialization
# ============================================================================

if "language" not in st.session_state:
    st.session_state.language = "pl"

if "tax_year" not in st.session_state:
    st.session_state.tax_year = 2025

if "step" not in st.session_state:
    st.session_state.step = 0

if "parsed_data" not in st.session_state:
    st.session_state.parsed_data = []

if "nbp_rates" not in st.session_state:
    st.session_state.nbp_rates = {}

if "excluded_swaps" not in st.session_state:
    st.session_state.excluded_swaps = set()

if "stocks_state" not in st.session_state:
    st.session_state.stocks_state = {}

if "dividends_state" not in st.session_state:
    st.session_state.dividends_state = {}

if "prior_loss" not in st.session_state:
    st.session_state.prior_loss = Decimal(0)

if "final_result" not in st.session_state:
    st.session_state.final_result = None

if "pipeline_result" not in st.session_state:
    st.session_state.pipeline_result = None


# ============================================================================
# Helper functions
# ============================================================================


def get_lang() -> Language:
    """Get current language setting."""
    return "pl" if st.session_state.language == "PL" else "en"


def format_pln(value: Decimal) -> str:
    """Format decimal as Polish currency."""
    if isinstance(value, (int, float)):
        value = Decimal(str(value))
    return f"{value:,.2f} PLN".replace(",", " ")


def format_percent(value: Decimal) -> str:
    """Format decimal as percentage."""
    if isinstance(value, (int, float)):
        value = Decimal(str(value))
    return f"{value:.2f}%"


# ============================================================================
# Sidebar configuration
# ============================================================================

with st.sidebar:
    st.markdown(f"## 📊 {i18n('title', get_lang())}")
    st.markdown(f"**v{__version__}**")

    st.divider()

    # Language selection
    lang_options = ["PL", "EN"]
    selected_lang = st.radio(
        i18n("language", get_lang()),
        lang_options,
        index=0 if st.session_state.language == "PL" else 1,
        horizontal=True,
    )
    st.session_state.language = selected_lang

    st.divider()

    # Tax year selector
    st.session_state.tax_year = st.number_input(
        i18n("tax_year", get_lang()),
        min_value=2020,
        max_value=2030,
        value=st.session_state.tax_year,
        step=1,
    )

    st.divider()

    # Step indicator
    step_names = [
        "📤 Upload",
        "📊 NBP Rates",
        "🔄 Crypto SWAPs",
        "📈 Stocks FIFO",
        "💰 Dividends WHT",
        "📉 Prior Losses",
        "✅ Final Review",
    ]
    st.markdown(f"### {i18n('step', get_lang())} {st.session_state.step + 1}/7")
    st.markdown(f"**{step_names[st.session_state.step]}**")

    st.divider()

    # Reset button
    if st.button("🔄 Resetuj wizard", use_container_width=True):
        for key in list(st.session_state.keys()):
            if key not in ["language", "tax_year"]:
                del st.session_state[key]
        st.session_state.step = 0
        st.rerun()

    st.divider()

    # Disclaimer
    st.markdown(
        f"⚠️ **{i18n('disclaimer', get_lang())}**",
        unsafe_allow_html=True,
    )


# ============================================================================
# Main content
# ============================================================================

lang = get_lang()

st.title(f"📊 revolut-pit — PIT-38 {i18n('wizard', lang)}")

col1, col2 = st.columns(2)
with col1:
    st.caption(f"🗓️ {i18n('tax_year', lang)}: {st.session_state.tax_year}")
with col2:
    st.caption(f"🌐 {i18n('language', lang)}: {st.session_state.language}")

st.divider()


# ============================================================================
# STEP 0: Upload + Parse
# ============================================================================

if st.session_state.step == 0:
    st.header(f"📤 {i18n('upload_title', lang)}")
    st.markdown(i18n("upload_help", lang))

    uploaded_files = st.file_uploader(
        i18n("upload_csv", lang),
        type=["csv"],
        accept_multiple_files=True,
    )

    if uploaded_files:
        st.success(f"✓ {len(uploaded_files)} {i18n('files_uploaded', lang)}")

        # File summary with auto-detection
        st.subheader(i18n("file_summary", lang))

        file_info = []
        parsed_data = []

        for uploaded_file in uploaded_files:
            # Save to temp location for auto-detection
            temp_path = Path(f"/tmp/{uploaded_file.name}")
            temp_path.write_bytes(uploaded_file.getvalue())

            # Try to auto-detect
            detected_parser = auto_detect(temp_path)
            if detected_parser:
                detection_status = f"✓ {detected_parser.name} {detected_parser.version}"
            else:
                detection_status = f"⚠️ {i18n('unknown_format', lang)}"

            file_info.append(
                {
                    "name": uploaded_file.name,
                    "size_kb": f"{uploaded_file.size / 1024:.1f}",
                    "detected": detection_status,
                }
            )

            parsed_data.append(
                {
                    "name": uploaded_file.name,
                    "path": temp_path,
                    "parser": detected_parser,
                }
            )

        file_df = pd.DataFrame(file_info)
        st.dataframe(file_df, use_container_width=True)

        st.session_state.parsed_data = parsed_data

        # Buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Wstecz", disabled=True, use_container_width=True):
                pass
        with col2:
            if st.button(
                "Akceptuj pliki → ",
                type="primary",
                use_container_width=True,
            ):
                st.session_state.step = 1
                st.rerun()
    else:
        st.info(f"ℹ️ {i18n('no_files', lang)}")


# ============================================================================
# STEP 1: Pobranie kursów NBP
# ============================================================================

elif st.session_state.step == 1:
    st.header(f"📊 {i18n('nbp_rates_step', lang)}")
    st.markdown(i18n("nbp_rates_help", lang))

    # Legal reference
    render_legal_legend(
        ["nbp_d_minus_1", "nbp_d_minus_1_definition"],
        lang=lang,
    )

    # Parse all files to collect currencies and dates
    if st.session_state.parsed_data:
        with st.spinner(i18n("fetching_nbp", lang)):
            try:
                # Create temporary directory for files
                temp_dir = Path(f"/tmp/revolut_pit_{datetime.now().timestamp()}")
                temp_dir.mkdir(exist_ok=True)

                # Copy files to temp dir
                for file_data in st.session_state.parsed_data:
                    import shutil

                    shutil.copy(file_data["path"], temp_dir / file_data["name"])

                # Initialize pipeline and fetch rates
                nbp_client = NBPClient()
                pipeline = Pipeline(
                    year=int(st.session_state.tax_year),
                    data_dir=temp_dir,
                    nbp_client=nbp_client,
                    verbose=False,
                )

                # Dummy run to collect rates
                pipeline.process_stocks()
                pipeline.process_crypto()

                # Store rates in session
                st.session_state.nbp_rates = pipeline.nbp_rates_used

            except Exception as e:
                st.error(f"❌ {i18n('error_fetching_nbp', lang)}: {str(e)}")

        # Display rates table
        if st.session_state.nbp_rates:
            st.subheader(i18n("nbp_rates_table", lang))

            rates_data = []
            for rate_key, rate_value in st.session_state.nbp_rates.items():
                parts = rate_key.split("_")
                if len(parts) >= 2:
                    currency = parts[0]
                    date_str = "_".join(parts[1:])
                else:
                    currency = rate_key
                    date_str = ""

                rates_data.append(
                    {
                        i18n("currency", lang): currency,
                        i18n("date", lang): date_str,
                        i18n("nbp_rate", lang): float(rate_value),
                    }
                )

            rates_df = pd.DataFrame(rates_data)
            st.dataframe(rates_df, use_container_width=True)

            st.markdown(f"### {i18n('verify_nbp', lang)}")
            for rate_key in sorted(st.session_state.nbp_rates.keys()):
                parts = rate_key.split("_")
                if len(parts) >= 2:
                    currency = parts[0]
                    date_str = "_".join(parts[1:])
                    url = nbp_url(currency, date_str)
                    st.markdown(f"- [{rate_key}]({url})")

        # Buttons
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("← Wstecz", use_container_width=True):
                st.session_state.step = 0
                st.rerun()
        with col2:
            pass
        with col3:
            if st.button("Akceptuj kursy →", type="primary", use_container_width=True):
                st.session_state.step = 2
                st.rerun()


# ============================================================================
# STEP 2: Wykrywanie SWAP-ów krypto
# ============================================================================

elif st.session_state.step == 2:
    st.header(f"🔄 {i18n('crypto_swaps_step', lang)}")
    st.markdown(i18n("crypto_swaps_help", lang))

    # Legal reference
    render_legal_legend(["crypto_crypto_exempt"], lang=lang)

    # TODO: Detect swaps from parsed crypto data
    # For now, show placeholder
    st.info("🔄 Analiza SWAP-ów w trakcie...")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("← Wstecz", use_container_width=True):
            st.session_state.step = 1
            st.rerun()
    with col2:
        pass
    with col3:
        if st.button("Akceptuj wykluczenia →", type="primary", use_container_width=True):
            st.session_state.step = 3
            st.rerun()


# ============================================================================
# STEP 3: Akcje — FIFO + przeliczenie PLN
# ============================================================================

elif st.session_state.step == 3:
    st.header(f"📈 {i18n('stocks_step', lang)}")
    st.markdown(i18n("stocks_help", lang))

    # Legal reference
    render_legal_legend(
        ["capital_gains_19_percent", "fifo_method", "cost_of_revenue"],
        lang=lang,
    )

    st.info("📈 Wczytywanie pozycji akcji...")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("← Wstecz", use_container_width=True):
            st.session_state.step = 2
            st.rerun()
    with col2:
        pass
    with col3:
        if st.button("Akceptuj pozycje →", type="primary", use_container_width=True):
            st.session_state.step = 4
            st.rerun()


# ============================================================================
# STEP 4: Dywidendy + kredyt zagraniczny WHT
# ============================================================================

elif st.session_state.step == 4:
    st.header(f"💰 {i18n('dividends_step', lang)}")
    st.markdown(i18n("dividends_help", lang))

    # Legal reference
    render_legal_legend(
        [
            "dividend_19_percent",
            "foreign_tax_credit",
            "treaty_pl_us",
            "treaty_pl_de",
            "treaty_pl_uk",
            "treaty_pl_fr",
            "treaty_pl_ca",
            "treaty_pl_nl",
        ],
        lang=lang,
    )

    st.info("💰 Wczytywanie danych dywidend...")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("← Wstecz", use_container_width=True):
            st.session_state.step = 3
            st.rerun()
    with col2:
        pass
    with col3:
        if st.button("Akceptuj dywidendy →", type="primary", use_container_width=True):
            st.session_state.step = 5
            st.rerun()


# ============================================================================
# STEP 5: Strata z lat ubiegłych
# ============================================================================

elif st.session_state.step == 5:
    st.header(f"📉 {i18n('prior_loss_step', lang)}")
    st.markdown(i18n("prior_loss_help", lang))

    # Legal reference
    render_legal_legend(["loss_carry_forward", "loss_5m_cap"], lang=lang)

    # Input field
    loss_input = st.number_input(
        i18n("prior_loss_amount", lang),
        min_value=0.0,
        value=float(st.session_state.prior_loss),
        step=100000.0,
    )
    st.session_state.prior_loss = Decimal(str(loss_input))

    # Show limit information
    max_annual = Decimal("5000000")
    if st.session_state.prior_loss > max_annual:
        st.warning(
            f"⚠️ Limit roczny wynosi {format_pln(max_annual)}. "
            f"Kwota powyżej limitu zostanie przesunięta na następny rok."
        )

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("← Wstecz", use_container_width=True):
            st.session_state.step = 4
            st.rerun()
    with col2:
        pass
    with col3:
        if st.button("Akceptuj stratę →", type="primary", use_container_width=True):
            st.session_state.step = 6
            st.rerun()


# ============================================================================
# STEP 6: Finalne pola PIT-38 + audyt
# ============================================================================

elif st.session_state.step == 6:
    st.header(f"✅ {i18n('final_review_step', lang)}")
    st.markdown(i18n("final_review_help", lang))

    # Legal reference
    render_legal_legend(
        ["pit38_deadline", "grosz_rounding", "czynny_zal"],
        lang=lang,
    )

    # Run full pipeline to generate PIT-38
    with st.spinner(i18n("calculating", lang)):
        try:
            # Create temporary directory for files
            temp_dir = Path(f"/tmp/revolut_pit_{datetime.now().timestamp()}")
            temp_dir.mkdir(exist_ok=True)

            # Copy files to temp dir
            for file_data in st.session_state.parsed_data:
                import shutil

                shutil.copy(file_data["path"], temp_dir / file_data["name"])

            # Initialize pipeline
            nbp_client = NBPClient()
            pipeline = Pipeline(
                year=int(st.session_state.tax_year),
                data_dir=temp_dir,
                nbp_client=nbp_client,
                verbose=False,
            )

            # Run pipeline
            result = pipeline.run(prior_year_loss=st.session_state.prior_loss)
            st.session_state.pipeline_result = result

        except Exception as e:
            st.error(f"❌ {i18n('error_parsing', lang)}: {str(e)}")
            st.stop()

    if st.session_state.pipeline_result:
        result = st.session_state.pipeline_result

        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)

        c = result.get("czesc_C", {})
        with col1:
            st.metric(
                i18n("securities_income", lang),
                format_pln(c.get("dochod_pln", Decimal(0))),
            )

        e = result.get("czesc_E", {})
        with col2:
            st.metric(
                i18n("crypto_income", lang),
                format_pln(e.get("dochod_pln", Decimal(0))),
            )

        d = result.get("czesc_D", {})
        with col3:
            st.metric(
                i18n("dividend_income", lang),
                format_pln(d.get("przychod_pln", Decimal(0))),
            )

        with col4:
            st.metric(
                i18n("tax_to_pay", lang),
                format_pln(result.get("podatek_do_zaplaty", Decimal(0))),
            )

        st.divider()

        # PIT-38 fields
        st.subheader("Pola PIT-38")

        pit38_cols = st.columns(3)

        with pit38_cols[0]:
            st.markdown("### Część C: Papiery wartościowe")
            st.write(f"Przychód: {format_pln(c.get('przychod_pln', Decimal(0)))}")
            st.write(f"Koszt: {format_pln(c.get('koszt_pln', Decimal(0)))}")
            st.write(f"Dochód: {format_pln(c.get('dochod_pln', Decimal(0)))}")

        with pit38_cols[1]:
            st.markdown("### Część D: Dywidendy")
            st.write(f"Przychód: {format_pln(d.get('przychod_pln', Decimal(0)))}")
            st.write(f"Podatek zagranica: {format_pln(d.get('podatek_zagraniczny', Decimal(0)))}")
            st.write(f"Do zapłaty: {format_pln(d.get('podatek_do_zaplaty', Decimal(0)))}")

        with pit38_cols[2]:
            st.markdown("### Część E: Kryptowaluty")
            st.write(f"Przychód: {format_pln(e.get('przychod_pln', Decimal(0)))}")
            st.write(f"Koszt: {format_pln(e.get('koszt_pln', Decimal(0)))}")
            st.write(f"Dochód: {format_pln(e.get('dochod_pln', Decimal(0)))}")

        st.divider()

        # Download buttons
        st.subheader("💾 Pobierz raporty")

        col1, col2, col3 = st.columns(3)

        with col1:
            # Generate Excel
            try:
                report_gen = ReportGenerator(Path("/tmp"))
                detail = result.get("_detail", {})
                stocks = detail.get("stocks", [])
                crypto = detail.get("crypto", [])
                dividends = detail.get("dividends", [])
                nbp_rates = detail.get("nbp_rates_used", {})

                excel_path = report_gen.generate_excel(
                    result,
                    stocks,
                    crypto,
                    dividends,
                    nbp_rates,
                    filename=f"pit38_{st.session_state.tax_year}.xlsx",
                )
                with open(excel_path, "rb") as f:
                    st.download_button(
                        label="📊 Pobierz Excel",
                        data=f.read(),
                        file_name=excel_path.name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
            except Exception as e:
                st.error(f"Błąd generowania Excel: {e}")

        with col2:
            # Generate JSON (full audit)
            try:
                detail = result.get("_detail", {})
                stocks = detail.get("stocks", [])
                crypto = detail.get("crypto", [])
                dividends = detail.get("dividends", [])
                nbp_rates = detail.get("nbp_rates_used", {})

                audit_trail = generate_audit_trail(
                    stocks, crypto, dividends, nbp_rates
                )
                json_data = json.dumps(
                    {
                        "metadata": {
                            "tax_year": int(st.session_state.tax_year),
                            "generated_at": datetime.now().isoformat(),
                            "language": st.session_state.language,
                        },
                        "summary": {
                            "total_income": float(
                                result.get("dochod_razem", Decimal(0))
                            ),
                            "tax_to_pay": float(
                                result.get("podatek_do_zaplaty", Decimal(0))
                            ),
                        },
                        "audit_trail": audit_trail,
                        "pit38_result": {
                            k: v for k, v in result.items() if k != "_detail"
                        },
                    },
                    indent=2,
                    default=str,
                )
                st.download_button(
                    label="🔍 Pobierz JSON",
                    data=json_data,
                    file_name=f"pit38_{st.session_state.tax_year}_audit.json",
                    mime="application/json",
                )
            except Exception as e:
                st.error(f"Błąd generowania JSON: {e}")

        with col3:
            # Generate PDF audit report (formal — for accountant)
            try:
                try:
                    from revolut_pit.pdf_audit import generate_audit_pdf
                except ImportError as ie:
                    if "reportlab" in str(ie):
                        st.warning(
                            "📄 PDF wymaga `reportlab`. Zainstaluj:\n\n"
                            "```bash\npip install reportlab\n```\n\n"
                            "albo: `pip install -e .` (zaktualizuje wszystkie zależności)"
                        )
                        raise
                    raise

                import tempfile

                pdf_tmp = Path(tempfile.gettempdir()) / f"pit38_{st.session_state.tax_year}_audyt.pdf"
                generate_audit_pdf(
                    pit38_result=result,
                    output_path=pdf_tmp,
                    user_identifier=st.session_state.get("user_identifier") or None,
                    tax_year=int(st.session_state.tax_year),
                )
                with open(pdf_tmp, "rb") as f:
                    st.download_button(
                        label="📄 PDF dla księgowej",
                        data=f.read(),
                        file_name=pdf_tmp.name,
                        mime="application/pdf",
                        help="Formalny raport audytowy z odnośnikami do ustaw — do przekazania księgowej",
                    )
            except ImportError:
                pass  # message already shown above
            except Exception as e:
                st.error(f"Błąd generowania PDF: {e}")

        st.markdown("[🌐 Złóż deklarację w e-Urząd Skarbowy](https://www.podatki.gov.pl/)")

        st.divider()

        # Disclaimer
        st.warning(
            f"""
            ⚠️ **{i18n('disclaimer', lang)}**

            This tool is provided as-is for informational purposes.
            Always verify calculations with a qualified tax advisor before filing.
            """
        )

    # Buttons
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("← Wstecz", use_container_width=True):
            st.session_state.step = 5
            st.rerun()
    with col2:
        if st.button("🔄 Resetuj", use_container_width=True):
            for key in list(st.session_state.keys()):
                if key not in ["language", "tax_year"]:
                    del st.session_state[key]
            st.session_state.step = 0
            st.rerun()
    with col3:
        st.markdown("✅ Zakoczono!")
