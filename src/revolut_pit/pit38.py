"""PIT-38 form generator."""

from decimal import Decimal
from typing import Dict, List, Optional

# Polish law (art. 7e ust. 3 PIT): max 5,000,000 PLN deducted in a single year
LOSS_CAP_PER_YEAR = Decimal("5000000")


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
        prior_year_loss: Decimal = Decimal(0),
    ) -> Dict:
        """
        Generate PIT-38 form structure.

        Args:
            stocks: List of stock sale results from calculator
            crypto: List of crypto sale results from calculator
            dividends: List of dividend results from calculator
            prior_year_loss: Loss carry-forward from prior years

        Returns:
            {
                'rok_podatkowy': int,
                'czesc_C': {  # Securities
                    'przychod_pln': Decimal,
                    'koszt_pln': Decimal,
                    'dochod_pln': Decimal,
                },
                'czesc_D': {  # Dividends
                    'przychod_pln': Decimal,
                    'podatek_pl_19': Decimal,
                    'podatek_zagraniczny': Decimal,
                    'podatek_do_zaplaty': Decimal,
                },
                'czesc_E': {  # Crypto
                    'przychod_pln': Decimal,
                    'koszt_pln': Decimal,
                    'dochod_pln': Decimal,
                },
                'czesc_G': {  # Prior losses
                    'strata_z_lat_ubieglych': Decimal,
                    'applied_loss': Decimal,
                    'remaining_loss_carryforward': Decimal,
                },
                'pit_zg': [  # Foreign income attachment
                    {'kraj': str, 'dochod_pln': Decimal, 'podatek_zagraniczny_pln': Decimal},
                ],
                'dochod_razem': Decimal,
                'podatek_do_zaplaty': Decimal,
                'warnings': [str],
            }
        """
        warnings = []

        # Part C: Securities (stocks)
        czesc_c = self._aggregate_section(stocks)

        # Part E: Crypto
        czesc_e = self._aggregate_section(crypto)

        # Part D: Dividends
        czesc_d = self._aggregate_dividends(dividends)

        # Aggregate income from capital gains sections (C + E)
        capital_gains_income = czesc_c["dochod_pln"] + czesc_e["dochod_pln"]

        # Part G: Prior losses with 5M PLN annual cap (art. 7e ust. 3 PIT)
        applied_loss = Decimal(0)
        remaining_loss_carryforward = prior_year_loss

        if prior_year_loss > 0 and capital_gains_income > 0:
            # Cap the deduction at 5M PLN per year
            applied_loss = min(prior_year_loss, LOSS_CAP_PER_YEAR)
            remaining_loss_carryforward = prior_year_loss - applied_loss

            # Reduce capital gains income by applied loss
            capital_gains_income = max(Decimal(0), capital_gains_income - applied_loss)

            warnings.append(
                f"Loss carry-forward applied: {applied_loss} PLN deducted from income"
            )

            if remaining_loss_carryforward > 0:
                warnings.append(
                    f"⚠ Strata {remaining_loss_carryforward} PLN przekracza roczny limit "
                    f"5 mln PLN — pozostała kwota {remaining_loss_carryforward} PLN "
                    f"przechodzi na kolejne lata"
                )

        czesc_g = {
            "strata_z_lat_ubieglych": prior_year_loss,
            "applied_loss": applied_loss,
            "remaining_loss_carryforward": remaining_loss_carryforward,
        }

        # Total taxable income (after loss application)
        dochod_razem = capital_gains_income + czesc_d["przychod_pln"]

        # Total tax to pay
        # Capital gains tax = reduced income (after loss) × 19%
        tax_securities_crypto = max(Decimal(0), capital_gains_income * Decimal("0.19"))
        tax_dividends = czesc_d["podatek_do_zaplaty"]

        podatek_do_zaplaty = tax_securities_crypto + tax_dividends

        # Build PIT/ZG (foreign income by country)
        pit_zg = []
        for div in dividends:
            pit_zg.append(
                {
                    "kraj": div.get("country_code", "XX"),
                    "dochod_pln": div.get("gross_pln", Decimal(0)),
                    "podatek_zagraniczny_pln": div.get("wht_paid_pln", Decimal(0)),
                }
            )

        return {
            "rok_podatkowy": self.tax_year,
            "czesc_C": czesc_c,
            "czesc_D": czesc_d,
            "czesc_E": czesc_e,
            "czesc_G": czesc_g,
            "pit_zg": pit_zg,
            "dochod_razem": dochod_razem,
            "podatek_do_zaplaty": podatek_do_zaplaty,
            "warnings": warnings,
        }

    def _aggregate_section(self, transactions: List[Dict]) -> Dict:
        """Aggregate capital gains section (C, E)."""
        przychod = Decimal(0)
        koszt = Decimal(0)

        for tx in transactions:
            przychod += tx.get("proceeds_pln", Decimal(0))
            koszt += tx.get("cost_basis_pln", Decimal(0))

        dochod = przychod - koszt

        return {
            "przychod_pln": przychod,
            "koszt_pln": koszt,
            "dochod_pln": max(Decimal(0), dochod),
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
