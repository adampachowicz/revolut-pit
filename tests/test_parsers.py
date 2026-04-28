"""Tests for CSV parsers."""

import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from revolut_pit.parsers.stocks import StocksParser
from revolut_pit.parsers.crypto import CryptoParser


class TestStocksParser:
    """Test stocks CSV parser."""

    @pytest.fixture
    def parser(self):
        return StocksParser(year=2025)

    def test_parse_account_statement_basic(self, parser):
        """Parse basic account statement."""
        csv_content = """Date,Ticker,Type,Quantity,Price per share,Total Amount,Currency,FX Rate
2025-03-15,AAPL,BUY - MARKET,10,150.00,USD 1500.00,USD,1.0"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            f.flush()

            txs = parser.parse_account_statement(Path(f.name))

            assert len(txs) == 1
            assert txs[0]["ticker"] == "AAPL"
            assert txs[0]["type"] == "BUY - MARKET"
            assert txs[0]["quantity"] == Decimal("10")
            assert txs[0]["price_per_share"] == Decimal("150.00")

    def test_parse_profit_and_loss(self, parser):
        """Parse profit and loss statement."""
        csv_content = """Income from Sells
Date acquired,Date sold,Symbol,Security name,ISIN,Country,Quantity,Cost basis,Gross proceeds,Gross PnL,Currency
2025-01-15,2025-06-20,AAPL,Apple Inc,US0378331005,US,10,1500.00,1600.00,100.00,USD

Other income & fees
Date,Symbol,Security name,ISIN,Country,Gross amount,Withholding tax,Net Amount,Currency
2025-03-15,AAPL,Apple Inc,US0378331005,US,50.00,7.50,42.50,USD"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            f.flush()

            sells, other_income = parser.parse_profit_and_loss(Path(f.name))

            assert len(sells) == 1
            assert sells[0]["symbol"] == "AAPL"
            assert sells[0]["quantity"] == Decimal("10")

            assert len(other_income) == 1
            assert other_income[0]["gross_amount"] == Decimal("50.00")


class TestCryptoParser:
    """Test crypto CSV parser."""

    @pytest.fixture
    def parser(self):
        return CryptoParser(year=2025)

    def test_parse_account_statement_basic(self, parser):
        """Parse basic crypto account statement."""
        csv_content = """Symbol,Type,Quantity,Price,Value,Fees,Date
BTC,Buy,1,50000,"$50000.00",0,"Jan 3, 2025, 6:18:28 PM"
ETH,Sell,10,3000,"$30000.00",0,"Jan 4, 2025, 7:00:00 PM\""""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            f.flush()

            txs = parser.parse_account_statement(Path(f.name))

            assert len(txs) >= 1
            assert txs[0]["symbol"] == "BTC"
            assert txs[0]["quantity"] == Decimal("1")

    def test_detect_swaps(self, parser):
        """Detect crypto-to-crypto swaps."""
        csv_content = """Symbol,Type,Quantity,Price,Value,Fees,Date
RNDR,Sell,100,1,"$100.00",0,"Jan 3, 2025, 6:18:28 PM"
RENDER,Buy,100,1,"$100.00",0,"Jan 3, 2025, 6:18:28 PM\""""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            f.flush()

            txs = parser.parse_account_statement(Path(f.name))

            # Check if SWAPs are marked
            swaps = [tx for tx in txs if tx.get("is_swap")]
            assert len(swaps) >= 2  # both legs flagged

    def test_swap_detected_when_intervening_row(self, parser):
        """Bug #6 regression: swap legs are NOT always adjacent in the CSV.

        Pre-fix detector compared `i` and `i+1` only, so a fee or stake
        row between the Sell and Buy hid the swap. The new detector
        searches all rows within a time window.
        """
        csv_content = """Symbol,Type,Quantity,Price,Value,Fees,Date
RNDR,Sell,100,1,"$100.00",0,"Jan 3, 2025, 6:18:28 PM"
USD,Stake,0,0,"$0.00",0,"Jan 3, 2025, 6:18:28 PM"
RENDER,Buy,100,1,"$100.00",0,"Jan 3, 2025, 6:18:28 PM\""""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            f.flush()

            txs = parser.parse_account_statement(Path(f.name))

            sells = [t for t in txs if t["type"].lower().startswith("sell")]
            buys = [
                t for t in txs
                if t["type"].lower().startswith("buy")
                and "revolut x" not in t["type"].lower()
            ]
            assert sells[0]["is_swap"] is True
            assert buys[0]["is_swap"] is True

    def test_same_symbol_pair_is_not_swap(self, parser):
        """Bug #6 regression: Sell+Buy of the SAME symbol is never a swap."""
        csv_content = """Symbol,Type,Quantity,Price,Value,Fees,Date
BTC,Sell,1,50000,"$50000.00",0,"Jan 3, 2025, 6:18:28 PM"
BTC,Buy,1,50000,"$50000.00",0,"Jan 3, 2025, 6:18:28 PM\""""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            f.flush()

            txs = parser.parse_account_statement(Path(f.name))

            assert all(not t.get("is_swap") for t in txs)

    def test_revolut_x_referral_buy_not_swap_partner(self, parser):
        """`Buy - Revolut X` referral bonuses must not be paired as a swap leg."""
        csv_content = """Symbol,Type,Quantity,Price,Value,Fees,Date
BTC,Sell,1,50000,"$50000.00",0,"Jan 3, 2025, 6:18:28 PM"
ETH,Buy - Revolut X,10,3000,"$50000.00",0,"Jan 3, 2025, 6:18:28 PM\""""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            f.flush()

            txs = parser.parse_account_statement(Path(f.name))

            sells = [t for t in txs if t["type"].lower().startswith("sell")]
            assert sells[0].get("is_swap") is not True
