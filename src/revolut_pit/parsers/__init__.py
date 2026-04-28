"""Parsers for Revolut and other broker CSV exports.

Provides a plugin architecture with auto-detection and registration system.
"""

from pathlib import Path
from typing import List, Optional, Type

from .base import BrokerParser, BrokerStockParser, BrokerCryptoParser
from .revolut.stocks import RevolutStocksParser
from .revolut.crypto import RevolutCryptoParser

# Backwards compatibility: re-export old names
StocksParser = RevolutStocksParser
CryptoParser = RevolutCryptoParser

__all__ = [
    "BrokerParser",
    "BrokerStockParser",
    "BrokerCryptoParser",
    "StocksParser",
    "CryptoParser",
    "register_parser",
    "auto_detect",
    "list_parsers",
]


# Global parser registry
_PARSER_REGISTRY: List[Type[BrokerParser]] = [
    RevolutStocksParser,
    RevolutCryptoParser,
]


def register_parser(parser_class: Type[BrokerParser]):
    """
    Register a new parser class in the global registry.

    Can be used as a decorator:
        @register_parser
        class MyBrokerStocksParser(BrokerStockParser):
            ...

    Args:
        parser_class: Parser class implementing BrokerParser interface

    Returns:
        The parser_class (for decorator support)
    """
    if parser_class not in _PARSER_REGISTRY:
        _PARSER_REGISTRY.append(parser_class)
    return parser_class


def auto_detect(filepath: Path) -> Optional[BrokerParser]:
    """
    Auto-detect which parser can handle the given file.

    Tries each registered parser's detect() method until one matches.

    Args:
        filepath: Path to CSV file to auto-detect

    Returns:
        Instance of matching parser, or None if no match found
    """
    import re

    filepath = Path(filepath)

    for parser_class in _PARSER_REGISTRY:
        # Create a temporary instance to call detect()
        # For Revolut parsers, we need a year; use current or 2025 as default
        try:
            # Get year from filename if possible
            filename = filepath.stem  # Remove extension
            year = 2025

            # Look for 4-digit year in filename (e.g., 2024, 2025)
            match = re.search(r"(20\d{2})", filename)
            if match:
                potential_year = int(match.group(1))
                if 2000 <= potential_year <= 2100:
                    year = potential_year

            instance = parser_class(year=year)
            if instance.detect(filepath):
                return instance
        except Exception:
            # If instantiation fails for a parser, try next one
            continue

    return None


def list_parsers() -> List[Type[BrokerParser]]:
    """
    List all registered parser classes.

    Returns:
        List of registered parser classes
    """
    return _PARSER_REGISTRY.copy()
