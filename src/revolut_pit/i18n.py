"""Internationalization (i18n) support for revolut-pit.

Provides Polish and English translations for UI strings.
Polish is the primary language with full translations.
English is secondary with complete translations as well.
"""

from typing import Dict, Literal

# Type alias for supported languages
Language = Literal["pl", "en"]

# Comprehensive translation dictionary
TRANSLATIONS: Dict[str, Dict[Language, str]] = {
    # Sidebar
    "title": {
        "pl": "revolut-pit",
        "en": "revolut-pit",
    },
    "version": {
        "pl": "Wersja",
        "en": "Version",
    },
    "settings": {
        "pl": "Ustawienia",
        "en": "Settings",
    },
    "language": {
        "pl": "Język",
        "en": "Language",
    },
    "tax_year": {
        "pl": "Rok podatkowy",
        "en": "Tax Year",
    },
    "prior_loss": {
        "pl": "Strata z lat ubiegłych (PLN)",
        "en": "Loss carry-forward (PLN)",
    },
    "clear_nbp_cache": {
        "pl": "Wyczyść pamięć NBP",
        "en": "Clear NBP cache",
    },
    "disclaimer": {
        "pl": "To narzędzie nie jest poradą podatkową. Zweryfikuj z księgową.",
        "en": "This tool is not tax advice. Verify with an accountant.",
    },
    # Upload stage
    "upload_title": {
        "pl": "Etap 1: Prześlij pliki",
        "en": "Stage 1: Upload files",
    },
    "upload_csv": {
        "pl": "Prześlij pliki CSV",
        "en": "Upload CSV files",
    },
    "upload_help": {
        "pl": "Obsługiwane: account_statement_YYYY.csv, profit_and_loss_YYYY.csv, crypto_* pliki",
        "en": "Supported: account_statement_YYYY.csv, profit_and_loss_YYYY.csv, crypto_* files",
    },
    "no_files": {
        "pl": "Nie przesłano plików",
        "en": "No files uploaded",
    },
    "files_uploaded": {
        "pl": "pliki przesłane",
        "en": "files uploaded",
    },
    "file_summary": {
        "pl": "Podsumowanie plików",
        "en": "File Summary",
    },
    "auto_detected": {
        "pl": "Auto-wykryte:",
        "en": "Auto-detected:",
    },
    "unknown_format": {
        "pl": "Nieznany format",
        "en": "Unknown format",
    },
    # Calculate stage
    "calculate_title": {
        "pl": "Etap 2: Oblicz",
        "en": "Stage 2: Calculate",
    },
    "calculate_button": {
        "pl": "Oblicz PIT-38",
        "en": "Calculate PIT-38",
    },
    "calculating": {
        "pl": "Trwa obliczanie...",
        "en": "Calculating...",
    },
    "fetching_nbp": {
        "pl": "Pobieranie kursów NBP...",
        "en": "Fetching NBP rates...",
    },
    "processing": {
        "pl": "Przetwarzanie transakcji...",
        "en": "Processing transactions...",
    },
    # Results stage
    "results_title": {
        "pl": "Etap 3: Wyniki",
        "en": "Stage 3: Results",
    },
    "summary_tab": {
        "pl": "Podsumowanie",
        "en": "Summary",
    },
    "stocks_tab": {
        "pl": "Akcje",
        "en": "Stocks",
    },
    "crypto_tab": {
        "pl": "Kryptowaluty",
        "en": "Crypto",
    },
    "dividends_tab": {
        "pl": "Dywidendy",
        "en": "Dividends",
    },
    "nbp_rates_tab": {
        "pl": "Kursy NBP",
        "en": "NBP Rates",
    },
    "cross_validation_tab": {
        "pl": "Krzyżowa weryfikacja",
        "en": "Cross-validation",
    },
    "warnings_tab": {
        "pl": "Ostrzeżenia",
        "en": "Warnings",
    },
    # Summary metrics
    "total_income": {
        "pl": "Całkowity dochód",
        "en": "Total Income",
    },
    "tax_to_pay": {
        "pl": "Podatek do zapłaty",
        "en": "Tax to Pay",
    },
    "securities_income": {
        "pl": "Dochód z papierów wartościowych",
        "en": "Securities Income",
    },
    "crypto_income": {
        "pl": "Dochód z kryptowalut",
        "en": "Crypto Income",
    },
    "dividend_income": {
        "pl": "Dochód z dywidend",
        "en": "Dividend Income",
    },
    # Part C (Securities)
    "part_c": {
        "pl": "Część C: Papiery wartościowe",
        "en": "Part C: Securities",
    },
    "proceeds": {
        "pl": "Przychód",
        "en": "Proceeds",
    },
    "cost": {
        "pl": "Koszt uzyskania przychodu",
        "en": "Cost",
    },
    "income": {
        "pl": "Dochód do opodatkowania",
        "en": "Taxable Income",
    },
    "tax_rate_19": {
        "pl": "Podatek 19%",
        "en": "Tax @ 19%",
    },
    # Part D (Dividends)
    "part_d": {
        "pl": "Część D: Dywidendy",
        "en": "Part D: Dividends",
    },
    "gross_income": {
        "pl": "Przychód brutto",
        "en": "Gross Income",
    },
    "withholding_tax": {
        "pl": "Podatek u źródła",
        "en": "Withholding Tax",
    },
    "foreign_tax_credit": {
        "pl": "Kredyt podatku zagranicznego",
        "en": "Foreign Tax Credit",
    },
    "treaty_rate": {
        "pl": "Stawka umowy",
        "en": "Treaty Rate",
    },
    # Part E (Crypto)
    "part_e": {
        "pl": "Część E: Kryptowaluty",
        "en": "Part E: Crypto",
    },
    "excluded_swaps": {
        "pl": "Wyłączone transakcje swap",
        "en": "Excluded SWAPs",
    },
    "swap_reason": {
        "pl": "Transakcje swap kryptowalut są zwolnione z opodatkowania",
        "en": "Crypto-to-crypto SWAPs are non-taxable",
    },
    # Part G (Prior losses)
    "part_g": {
        "pl": "Część G: Straty z lat ubiegłych",
        "en": "Part G: Prior-year losses",
    },
    # Column headers
    "date": {
        "pl": "Data",
        "en": "Date",
    },
    "date_acquired": {
        "pl": "Data nabycia",
        "en": "Date Acquired",
    },
    "date_sold": {
        "pl": "Data sprzedaży",
        "en": "Date Sold",
    },
    "symbol": {
        "pl": "Symbol",
        "en": "Symbol",
    },
    "quantity": {
        "pl": "Ilość",
        "en": "Quantity",
    },
    "currency": {
        "pl": "Waluta",
        "en": "Currency",
    },
    "cost_foreign": {
        "pl": "Koszt (waluta obca)",
        "en": "Cost (Foreign)",
    },
    "proceeds_foreign": {
        "pl": "Przychód (waluta obca)",
        "en": "Proceeds (Foreign)",
    },
    "nbp_rate_acquired": {
        "pl": "Kurs NBP (nabycie)",
        "en": "NBP Rate (Acquired)",
    },
    "nbp_rate_sold": {
        "pl": "Kurs NBP (sprzedaż)",
        "en": "NBP Rate (Sold)",
    },
    "cost_pln": {
        "pl": "Koszt (PLN)",
        "en": "Cost (PLN)",
    },
    "proceeds_pln": {
        "pl": "Przychód (PLN)",
        "en": "Proceeds (PLN)",
    },
    "gain_pln": {
        "pl": "Zysk (PLN)",
        "en": "Gain (PLN)",
    },
    "total": {
        "pl": "Razem",
        "en": "Total",
    },
    # Audit & Verification
    "nbp_rate": {
        "pl": "Kurs NBP",
        "en": "NBP Rate",
    },
    "rate_source": {
        "pl": "Źródło kursu",
        "en": "Rate Source",
    },
    "verify_nbp": {
        "pl": "Weryfikuj w NBP",
        "en": "Verify at NBP",
    },
    "cross_validate": {
        "pl": "Krzyżowa weryfikacja",
        "en": "Cross-validation",
    },
    "cross_validate_text": {
        "pl": "Porównanie całkowitych przychodów (PLN converted back to USD) vs. Revolut",
        "en": "Comparison of total proceeds (PLN converted back to USD) vs. Revolut",
    },
    "drift": {
        "pl": "Odchylenie",
        "en": "Drift",
    },
    "drift_ok": {
        "pl": "W normie (< 0.5%)",
        "en": "OK (< 0.5%)",
    },
    "drift_warn": {
        "pl": "Ostrzeżenie (> 0.5%)",
        "en": "Warning (> 0.5%)",
    },
    # Warnings
    "warnings": {
        "pl": "Ostrzeżenia",
        "en": "Warnings",
    },
    "no_warnings": {
        "pl": "Brak ostrzeżeń",
        "en": "No warnings",
    },
    "w8ben_warning": {
        "pl": "Brak formularza W-8BEN dla USA",
        "en": "Missing W-8BEN form for USA",
    },
    "w8ben_info": {
        "pl": "Rozważ składanie formularza W-8BEN aby zmniejszyć stawkę WHT z 30% na 15%",
        "en": "Consider filing W-8BEN form to reduce WHT rate from 30% to 15%",
    },
    # Downloads
    "download_excel": {
        "pl": "Pobierz Excel",
        "en": "Download Excel",
    },
    "download_markdown": {
        "pl": "Pobierz Markdown",
        "en": "Download Markdown",
    },
    "download_json": {
        "pl": "Pobierz JSON (pełny audit)",
        "en": "Download JSON (full audit)",
    },
    "filename_pit38": {
        "pl": "pit38",
        "en": "pit38",
    },
    # Error messages
    "error_no_data": {
        "pl": "Brak danych do przetworzenia",
        "en": "No data to process",
    },
    "error_parsing": {
        "pl": "Błąd analizy pliku",
        "en": "Error parsing file",
    },
    "error_nbp": {
        "pl": "Błąd pobierania kursów NBP",
        "en": "Error fetching NBP rates",
    },
    "error_fetching_nbp": {
        "pl": "Błąd pobierania kursów NBP",
        "en": "Error fetching NBP rates",
    },
    # Wizard specific
    "wizard": {
        "pl": "Kreator PIT-38",
        "en": "PIT-38 Wizard",
    },
    "step": {
        "pl": "Krok",
        "en": "Step",
    },
    "nbp_rates_step": {
        "pl": "Pobranie kursów NBP",
        "en": "NBP Rates Fetching",
    },
    "nbp_rates_help": {
        "pl": "Pobieramy aktualne kursy NBP dla wszystkich walut z Twoich transakcji.",
        "en": "Fetching current NBP rates for all currencies in your transactions.",
    },
    "nbp_rates_table": {
        "pl": "Tabela kursów NBP",
        "en": "NBP Rates Table",
    },
    "crypto_swaps_step": {
        "pl": "Wykrywanie SWAP-ów krypto",
        "en": "Crypto SWAP Detection",
    },
    "crypto_swaps_help": {
        "pl": "Identyfikujemy transakcje swap kryptowalut (nie podlegające opodatkowaniu).",
        "en": "Identifying crypto swap transactions (non-taxable events).",
    },
    "stocks_step": {
        "pl": "Akcje — FIFO + przeliczenie PLN",
        "en": "Stocks — FIFO + PLN Conversion",
    },
    "stocks_help": {
        "pl": "Przeglądaj wszystkie pozycje akcji z zastosowaniem metody FIFO.",
        "en": "Review all stock positions using FIFO method.",
    },
    "dividends_step": {
        "pl": "Dywidendy + kredyt zagraniczny WHT",
        "en": "Dividends + Foreign Tax Credit",
    },
    "dividends_help": {
        "pl": "Przegląd dywidend, podatków u źródła i kredytu zagranicznego.",
        "en": "Review dividends, withholding tax, and foreign tax credits.",
    },
    "prior_loss_step": {
        "pl": "Strata z lat ubiegłych",
        "en": "Prior Year Losses",
    },
    "prior_loss_help": {
        "pl": "Wprowadź stratę z lat ubiegłych do odliczenia (max 5M PLN/rok).",
        "en": "Enter prior year losses to deduct (max 5M PLN/year).",
    },
    "prior_loss_amount": {
        "pl": "Kwota straty (PLN)",
        "en": "Loss Amount (PLN)",
    },
    "final_review_step": {
        "pl": "Finalne pola PIT-38 + audyt",
        "en": "Final PIT-38 Fields + Audit",
    },
    "final_review_help": {
        "pl": "Przegląd ostatecznego PIT-38 i pobierz raporty.",
        "en": "Review final PIT-38 and download reports.",
    },
}


def t(key: str, lang: Language = "pl") -> str:
    """
    Get translated string for the given key and language.

    Args:
        key: Translation key (e.g., 'tax_year', 'calculate_button')
        lang: Language code ('pl' or 'en'), defaults to 'pl'

    Returns:
        Translated string, or key itself if translation not found

    Example:
        >>> t('tax_year', 'pl')
        'Rok podatkowy'
        >>> t('tax_year', 'en')
        'Tax Year'
    """
    if key not in TRANSLATIONS:
        return key

    lang_dict = TRANSLATIONS[key]
    if lang not in lang_dict:
        return key

    return lang_dict[lang]


def get_all_translations(lang: Language = "pl") -> Dict[str, str]:
    """
    Get all translations for a specific language.

    Args:
        lang: Language code ('pl' or 'en')

    Returns:
        Dictionary mapping keys to translations
    """
    result = {}
    for key, lang_dict in TRANSLATIONS.items():
        if lang in lang_dict:
            result[key] = lang_dict[lang]
        else:
            result[key] = key
    return result
