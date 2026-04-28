"""Abstract base classes for broker CSV parsers.

Defines interfaces that all broker parsers must implement for stocks and crypto.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class BrokerParser(ABC):
    """Base class for all broker parsers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the broker (e.g., 'Revolut', 'Interactive Brokers')."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Parser version (e.g., '1.0.0')."""
        pass

    @abstractmethod
    def detect(self, filepath: Path) -> bool:
        """
        Auto-detect if this parser can handle the given file.

        Args:
            filepath: Path to CSV file to check

        Returns:
            True if this parser can handle the file, False otherwise
        """
        pass


class BrokerStockParser(BrokerParser):
    """Interface for stock CSV parsers."""

    @abstractmethod
    def parse_account_statement(self, filepath: Path) -> List[Dict]:
        """
        Parse account_statement CSV.

        Returns list of transactions with standardized fields:
        {
            'date': datetime,
            'ticker': str,
            'type': str,
            'quantity': Decimal,
            'price_per_share': Decimal,
            'total_amount': Decimal,
            'currency': str,
            'fx_rate_revolut': Decimal,  # broker's rate (informational)
        }

        Args:
            filepath: Path to account_statement CSV file

        Returns:
            List of transaction dicts in standardized format
        """
        pass

    @abstractmethod
    def parse_profit_and_loss(self, filepath: Path) -> Tuple[List[Dict], List[Dict]]:
        """
        Parse profit_and_loss CSV.

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
            filepath: Path to profit_and_loss CSV file

        Returns:
            Tuple of (sells list, other_income list) in standardized format
        """
        pass


class BrokerCryptoParser(BrokerParser):
    """Interface for crypto CSV parsers."""

    @abstractmethod
    def parse_account_statement(self, filepath: Path) -> List[Dict]:
        """
        Parse crypto_account_statement CSV.

        Returns list of crypto transactions:
        {
            'date': datetime,
            'symbol': str,
            'type': str,  # Buy, Sell, Stake, etc.
            'quantity': Decimal,
            'price': Decimal,
            'value': Decimal,
            'value_currency': str,
            'fees': Decimal,
            'is_swap': bool,  # True if detected as crypto-to-crypto swap
        }

        Args:
            filepath: Path to crypto_account_statement CSV file

        Returns:
            List of transaction dicts in standardized format
        """
        pass

    @abstractmethod
    def parse_profit_and_loss(self, filepath: Path) -> Dict:
        """
        Parse crypto_profit_and_loss CSV (optional).

        Returns dict with realized/unrealized gains and fees.
        Used primarily for validation against account_statement calculations.

        Args:
            filepath: Path to crypto_profit_and_loss CSV file

        Returns:
            Dict with 'realized_gains', 'unrealized_gains', 'fees' keys
        """
        pass
