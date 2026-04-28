"""End-to-end PIT-38 calculation pipeline.

Glues together: parsers → NBP API → calculator → PIT-38 → reports.
"""

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .nbp import NBPClient
from .dividends import DividendCalculator
from .pit38 import PIT38Generator
from .parsers.stocks import StocksParser
from .parsers.crypto import CryptoParser


# Country detection from ISIN (first 2 chars)
ISIN_TO_COUNTRY = {
    "US": "US",
    "DE": "DE",
    "NL": "NL",
    "GB": "GB",
    "IE": "IE",
    "LU": "LU",
    "FR": "FR",
}


def isin_to_country(isin: str) -> str:
    """Extract country code from ISIN."""
    if isin and len(isin) >= 2:
        return isin[:2].upper()
    return "XX"


def round_grosz(amount: Decimal) -> Decimal:
    """Round to grosz (0.01 PLN), .5 rounds up — Polish tax rounding."""
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class Pipeline:
    """Orchestrates parsing → NBP fetches → calculations → PIT-38 generation."""

    def __init__(
        self,
        year: int,
        data_dir: Path,
        nbp_client: Optional[NBPClient] = None,
        verbose: bool = True,
    ):
        self.year = year
        self.data_dir = Path(data_dir)
        self.nbp = nbp_client or NBPClient()
        self.verbose = verbose
        self.div_calc = DividendCalculator()
        self.pit38_gen = PIT38Generator(tax_year=year)

        # Track all NBP rates fetched (for audit)
        self.nbp_rates_used: Dict[str, Decimal] = {}

    def log(self, msg: str):
        if self.verbose:
            print(msg)

    def _get_rate(self, currency: str, date) -> Decimal:
        """Get NBP D-1 rate and remember it for the audit sheet."""
        if isinstance(date, str):
            date = datetime.fromisoformat(date.replace("Z", "+00:00").split("T")[0])
        if hasattr(date, "to_pydatetime"):
            date = date.to_pydatetime()
        if hasattr(date, "date"):
            d = date.date() if hasattr(date, "date") else date
        else:
            d = date

        rate = self.nbp.get_rate(currency, d, use_d_minus_1=True)
        # remember which actual NBP day was used
        self.nbp_rates_used[f"{currency}_{d.isoformat()}"] = rate
        return rate

    # -- Stocks ---------------------------------------------------------------

    def process_stocks(self) -> Tuple[List[Dict], List[Dict]]:
        """
        Process stock P&L for the year.

        Returns:
            (closed_positions, dividend_results)
        """
        # Find P&L file (handle Revolut's typo "statment" + "statement")
        pnl_files = list(self.data_dir.glob(f"profit_and_loss*{self.year}.csv"))
        if not pnl_files:
            self.log(f"No stock P&L file found for {self.year}")
            return [], []

        pnl_path = pnl_files[0]
        self.log(f"Stock P&L: {pnl_path.name}")

        parser = StocksParser(year=self.year)
        sells, other_income = parser.parse_profit_and_loss(pnl_path)

        # Build ISIN → country map from dividends section (often more complete)
        isin_country_map: Dict[str, str] = {}
        for d in other_income:
            if d.get("isin") and d.get("country"):
                isin_country_map[d["isin"]] = d["country"]
        for s in sells:
            if s.get("isin") and s.get("country"):
                isin_country_map[s["isin"]] = s["country"]

        # Closed positions → PLN math
        closed = []
        for s in sells:
            currency = s["currency"]
            cost_rate = self._get_rate(currency, s["date_acquired"])
            sell_rate = self._get_rate(currency, s["date_sold"])

            cost_pln = round_grosz(s["cost_basis"] * cost_rate)
            proceeds_pln = round_grosz(s["gross_proceeds"] * sell_rate)
            gain_pln = proceeds_pln - cost_pln

            country = (
                s.get("country")
                or isin_country_map.get(s.get("isin", ""), "")
                or isin_to_country(s.get("isin", "") or "")
            )

            closed.append(
                {
                    "symbol": s["symbol"],
                    "isin": s.get("isin", ""),
                    "country_code": country,
                    "date_acquired": s["date_acquired"],
                    "date_sold": s["date_sold"],
                    "quantity": s["quantity"],
                    "currency": currency,
                    "cost_basis_foreign": s["cost_basis"],
                    "proceeds_foreign": s["gross_proceeds"],
                    "cost_rate_nbp": cost_rate,
                    "sell_rate_nbp": sell_rate,
                    "cost_basis_pln": cost_pln,
                    "proceeds_pln": proceeds_pln,
                    "gain_pln": gain_pln,
                }
            )

        # Dividends → PLN + WHT credit
        dividends = []
        for d in other_income:
            currency = d["currency"]
            if currency == "PLN":
                # Revolut already converted (newer exports); use values as-is
                rate = Decimal("1")
                gross_pln = round_grosz(d["gross_amount"])
                wht_pln = round_grosz(d["withholding_tax"])
            else:
                rate = self._get_rate(currency, d["date"])
                gross_pln = round_grosz(d["gross_amount"] * rate)
                wht_pln = round_grosz(d["withholding_tax"] * rate)

            country = (
                d.get("country")
                or isin_country_map.get(d.get("isin", ""), "")
                or isin_to_country(d.get("isin", "") or "")
                or "US"
            )

            div_result = self.div_calc.calculate_dividend(
                gross_pln=gross_pln,
                wht_pln=wht_pln,
                country_code=country,
                symbol=d["symbol"],
            )
            div_result["date"] = d["date"]
            div_result["currency"] = currency
            div_result["nbp_rate"] = rate
            div_result["gross_foreign"] = d["gross_amount"]
            div_result["wht_foreign"] = d["withholding_tax"]
            div_result["isin"] = d.get("isin", "")
            dividends.append(div_result)

        return closed, dividends

    # -- Crypto ---------------------------------------------------------------

    def process_crypto(self) -> List[Dict]:
        """
        Process crypto for the year, EXCLUDING token swaps (non-taxable in PL).
        """
        pnl_files = list(self.data_dir.glob(f"crypto_profit_and_loss*{self.year}.csv"))
        acct_files = list(self.data_dir.glob(f"crypto_account_statement*{self.year}.csv"))

        if not pnl_files:
            self.log(f"No crypto P&L file found for {self.year}")
            return []

        pnl_path = pnl_files[0]
        acct_path = acct_files[0] if acct_files else None
        self.log(f"Crypto P&L: {pnl_path.name}")

        parser = CryptoParser(year=self.year)

        # Detect swaps from account statement (exclude their dates from taxable P&L)
        swap_keys = set()
        if acct_path:
            try:
                txs = parser.parse_account_statement(acct_path)
                # parse_account_statement runs _detect_swaps and sets is_swap=True
                swap_count = 0
                for tx in txs:
                    if tx.get("is_swap") and tx.get("type", "").lower().startswith("sell"):
                        swap_keys.add((tx["symbol"], tx["date"].date()))
                        swap_count += 1
                if swap_count:
                    self.log(f"  Detected {swap_count} crypto swap(s) — excluded from PIT-38")
            except Exception as e:
                self.log(f"  Crypto account statement parse warning: {e}")

        # Read crypto P&L manually (it's a single-section CSV)
        import pandas as pd

        df = pd.read_csv(pnl_path)
        closed = []
        for _, row in df.iterrows():
            try:
                date_acq = pd.to_datetime(row["Date acquired"])
                date_sold = pd.to_datetime(row["Date sold"])
                symbol = str(row["Symbol"])
                qty = Decimal(str(row["Quantity"]))
                cost = Decimal(str(row["Cost basis"]))
                proceeds = Decimal(str(row["Gross proceeds"]))
                currency = str(row.get("Currency", "USD"))

                # Heuristic swap detection: same-day sell+buy, ~equal proceeds vs cost
                if abs(proceeds - cost) < Decimal("0.5") and (date_acq - date_sold).days < 365:
                    # Don't auto-skip — only skip if matches account-detected swap
                    pass

                if (symbol, date_sold.date()) in swap_keys:
                    self.log(f"  Skipping {symbol} {date_sold.date()} — token swap (non-taxable)")
                    continue

                cost_rate = self._get_rate(currency, date_acq)
                sell_rate = self._get_rate(currency, date_sold)

                cost_pln = round_grosz(cost * cost_rate)
                proceeds_pln = round_grosz(proceeds * sell_rate)
                gain_pln = proceeds_pln - cost_pln

                closed.append(
                    {
                        "symbol": symbol,
                        "date_acquired": date_acq,
                        "date_sold": date_sold,
                        "quantity": qty,
                        "currency": currency,
                        "cost_basis_foreign": cost,
                        "proceeds_foreign": proceeds,
                        "cost_rate_nbp": cost_rate,
                        "sell_rate_nbp": sell_rate,
                        "cost_basis_pln": cost_pln,
                        "proceeds_pln": proceeds_pln,
                        "gain_pln": gain_pln,
                    }
                )
            except Exception as e:
                self.log(f"  Crypto P&L row parse error: {e}")
                continue

        return closed

    # -- Top-level ------------------------------------------------------------

    def run(self, prior_year_loss: Decimal = Decimal(0)) -> Dict:
        """Run end-to-end and return full result dict."""
        self.log(f"\n{'='*60}\nrevolut-pit pipeline — year {self.year}\n{'='*60}")

        stocks, dividends = self.process_stocks()
        crypto = self.process_crypto()

        self.log(f"\nStock closed positions: {len(stocks)}")
        self.log(f"Dividends:              {len(dividends)}")
        self.log(f"Crypto closed (taxable): {len(crypto)}")

        pit38_result = self.pit38_gen.generate(
            stocks=stocks,
            crypto=crypto,
            dividends=dividends,
            prior_year_loss=prior_year_loss,
        )

        # Add detail for reports
        pit38_result["_detail"] = {
            "stocks": stocks,
            "crypto": crypto,
            "dividends": dividends,
            "nbp_rates_used": self.nbp_rates_used,
        }
        return pit38_result
