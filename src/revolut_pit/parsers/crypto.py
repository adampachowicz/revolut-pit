"""Parser for Revolut cryptocurrency trading data.

DEPRECATED: This module is maintained for backwards compatibility.
Use revolut_pit.parsers.revolut.crypto instead.

New code should use:
    from revolut_pit.parsers.revolut.crypto import RevolutCryptoParser

Or use the auto-detection system:
    from revolut_pit.parsers import auto_detect
    parser = auto_detect(filepath)
"""

# Re-export for backwards compatibility
from .revolut.crypto import RevolutCryptoParser

# Alias to old name for backwards compatibility
CryptoParser = RevolutCryptoParser

__all__ = ["CryptoParser", "RevolutCryptoParser"]
