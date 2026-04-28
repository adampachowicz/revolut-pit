"""Parser for Revolut stock trading data.

DEPRECATED: This module is maintained for backwards compatibility.
Use revolut_pit.parsers.revolut.stocks instead.

New code should use:
    from revolut_pit.parsers.revolut.stocks import RevolutStocksParser

Or use the auto-detection system:
    from revolut_pit.parsers import auto_detect
    parser = auto_detect(filepath)
"""

# Re-export for backwards compatibility
from .revolut.stocks import RevolutStocksParser

# Alias to old name for backwards compatibility
StocksParser = RevolutStocksParser

__all__ = ["StocksParser", "RevolutStocksParser"]
