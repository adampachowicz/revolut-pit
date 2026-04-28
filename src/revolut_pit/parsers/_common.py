"""Shared helpers for all broker parsers."""

import re
from decimal import Decimal
from typing import Optional, Tuple


_AMT_RE = re.compile(r"-?\d+(\.\d+)?")


def parse_amount(value) -> Decimal:
    """
    Parse amount string to Decimal.

    Examples:
        '8.66' -> Decimal('8.66')
        '1.28 PLN' -> Decimal('1.28')
        '$0.96' -> Decimal('0.96')
        '-0.11' -> Decimal('-0.11')
        None -> Decimal('0')
        '' -> Decimal('0')

    Args:
        value: String, number, or None to parse

    Returns:
        Decimal representation of the amount
    """
    if value is None:
        return Decimal(0)
    s = str(value).strip()
    if s == "" or s.lower() == "nan":
        return Decimal(0)
    # Strip currency prefix ($, €, £) and suffix (PLN, USD, EUR)
    s = s.replace("$", "").replace("€", "").replace("£", "").strip()
    # Strip trailing currency code
    parts = s.split()
    if len(parts) >= 2 and parts[-1].isalpha():
        s = " ".join(parts[:-1])
    s = s.replace(",", "").strip()
    try:
        return Decimal(s)
    except Exception:
        m = _AMT_RE.search(s)
        return Decimal(m.group(0)) if m else Decimal(0)


def parse_amount_with_currency(value) -> Tuple[Decimal, Optional[str]]:
    """
    Parse amount and currency from a string.

    Examples:
        '$1.78' -> (Decimal('1.78'), 'USD')
        '1.38 PLN' -> (Decimal('1.38'), 'PLN')
        'EUR 500' -> (Decimal('500'), 'EUR')
        '100' -> (Decimal('100'), None)
        None -> (Decimal('0'), None)

    Args:
        value: String to parse for amount and currency

    Returns:
        Tuple of (Decimal amount, currency code or None)
    """
    if value is None:
        return Decimal(0), None
    s = str(value).strip()
    if not s or s.lower() == "nan":
        return Decimal(0), None

    currency = None
    if s.startswith("$"):
        currency = "USD"
        s = s[1:].strip()
    elif s.startswith("€"):
        currency = "EUR"
        s = s[1:].strip()
    elif s.startswith("£"):
        currency = "GBP"
        s = s[1:].strip()

    parts = s.split()
    if len(parts) >= 2:
        # Could be "EUR 500" (prefix) or "1.38 PLN" (suffix)
        if parts[0].isalpha() and len(parts[0]) == 3:
            currency = parts[0].upper()
            s = " ".join(parts[1:])
        elif parts[-1].isalpha() and len(parts[-1]) == 3:
            currency = parts[-1].upper()
            s = " ".join(parts[:-1])

    s = s.replace(",", "").strip()
    try:
        return Decimal(s), currency
    except Exception:
        m = _AMT_RE.search(s)
        return (Decimal(m.group(0)) if m else Decimal(0)), currency
