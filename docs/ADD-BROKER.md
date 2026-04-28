# Adding a New Broker — Step-by-Step Guide

revolut-pit uses a plugin architecture. Adding support for a new broker (Interactive Brokers, eToro, etc.) is straightforward.

## Architecture Overview

The parser plugin system:

```
parsers/
├── __init__.py            # Registry (auto-detection, registration)
├── base.py                # Abstract interfaces
├── _common.py             # Shared parsing utilities
├── revolut/               # Revolut broker package
│   ├── __init__.py
│   ├── stocks.py          # RevolutStocksParser
│   └── crypto.py          # RevolutCryptoParser
└── interactive_brokers/   # (future) Interactive Brokers package
    ├── __init__.py
    ├── stocks.py          # IBStocksParser
    └── ...
```

## Step 1: Create Broker Package

Create a directory for your broker under `src/revolut_pit/parsers/`:

```bash
mkdir -p src/revolut_pit/parsers/my_broker
touch src/revolut_pit/parsers/my_broker/__init__.py
touch src/revolut_pit/parsers/my_broker/stocks.py
touch src/revolut_pit/parsers/my_broker/crypto.py
```

## Step 2: Create Stock Parser

File: `src/revolut_pit/parsers/my_broker/stocks.py`

```python
from pathlib import Path
from typing import List, Dict, Tuple
import pandas as pd
from decimal import Decimal

from .._common import parse_amount, parse_amount_with_currency
from ..base import BrokerStockParser


class MyBrokerStocksParser(BrokerStockParser):
    """Parse My Broker stock trading data."""

    @property
    def name(self) -> str:
        return "My Broker"

    @property
    def version(self) -> str:
        return "1.0.0"

    def __init__(self, year: int):
        self.year = year

    def detect(self, filepath: Path) -> bool:
        """
        Detect if this is a My Broker stocks CSV.
        
        Check:
        - Filename pattern
        - Header row
        - Unique column names
        """
        filename = filepath.name.lower()
        
        # Your broker might use: trades_YYYY.csv, portfolio_export.csv, etc.
        if "stock" not in filename and "trade" not in filename:
            return False
        
        try:
            with open(filepath, "r") as f:
                header = f.readline()
                # Check for unique column to your broker
                if "My Broker Column Name" in header:
                    return True
        except Exception:
            pass
        
        return False

    def parse_account_statement(self, filepath: Path) -> List[Dict]:
        """
        Parse account statement for stocks.
        
        Must return standardized format:
        [{
            'date': datetime,
            'ticker': str,
            'type': str,
            'quantity': Decimal,
            'price_per_share': Decimal,
            'total_amount': Decimal,
            'currency': str,
            'fx_rate_revolut': Decimal,  # your broker's rate
        }]
        """
        df = pd.read_csv(filepath)
        transactions = []
        
        for _, row in df.iterrows():
            try:
                # Map your broker's columns to standardized format
                date = pd.to_datetime(row["Date Column"])
                ticker = str(row["Symbol Column"]).strip()
                qty = parse_amount(row["Quantity Column"])
                price = parse_amount(row["Price Column"])
                currency = str(row.get("Currency", "USD")).strip()
                
                transaction = {
                    'date': date,
                    'ticker': ticker,
                    'type': str(row.get("Type", "")).strip(),
                    'quantity': qty,
                    'price_per_share': price,
                    'total_amount': qty * price,
                    'currency': currency,
                    'fx_rate_revolut': parse_amount(row.get("FX Rate", 0)),
                }
                transactions.append(transaction)
            except Exception as e:
                print(f"Warning: Could not parse row: {e}")
                continue
        
        return transactions

    def parse_profit_and_loss(self, filepath: Path) -> Tuple[List[Dict], List[Dict]]:
        """
        Parse profit and loss statement.
        
        Must return: (sells, other_income) tuple with standardized format.
        See base.py for exact structure.
        """
        # Your broker might structure P&L differently
        # Read CSV, parse sections, return standardized dicts
        
        df = pd.read_csv(filepath)
        sells = []
        other_income = []
        
        for _, row in df.iterrows():
            try:
                sell = {
                    'date_acquired': pd.to_datetime(row["Bought Date"]),
                    'date_sold': pd.to_datetime(row["Sold Date"]),
                    'symbol': str(row["Symbol"]).strip(),
                    'security_name': str(row.get("Company Name", "")).strip(),
                    'isin': str(row.get("ISIN", "")).strip(),
                    'country': str(row.get("Country", "")).strip(),
                    'quantity': parse_amount(row["Shares"]),
                    'cost_basis': parse_amount(row["Cost"]),
                    'gross_proceeds': parse_amount(row["Proceeds"]),
                    'gross_pnl': parse_amount(row["Profit"]),
                    'currency': str(row.get("Currency", "USD")).strip(),
                }
                sells.append(sell)
            except Exception as e:
                print(f"Warning: Could not parse sell: {e}")
        
        # Similar for other_income (dividends)...
        
        return sells, other_income
```

