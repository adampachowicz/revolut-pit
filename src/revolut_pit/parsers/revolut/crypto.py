"""Parser for Revolut cryptocurrency trading data."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Dict, Optional

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

    # Maximum allowed time delta between the two legs of a crypto-to-crypto swap.
    # Revolut occasionally records the buy/sell halves with sub-second drift,
    # which the original adjacency-only detector missed.
    SWAP_TIME_TOLERANCE_SECONDS = 60

    # Tolerance when comparing the fiat value of the two legs (relative).
    SWAP_VALUE_TOLERANCE = Decimal("0.01")  # 1%

    def _detect_swaps(self, transactions: List[Dict]) -> List[Dict]:
        """Detect crypto-to-crypto swaps (art. 17 ust. 1 pkt 11 PIT — exempt).

        A swap is a pair of (Sell X, Buy Y) where X != Y, executed within a
        narrow time window with matching fiat value. The previous detector
        only inspected adjacent CSV rows and required equal quantity, which
        produced both false negatives (intervening fee rows, sub-second drift)
        and false positives (legitimate fiat trades that happened to share
        a quantity and timestamp).

        Both matched legs are flagged with `is_swap=True` and cross-referenced
        via `swap_partner_index`.
        """
        from datetime import timedelta

        tolerance = timedelta(seconds=self.SWAP_TIME_TOLERANCE_SECONDS)

        sells = [
            i for i, tx in enumerate(transactions)
            if tx["type"].lower().startswith("sell")
        ]
        buys = [
            i for i, tx in enumerate(transactions)
            if tx["type"].lower().startswith("buy")
            # "Buy - Revolut X" rows are referral bonuses (cost basis 0), not swaps.
            and "revolut x" not in tx["type"].lower()
        ]

        used_buys: set = set()

        for s_idx in sells:
            sell = transactions[s_idx]
            if sell.get("is_swap"):
                continue

            best_match: Optional[int] = None
            best_dt = tolerance + timedelta(seconds=1)

            for b_idx in buys:
                if b_idx in used_buys:
                    continue
                buy = transactions[b_idx]
                if buy["symbol"] == sell["symbol"]:
                    # Same-symbol pair is never a swap.
                    continue

                dt = abs(sell["date"] - buy["date"])
                if dt > tolerance:
                    continue

                # Require fiat value to match within tolerance.
                if not self._values_match(sell["value"], buy["value"]):
                    continue

                if dt < best_dt:
                    best_dt = dt
                    best_match = b_idx

            if best_match is not None:
                used_buys.add(best_match)
                sell["is_swap"] = True
                sell["swap_partner_index"] = best_match
                transactions[best_match]["is_swap"] = True
                transactions[best_match]["swap_partner_index"] = s_idx

        return transactions

    @classmethod
    def _values_match(cls, a: Decimal, b: Decimal) -> bool:
        """Return True if two fiat values match within SWAP_VALUE_TOLERANCE."""
        if a == 0 or b == 0:
            return a == b
        diff = abs(a - b)
        scale = max(abs(a), abs(b))
        return (diff / scale) <= cls.SWAP_VALUE_TOLERANCE

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
