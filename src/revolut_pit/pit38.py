"""PIT-38 form generator.

Polish capital gains tax law treats securities (Part C) and crypto (Part E)
as SEPARATE sources of income. Per art. 22 ust. 14 and art. 30b ust. 1a PIT,
losses cannot cross between them — a crypto loss does NOT offset a stock gain.

Key legal references:
- Art. 9 ust. 3 PIT — loss carry-forward 5 years; cap 5M PLN/year (sentence 2)
- Art. 9 ust. 6 PIT — losses applied within the same source only
- Art. 30b ust. 1 PIT — securities, 19% flat
- Art. 30b ust. 1a PIT — crypto, 19% flat (separate source)
- Art. 30a ust. 1 pkt 4 + ust. 7 PIT — dividends, 19% withholding, NOT combined
  with art. 30b income; foreign WHT credit per art. 30a ust. 9 i 11.
"""

from decimal import Decimal
from typing import Dict, List

# Art. 9 ust. 3 zd. 2 PIT: max 5,000,000 PLN deductible in a single year
# (any excess remains carried forward within the 5-year window).
LOSS_CAP_PER_YEAR = Decimal("5000000")
TAX_RATE = Decimal("0.19")


class PIT38Generator:
    """Generate PIT-38 tax form values from calculator results."""

    def __init__(self, tax_year: int):
        """Initialize generator for a specific tax year."""
        self.tax_year = tax_year

    def generate(
        self,
        stocks: List[Dict],
        crypto: List[Dict],
        dividends: List[Dict],
        prior_year_loss_c: Decimal = Decimal(0),
        prior_year_loss_e: Decimal = Decimal(0),
    ) -> Dict:
        """
        Generate PIT-38 form structure.

        Losses are tracked separately per source (art. 9 ust. 6 PIT):
        - prior_year_loss_c: losses from securities (Part C) carried forward
        - prior_year_loss_e: losses from crypto (Part E) carried forward

        A crypto loss CANNOT offset a securities gain and vice versa.

        Each section reports both `dochod_pln` (gain) and `strata_pln` (loss),
        so the caller knows the current-year loss to carry forward (art. 9 ust. 3).

        Returns a dict with keys: rok_podatkowy, czesc_C, czesc_D, czesc_E,
        czesc_G, pit_zg, dochod_razem, podatek_do_zaplaty, warnings.
        """
        warnings: List[str] = []

        czesc_c = self._aggregate_section(stocks)
        czesc_e = self._aggregate_section(crypto)
        czesc_d = self._aggregate_dividends(dividends)

        # Apply prior-year losses, per-source, with the 5M PLN annual cap.
        applied_c, remaining_c = self._apply_prior_loss(
            prior_year_loss_c, czesc_c["dochod_pln"], "C", warnings
        )
        applied_e, remaining_e = self._apply_prior_loss(
            prior_year_loss_e, czesc_e["dochod_pln"], "E", warnings
        )

        dochod_c_after_loss = max(Decimal(0), czesc_c["dochod_pln"] - applied_c)
        dochod_e_after_loss = max(Decimal(0), czesc_e["dochod_pln"] - applied_e)

        czesc_c["dochod_po_stracie_pln"] = dochod_c_after_loss
        czesc_e["dochod_po_stracie_pln"] = dochod_e_after_loss

        czesc_g = {
            "strata_z_lat_ubieglych_c": prior_year_loss_c,
            "strata_z_lat_ubieglych_e": prior_year_loss_e,
            "applied_loss_c": applied_c,
            "applied_loss_e": applied_e,
            "remaining_loss_carryforward_c": remaining_c,
            "remaining_loss_carryforward_e": remaining_e,
        }

        # Current-year losses — to be carried into NEXT year's prior_year_loss_*.
        # Reported so the user does not lose the carry-forward right (art. 9 ust. 3).
        if czesc_c["strata_pln"] > 0:
            warnings.append(
                f"Strata bieżącego roku z części C (papiery wartościowe): "
                f"{czesc_c['strata_pln']} PLN — zachowaj do rozliczenia w latach "
                f"{self.tax_year + 1}–{self.tax_year + 5} (art. 9 ust. 3 PIT)."
            )
        if czesc_e["strata_pln"] > 0:
            warnings.append(
                f"Strata bieżącego roku z części E (kryptowaluty): "
                f"{czesc_e['strata_pln']} PLN — zachowaj do rozliczenia w latach "
                f"{self.tax_year + 1}–{self.tax_year + 5} (art. 22 ust. 16 PIT)."
            )

        # `dochod_razem`: total taxable capital-gains income (C + E after losses).
        # Dividends (Part D) are NOT included — art. 30a ust. 7 PIT prohibits
        # combining art. 30a (dividends) with art. 30b (capital gains) income.
        dochod_razem = dochod_c_after_loss + dochod_e_after_loss

        tax_c = (dochod_c_after_loss * TAX_RATE).quantize(Decimal("0.01"))
        tax_e = (dochod_e_after_loss * TAX_RATE).quantize(Decimal("0.01"))
        tax_d = czesc_d["podatek_do_zaplaty"]

        podatek_do_zaplaty = tax_c + tax_e + tax_d

        pit_zg = [
            {
                "kraj": div.get("country_code", "XX"),
                "dochod_pln": div.get("gross_pln", Decimal(0)),
                "podatek_zagraniczny_pln": div.get("wht_paid_pln", Decimal(0)),
            }
            for div in dividends
        ]

        return {
            "rok_podatkowy": self.tax_year,
            "czesc_C": czesc_c,
            "czesc_D": czesc_d,
            "czesc_E": czesc_e,
            "czesc_G": czesc_g,
            "pit_zg": pit_zg,
            "dochod_razem": dochod_razem,
            "podatek_czesc_C": tax_c,
            "podatek_czesc_E": tax_e,
            "podatek_czesc_D": tax_d,
            "podatek_do_zaplaty": podatek_do_zaplaty,
            "warnings": warnings,
        }

    def _apply_prior_loss(
        self,
        prior_loss: Decimal,
        current_income: Decimal,
        section: str,
        warnings: List[str],
    ) -> tuple[Decimal, Decimal]:
        """Apply prior-year loss to current income with the 5M PLN annual cap.

        Returns (applied_loss, remaining_loss_carryforward).
        """
        if prior_loss <= 0 or current_income <= 0:
            return Decimal(0), prior_loss

        capped = min(prior_loss, LOSS_CAP_PER_YEAR)
        # Cannot apply more than the income itself.
        applied = min(capped, current_income)
        remaining = prior_loss - applied

        warnings.append(
            f"Strata z lat ubiegłych zastosowana w części {section}: "
            f"{applied} PLN (limit roczny 5 mln PLN — art. 9 ust. 3 PIT)."
        )
        if prior_loss > LOSS_CAP_PER_YEAR:
            warnings.append(
                f"⚠ Strata {prior_loss} PLN w części {section} przekracza roczny "
                f"limit 5 mln PLN — pozostała kwota {remaining} PLN przechodzi "
                f"na kolejne lata."
            )
        return applied, remaining

    def _aggregate_section(self, transactions: List[Dict]) -> Dict:
        """Aggregate a capital-gains section (C or E).

        Reports both `dochod_pln` (positive gain) and `strata_pln` (positive
        loss magnitude). Exactly one of them is non-zero. The raw signed
        balance is also returned as `bilans_pln` for transparency.
        """
        przychod = Decimal(0)
        koszt = Decimal(0)

        for tx in transactions:
            przychod += tx.get("proceeds_pln", Decimal(0))
            koszt += tx.get("cost_basis_pln", Decimal(0))

        bilans = przychod - koszt

        return {
            "przychod_pln": przychod,
            "koszt_pln": koszt,
            "bilans_pln": bilans,
            "dochod_pln": max(Decimal(0), bilans),
            "strata_pln": max(Decimal(0), -bilans),
        }

    def _aggregate_dividends(self, dividends: List[Dict]) -> Dict:
        """Aggregate dividend section (D)."""
        przychod = Decimal(0)
        podatek_19 = Decimal(0)
        podatek_zagraniczny = Decimal(0)
        podatek_do_zaplaty = Decimal(0)

        for div in dividends:
            przychod += div.get("gross_pln", Decimal(0))
            podatek_19 += div.get("polish_tax_19", Decimal(0))
            podatek_zagraniczny += div.get("wht_paid_pln", Decimal(0))
            podatek_do_zaplaty += div.get("tax_to_pay", Decimal(0))

        return {
            "przychod_pln": przychod,
            "podatek_pl_19": podatek_19,
            "podatek_zagraniczny": podatek_zagraniczny,
            "podatek_do_zaplaty": podatek_do_zaplaty,
        }