## Step 3: Create Crypto Parser (if applicable)

File: `src/revolut_pit/parsers/my_broker/crypto.py`

```python
from pathlib import Path
from typing import List, Dict
import pandas as pd
from decimal import Decimal

from .._common import parse_amount, parse_amount_with_currency
from ..base import BrokerCryptoParser


class MyBrokerCryptoParser(BrokerCryptoParser):
    """Parse My Broker crypto trading data."""

    @property
    def name(self) -> str:
        return "My Broker"

    @property
    def version(self) -> str:
        return "1.0.0"

    def __init__(self, year: int):
        self.year = year

    def detect(self, filepath: Path) -> bool:
        filename = filepath.name.lower()
        if "crypto" not in filename:
            return False
        # Add your detection logic
        return True

    def parse_account_statement(self, filepath: Path) -> List[Dict]:
        """Parse crypto transactions (buy, sell, swap, staking rewards)."""
        df = pd.read_csv(filepath)
        transactions = []
        
        for _, row in df.iterrows():
            try:
                transaction = {
                    'date': pd.to_datetime(row["Date"]),
                    'symbol': str(row["Coin"]).strip().upper(),
                    'type': str(row["Type"]).strip(),  # Buy, Sell, Swap, Staking Reward
                    'quantity': parse_amount(row["Amount"]),
                    'price': parse_amount(row["Price"]),
                    'value': parse_amount(row["Total"]),
                    'value_currency': "USD",
                    'fees': parse_amount(row.get("Fee", 0)),
                    'is_swap': False,  # Your broker might have SWAP type
                }
                transactions.append(transaction)
            except Exception as e:
                print(f"Warning: Could not parse crypto transaction: {e}")
        
        # Detect SWAPs if not explicitly marked
        transactions = self._detect_swaps(transactions)
        return transactions

    def _detect_swaps(self, transactions: List[Dict]) -> List[Dict]:
        """Detect crypto-to-crypto swaps (if not explicitly marked)."""
        # Similar to Revolut parser: look for Sell+Buy pairs at same time
        return transactions

    def parse_profit_and_loss(self, filepath: Path) -> Dict:
        """Parse crypto P&L (optional for validation)."""
        return {"realized_gains": [], "unrealized_gains": [], "fees": []}
```

## Step 4: Create Package __init__.py

File: `src/revolut_pit/parsers/my_broker/__init__.py`

```python
"""My Broker parsers."""

from .stocks import MyBrokerStocksParser
from .crypto import MyBrokerCryptoParser

__all__ = ["MyBrokerStocksParser", "MyBrokerCryptoParser"]
```

## Step 5: Register Parsers

Update `src/revolut_pit/parsers/__init__.py` to import and register:

```python
# Add these imports
from .my_broker.stocks import MyBrokerStocksParser
from .my_broker.crypto import MyBrokerCryptoParser

# Update _PARSER_REGISTRY
_PARSER_REGISTRY: List[Type[BrokerParser]] = [
    RevolutStocksParser,
    RevolutCryptoParser,
    MyBrokerStocksParser,        # Add
    MyBrokerCryptoParser,        # Add
]
```

## Step 6: Write Tests

File: `tests/test_my_broker.py`

