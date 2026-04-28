"""Parser for Revolut cryptocurrency trading data."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Dict

import pandas as pd

from .._common import parse_amount, parse_amount_with_currency
from ..base import BrokerCryptoParser


class RevolutCryptoParser(BrokerCryptoParser):
    """Parse Revolut crypto_account_statement and crypto_profit_and_loss CSVs."""

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
        Auto-detect if this is a Revolut crypto CSV.

        Checks for:
        - Filename contains 'crypto_account_statement' or 'crypto_profit_and_loss'
        - File contains expected columns

        Args:
            filepath: Path to potential Revolut crypto CSV

        Returns:
            True if detected as Revolut crypto file, False otherwise
        """
        filename = filepath.name.lower()

        # Check for crypto-related filenames
        if "crypto_account_statement" not in filename and "crypto_profit_and_loss" not in filename:
            return False

        try:
            # Try to read first line to check columns
            with open(filepath, "r") as f:
                first_line = f.readline()
                # Revolut crypto files have specific column headers
                if "Symbol" in first_line or "Type" in first_line:
                    return True
        except Exception:
            pass

        return False

    def parse_account_statement(self, filepath: Path) -> List[Dict]:
        """
        Parse crypto_account_statement_YYYY.csv.

        Returns list of crypto transactions:
        {
            'date': datetime,
            'symbol': str,
            'type': str,
            'quantity': Decimal,
            'price': Decimal,
            'value': Decimal,
            'value_currency': str,
            'fees': Decimal,
            'is_swap': bool,
        }

        Args:
            filepath: Path to crypto_account_statement CSV

        Returns:
            List of transaction dicts
        """
        df = pd.read_csv(filepath)
        transactions = []

        for _, row in df.iterrows():
            try:
                date_str = str(row["Date"])
                # Parse "Jan 3, 2025, 6:18:28 PM" format
                date = pd.to_datetime(date_str)

                value, value_currency = parse_amount_with_currency(row["Value"])
                price, _ = parse_amount_with_currency(row.get("Price", 0))
                fees, _ = parse_amount_with_currency(row.get("Fees", 0))
                qty_raw = row.get("Quantity", 0)
                qty = parse_amount(qty_raw) if pd.notna(qty_raw) else Decimal(0)

                transaction = {
                    "date": date,
                    "symbol": str(row["Symbol"]).strip().upper(),
                    "type": str(row["Type"]).strip(),
                    "quantity": qty,
                    "price": price,
                    "value": value,
                    "value_currency": value_currency or "USD",
                    "fees": fees,
                    "is_swap": False,  # Detected in post-processing
                }
                transactions.append(transaction)
            except Exception as e:
                print(f"Warning: Could not parse crypto transaction: {e}")
                continue

        # Detect SWAPs: same quantity Sell+Buy at same timestamp
        transactions = self._detect_swaps(transactions)
        return transactions

    def _detect_swaps(self, transactions: List[Dict]) -> List[Dict]:
        """
        Detect crypto-to-crypto swaps (same qty Sell+Buy at same timestamp).

        Mark as SWAP and set is_swap=True.

        Args:
            transactions: List of transaction dicts

        Returns:
            Same list with is_swap flags set
        """
        for i, tx in enumerate(transactions):
            if tx["type"] not in ("Sell", "SELL"):
                continue

            # Look for matching Buy immediately after
            if i + 1 < len(transactions):
                next_tx = transactions[i + 1]
                if (
                    next_tx["type"] in ("Buy", "BUY")
                    and tx["quantity"] == next_tx["quantity"]
                    and tx["date"] == next_tx["date"]
                ):
                    tx["is_swap"] = True
                    next_tx["is_swap"] = True

        return transactions

    def parse_profit_and_loss(self, filepath: Path) -> Dict:
        """
        Parse crypto_profit_and_loss_YYYY.csv.

        Returns dict with sections:
        {
            'realized_gains': [...],
            'unrealized_gains': [...],
            'fees': [...],
        }

        Used primarily for validation against account_statement calculations.

        Args:
            filepath: Path to crypto_profit_and_loss CSV

        Returns:
            Dict with gains and fees
        """
        # TODO: Implement crypto P&L parsing
        return {"realized_gains": [], "unrealized_gains": [], "fees": []}
