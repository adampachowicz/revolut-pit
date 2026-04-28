"""Tests for parser registry and auto-detection."""

import tempfile
from pathlib import Path

import pytest

from revolut_pit.parsers import (
    register_parser,
    auto_detect,
    list_parsers,
    BrokerStockParser,
    BrokerCryptoParser,
)


class TestParserRegistry:
    """Test parser registration and listing."""

    def test_list_parsers_returns_list(self):
        """List parsers should return a list."""
        parsers = list_parsers()
        assert isinstance(parsers, list)
        assert len(parsers) >= 2  # At least Revolut stocks and crypto

    def test_list_parsers_contains_revolut(self):
        """List parsers should include Revolut parsers."""
        parsers = list_parsers()
        parser_names = [p.__name__ for p in parsers]
        assert "RevolutStocksParser" in parser_names
        assert "RevolutCryptoParser" in parser_names

    def test_register_parser_adds_to_registry(self):
        """Register parser should add to global registry."""
        initial_count = len(list_parsers())

        # Create a minimal test parser
        class TestBrokerParser(BrokerStockParser):
            @property
            def name(self):
                return "TestBroker"

            @property
            def version(self):
                return "1.0.0"

            def detect(self, filepath):
                return False

            def parse_account_statement(self, filepath):
                return []

            def parse_profit_and_loss(self, filepath):
                return [], []

        # Register it
        register_parser(TestBrokerParser)

        # Should have one more parser
        assert len(list_parsers()) == initial_count + 1

        # Cleanup (remove test parser)
        from revolut_pit.parsers import _PARSER_REGISTRY

        _PARSER_REGISTRY.remove(TestBrokerParser)

    def test_register_parser_as_decorator(self):
        """Register parser can be used as a decorator."""
        initial_count = len(list_parsers())

        @register_parser
        class AnotherTestParser(BrokerCryptoParser):
            @property
            def name(self):
                return "AnotherTestBroker"

            @property
            def version(self):
                return "1.0.0"

            def detect(self, filepath):
                return False

            def parse_account_statement(self, filepath):
                return []

            def parse_profit_and_loss(self, filepath):
                return {}

        # Should have one more parser
        assert len(list_parsers()) == initial_count + 1

        # Cleanup
        from revolut_pit.parsers import _PARSER_REGISTRY

        _PARSER_REGISTRY.remove(AnotherTestParser)


class TestAutoDetection:
    """Test auto-detection of file types."""

    def test_auto_detect_stocks_profit_and_loss(self):
        """Auto-detect Revolut stocks profit_and_loss file."""
        csv_content = """Income from Sells
Date acquired,Date sold,Symbol,Security name,ISIN,Country,Quantity,Cost basis,Gross proceeds,Gross PnL,Currency
2025-01-15,2025-06-20,AAPL,Apple Inc,US0378331005,US,10,1500.00,1600.00,100.00,USD"""

        with tempfile.NamedTemporaryFile(
            mode="w", suffix="profit_and_loss_2025.csv", delete=False
        ) as f:
            f.write(csv_content)
            f.flush()

            parser = auto_detect(Path(f.name))

            assert parser is not None
            assert parser.name == "Revolut"
            assert hasattr(parser, "parse_profit_and_loss")

    def test_auto_detect_stocks_account_statement(self):
        """Auto-detect Revolut stocks account_statement file."""
        csv_content = """Date,Ticker,Type,Quantity,Price per share,Total Amount,Currency,FX Rate
2025-03-15,AAPL,BUY - MARKET,10,150.00,USD 1500.00,USD,1.0"""

        with tempfile.NamedTemporaryFile(
            mode="w", suffix="account_statement_2025.csv", delete=False
        ) as f:
            f.write(csv_content)
            f.flush()

            parser = auto_detect(Path(f.name))

            assert parser is not None
            assert parser.name == "Revolut"

    def test_auto_detect_crypto_account_statement(self):
        """Auto-detect Revolut crypto account_statement file."""
        csv_content = """Symbol,Type,Quantity,Price,Value,Fees,Date
BTC,Buy,1,50000,"$50000.00",0,"Jan 3, 2025, 6:18:28 PM"
ETH,Sell,10,3000,"$30000.00",0,"Jan 4, 2025, 7:00:00 PM\""""

        with tempfile.NamedTemporaryFile(
            mode="w", suffix="crypto_account_statement_2025.csv", delete=False
        ) as f:
            f.write(csv_content)
            f.flush()

            parser = auto_detect(Path(f.name))

            assert parser is not None
            assert parser.name == "Revolut"

    def test_auto_detect_unknown_file(self):
        """Auto-detect should return None for unknown files."""
        csv_content = """Unknown,File,Format
1,2,3"""

        with tempfile.NamedTemporaryFile(
            mode="w", suffix="unknown_2025.csv", delete=False
        ) as f:
            f.write(csv_content)
            f.flush()

            parser = auto_detect(Path(f.name))

            assert parser is None

    def test_auto_detect_extracts_year_from_filename(self):
        """Auto-detect should extract year from filename."""
        csv_content = """Date,Ticker,Type,Quantity,Price per share,Total Amount,Currency,FX Rate
2025-03-15,AAPL,BUY - MARKET,10,150.00,USD 1500.00,USD,1.0"""

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "account_statement_2024.csv"
            with open(filepath, "w") as f:
                f.write(csv_content)

            parser = auto_detect(filepath)

            assert parser is not None
            # Should have extracted 2024 from filename
            assert parser.year == 2024
