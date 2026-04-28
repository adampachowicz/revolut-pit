"""Dividend tax calculation with foreign tax credit."""

from decimal import Decimal
from typing import Dict, List, Tuple


class DividendCalculator:
    """Calculate Polish dividend tax (PIT part D) with WHT credit."""

    # Treaty withholding rates by country
    TREATY_RATES = {
        "US": Decimal("0.15"),
        "DE": Decimal("0.15"),
        "NL": Decimal("0.15"),
        "GB": Decimal("0.10"),
    }

    DEFAULT_TREATY_RATE = Decimal("0.15")
    POLISH_TAX_RATE = Decimal("0.19")

    def calculate_dividend(
        self,
        gross_pln: Decimal,
        wht_pln: Decimal,
        country_code: str,
        symbol: str = "",
    ) -> Dict:
        """
        Calculate dividend tax with foreign tax credit.

        Args:
            gross_pln: Gross dividend in PLN
            wht_pln: Withholding tax paid in PLN
            country_code: ISO country code (e.g., 'US', 'DE')
            symbol: Stock ticker (for reporting)

        Returns:
            {
                'symbol': str,
                'country_code': str,
                'gross_pln': Decimal,
                'wht_paid_pln': Decimal,
                'polish_tax_19': Decimal,  # 19% of gross
                'treaty_rate': Decimal,
                'treaty_cap': Decimal,  # max WHT credit
                'tax_credit': Decimal,  # min(wht_paid, treaty_cap)
                'tax_to_pay': Decimal,  # max(0, polish_tax - credit)
                'warning': str or None,
            }
        """
        treaty_rate = self.TREATY_RATES.get(country_code, self.DEFAULT_TREATY_RATE)
        polish_tax = gross_pln * self.POLISH_TAX_RATE
        treaty_cap = gross_pln * treaty_rate
        tax_credit = min(wht_pln, treaty_cap)
        tax_to_pay = max(Decimal(0), polish_tax - tax_credit)

        warning = None
        if wht_pln > treaty_cap:
            warning = (
                f"⚠ {symbol or country_code}: WHT {wht_pln} PLN "
                f"exceeds treaty cap {treaty_cap:.2f} PLN. "
                f"Check W-8BEN or treaty terms."
            )

        return {
            "symbol": symbol,
            "country_code": country_code,
            "gross_pln": gross_pln,
            "wht_paid_pln": wht_pln,
            "polish_tax_19": polish_tax,
            "treaty_rate": treaty_rate,
            "treaty_cap": treaty_cap,
            "tax_credit": tax_credit,
            "tax_to_pay": tax_to_pay,
            "warning": warning,
        }

    def calculate_batch(
        self, dividends: List[Tuple[str, str, Decimal, Decimal]]
    ) -> Tuple[List[Dict], List[str]]:
        """
        Calculate dividends in batch.

        Args:
            dividends: List of (symbol, country_code, gross_pln, wht_pln)

        Returns:
            (results, warnings)
        """
        results = []
        warnings = []

        for symbol, country_code, gross_pln, wht_pln in dividends:
            result = self.calculate_dividend(gross_pln, wht_pln, country_code, symbol)
            results.append(result)
            if result["warning"]:
                warnings.append(result["warning"])

        return results, warnings