```python
"""Tests for My Broker parser."""

import tempfile
from pathlib import Path
from decimal import Decimal
import pytest

from revolut_pit.parsers.my_broker.stocks import MyBrokerStocksParser


class TestMyBrokerStocksParser:
    """Test My Broker stocks parser."""

    @pytest.fixture
    def parser(self):
        return MyBrokerStocksParser(year=2025)

    def test_detect_my_broker_file(self, parser):
        """Detect My Broker CSV by filename."""
        csv_content = "Date,Symbol,Type,Quantity,Price\n2025-03-15,AAPL,BUY,10,150.00"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "trades_2025.csv"
            filepath.write_text(csv_content)
            
            # Your detect() should return True for My Broker files
            # parser.detect(filepath) should be True
            
    def test_parse_account_statement(self, parser):
        """Parse My Broker account statement."""
        csv_content = "Date,Symbol,Type,Quantity,Price,Currency\n2025-03-15,AAPL,BUY,10,150.00,USD"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "trades_2025.csv"
            filepath.write_text(csv_content)
            
            txs = parser.parse_account_statement(filepath)
            
            assert len(txs) == 1
            assert txs[0]["ticker"] == "AAPL"
            assert txs[0]["quantity"] == Decimal("10")
            assert txs[0]["price_per_share"] == Decimal("150.00")

    def test_parse_profit_and_loss(self, parser):
        """Parse My Broker profit and loss."""
        csv_content = """Date Bought,Date Sold,Symbol,Quantity,Cost,Proceeds
2025-01-15,2025-06-20,AAPL,10,1500.00,1600.00"""
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "pl_2025.csv"
            filepath.write_text(csv_content)
            
            sells, other_income = parser.parse_profit_and_loss(filepath)
            
            assert len(sells) == 1
            assert sells[0]["symbol"] == "AAPL"
            assert sells[0]["quantity"] == Decimal("10")
```

## Step 7: Test Everything

```bash
# Run all tests
pytest tests/ -v

# Run only your broker's tests
pytest tests/test_my_broker.py -v

# Run integration test with sample data
python -m revolut_pit calc --year 2025 --data-dir ./examples --output-dir ./output
```

Verify:
- Auto-detection works
- Parsing produces standardized output
- All existing tests still pass (52+ tests)
- Your tests pass

## Step 8: Document Your Broker

Create `docs/BROKER-MY_BROKER.md`:

```markdown
# My Broker Parser

## CSV Format

My Broker exports as `trades_YYYY.csv` and `pl_YYYY.csv`.

### Columns
- Date: Transaction date
- Symbol: Stock ticker
- Type: BUY, SELL, DIVIDEND
- Quantity: Shares
- Price: Per-share price
- Currency: USD, EUR, etc.
- FX Rate: My Broker's exchange rate

## Quirks

- Currency symbols are sometimes reversed ($100 vs 100 USD)
- Dividends are in a separate CSV
- Crypto not supported yet
- No fee information in export

## How to Export

1. Login to My Broker
2. Account → Tax Documents
3. Select year
4. Download CSV
```

## Step 9: Submit PR (if contributing)

1. Fork the repo
2. Create branch: `git checkout -b add-my-broker-support`
3. Commit: `git add . && git commit -m "Add My Broker parser support"`
4. Push: `git push origin add-my-broker-support`
5. Open PR with description

In the PR description:
- Link to My Broker API/docs
- Sample CSV (anonymized)
- Test results (all 52+ tests pass)
- Any limitations noted

## Tips

- **Use parse_amount/_common.py**: Don't reimplement currency parsing
- **Handle edge cases**: Missing fields, empty CSVs, malformed dates
- **Test with real data**: Anonymize it, then include as fixture
- **Document quirks**: Every broker has oddities (Revolut has typos!)
- **Maximize reuse**: If two brokers use similar format, consider shared code
- **Ask questions**: Community can help if stuck

## Example: Real Broker Workflow

For Interactive Brokers:

1. Check IB's CSV format (website, manual)
2. Find unique column headers
3. Create `parsers/interactive_brokers/` with stocks.py, crypto.py
4. Implement `detect()` to check for IB-specific patterns
5. Implement parse methods to map IB columns → standard format
6. Write tests with sample IB export (anonymized)
7. Document any IB-specific tax rules (treaty rates, etc.)
8. PR!

The goal: Any investor using any broker can generate correct PIT-38 with revolut-pit.
