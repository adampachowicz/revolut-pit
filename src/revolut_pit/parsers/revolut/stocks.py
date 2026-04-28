"""Parser for Revolut stock trading data."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import pandas as pd

from .._common import parse_amount, parse_amount_with_currency
from ..base import BrokerStockParser


class RevolutStocksParser(BrokerStockParser):
    """Parse Revolut account_statement and profit_and_loss CSV files for stocks."""

    @property
    def name(self) -> str:
        """Broker name."""
        return "Revolut"

    @property
    def version(self) -> str:
        """Parser version."""
        return "1.0.0"

    def __init__(self, year: int):
        """Initialize parser for a specific tax year."""
        self.year = year

    def detect(self, filepath: Path) -> bool:
        """
        Auto-detect if this is a Revolut stocks CSV.

        Checks for:
        - Filename contains 'profit_and_loss' or 'account_statement'
        - Not 'crypto_' prefix
        - File contains expected columns

        Args:
            filepath: Path to potential Revolut stocks CSV

        Returns:
            True if detected as Revolut stocks file, False otherwise
        """
        filename = filepath.name.lower()

        # Skip crypto files
        if "crypto" in filename:
            return False

        # Check for stock-related filenames
        if "profit_and_loss" not in filename and "account_statement" not in filename:
            return False

        try:
            # Try to read first line to check columns
            with open(filepath, "r") as f:
                first_line = f.readline()
                # Revolut stocks files have specific column headers
                if "Income from Sells" in first_line or "Ticker" in first_line:
                    return True
        except Exception:
            pass

        return False

    def parse_account_statement(self, filepath: Path) -> List[Dict]:
        """
        Parse account_statement_YYYY.csv.

        Returns list of transactions with standardized fields:
        {
            'date': datetime,
            'ticker': str,
            'type': str,
            'quantity': Decimal,
            'price_per_share': Decimal,
            'total_amount': Decimal,
            'currency': str,
            'fx_rate_revolut': Decimal,
        }

        Args:
            filepath: Path to account_statement CSV

        Returns:
            List of transaction dicts
        """
        df = pd.read_csv(filepath)
        transactions = []

        for _, row in df.iterrows():
            try:
                date = pd.to_datetime(row["Date"])

                # Extract currency and amount from "USD 1.78" / "$1.78" / "1.78 USD" format
                total_amount, currency_in_total = parse_amount_with_currency(
                    row["Total Amount"]
                )
                # Currency column wins if present
                currency = (
                    str(row.get("Currency", "")).strip()
                    or currency_in_total
                    or "PLN"
                )

                price_amt, _ = parse_amount_with_currency(row.get("Price per share", 0))
                qty_str = str(row.get("Quantity", 0)).strip()
                qty = parse_amount(qty_str) if qty_str else Decimal(0)
                fx_str = str(row.get("FX Rate", 0)).strip()
                fx = (
                    parse_amount(fx_str)
                    if fx_str and fx_str.lower() != "nan"
                    else Decimal(0)
                )

                transaction = {
                    "date": date,
                    "ticker": str(row.get("Ticker", "")).strip(),
                    "type": str(row.get("Type", "")).strip(),
                    "quantity": qty,
                    "price_per_share": price_amt,
                    "total_amount": total_amount,
                    "currency": currency,
                    "fx_rate_revolut": fx,
                }
                transactions.append(transaction)
            except Exception as e:
                print(f"Warning: Could not parse row: {e}")
                continue

        return transactions

    def parse_profit_and_loss(self, filepath: Path) -> Tuple[List[Dict], List[Dict]]:
        """
        Parse profit_and_loss_YYYY.csv.

        Returns:
            (sells, other_income) tuple

        sells: [{
            'date_acquired': datetime,
            'date_sold': datetime,
            'symbol': str,
            'security_name': str,
            'isin': str,
            'country': str,
            'quantity': Decimal,
            'cost_basis': Decimal,
            'gross_proceeds': Decimal,
            'gross_pnl': Decimal,
            'currency': str,
        }]

        other_income: [{
            'date': datetime,
            'symbol': str,
            'security_name': str,
            'isin': str,
            'country': str,
            'gross_amount': Decimal,
            'withholding_tax': Decimal,
            'net_amount': Decimal,
            'currency': str,
        }]

        Args:
            filepath: Path to profit_and_loss CSV

        Returns:
            Tuple of (sells, other_income) in standardized format
        """
        with open(filepath, "r") as f:
            content = f.read()

        sections = content.split("\n\n")
        sells = []
        other_income = []

        for section in sections:
            if "Income from Sells" in section:
                df = pd.read_csv(
                    pd.io.common.StringIO(section.replace("Income from Sells\n", ""))
                )
                for _, row in df.iterrows():
                    try:
                        sell = {
                            "date_acquired": pd.to_datetime(row["Date acquired"]),
                            "date_sold": pd.to_datetime(row["Date sold"]),
                            "symbol": str(row.get("Symbol", "")).strip(),
                            "security_name": str(row.get("Security name", "")).strip(),
                            "isin": str(row.get("ISIN", "")).strip(),
                            "country": str(row.get("Country", "")).strip(),
                            "quantity": parse_amount(row.get("Quantity", 0)),
                            "cost_basis": parse_amount(row.get("Cost basis", 0)),
                            "gross_proceeds": parse_amount(row.get("Gross proceeds", 0)),
                            "gross_pnl": parse_amount(row.get("Gross PnL", 0)),
                            "currency": str(row.get("Currency", "USD")).strip(),
                        }
                        sells.append(sell)
                    except Exception as e:
                        print(f"Warning: Could not parse sell transaction: {e}")

            if "Other income" in section:
                df = pd.read_csv(
                    pd.io.common.StringIO(section.replace("Other income & fees\n", ""))
                )
                for _, row in df.iterrows():
                    try:
                        income = {
                            "date": pd.to_datetime(row["Date"]),
                            "symbol": str(row.get("Symbol", "")).strip(),
                            "security_name": str(row.get("Security name", "")).strip(),
                            "isin": str(row.get("ISIN", "")).strip(),
                            "country": str(row.get("Country", "")).strip(),
                            "gross_amount": parse_amount(row.get("Gross amount", 0)),
                            "withholding_tax": parse_amount(row.get("Withholding tax", 0)),
                            "net_amount": parse_amount(row.get("Net Amount", 0)),
                            "currency": str(row.get("Currency", "USD")).strip(),
                        }
                        other_income.append(income)
                    except Exception as e:
                        print(f"Warning: Could not parse other income: {e}")

        return sells, other_income
