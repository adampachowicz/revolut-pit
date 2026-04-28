"""Tests for NBP client."""

import json
import tempfile
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from revolut_pit.nbp import NBPClient


class TestNBPClient:
    """Test NBP exchange rate client."""

    @pytest.fixture
    def nbp_client(self):
        """Create NBP client with temp cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield NBPClient(cache_dir=tmpdir)

    def test_is_business_day(self, nbp_client):
        """Test business day detection."""
        # Monday
        assert nbp_client._is_business_day(datetime(2025, 3, 3))
        # Friday
        assert nbp_client._is_business_day(datetime(2025, 3, 7))
        # Saturday
        assert not nbp_client._is_business_day(datetime(2025, 3, 1))
        # Sunday
        assert not nbp_client._is_business_day(datetime(2025, 3, 2))

    @patch("revolut_pit.nbp.requests.get")
    def test_t1_1_midweek_weekday(self, mock_get, nbp_client):
        """T1.1: Mid-week weekday → use D-1 rate"""
        # Wednesday = D-1 is Tuesday
        wednesday = datetime(2025, 3, 5)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"rates": [{"mid": 4.25}]}
        mock_get.return_value = mock_response

        rate = nbp_client.get_rate("USD", wednesday, use_d_minus_1=True)

        assert rate == Decimal("4.25")
        # Check that Tuesday was requested (D-1)
        assert mock_get.called
        call_args = mock_get.call_args[0][0]
        assert "2025-03-04" in call_args  # Tuesday

    @patch("revolut_pit.nbp.requests.get")
    def test_t1_2_monday_uses_friday(self, mock_get, nbp_client):
        """T1.2: Monday transaction → use Friday rate"""
        monday = datetime(2025, 3, 3)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"rates": [{"mid": 4.20}]}
        mock_get.return_value = mock_response

        rate = nbp_client.get_rate("USD", monday, use_d_minus_1=True)

        assert rate == Decimal("4.20")
        call_args = mock_get.call_args[0][0]
        assert "2025-02-28" in call_args  # Friday (weekend back)

    @patch("revolut_pit.nbp.requests.get")
    def test_t1_3_day_after_easter(self, mock_get, nbp_client):
        """T1.3: Day after Easter → step back to last business day"""
        # Easter Monday 2025 is April 21, so April 22 is Tuesday after
        easter_tuesday = datetime(2025, 4, 22)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"rates": [{"mid": 4.30}]}
        mock_get.return_value = mock_response

        rate = nbp_client.get_rate("USD", easter_tuesday, use_d_minus_1=True)

        assert rate == Decimal("4.30")

    @patch("revolut_pit.nbp.requests.get")
    def test_t1_4_dec_31_uses_dec_30(self, mock_get, nbp_client):
        """T1.4: Dec 31 transaction → use Dec 30 rate"""
        dec_31 = datetime(2024, 12, 31)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"rates": [{"mid": 4.35}]}
        mock_get.return_value = mock_response

        rate = nbp_client.get_rate("USD", dec_31, use_d_minus_1=True)

        assert rate == Decimal("4.35")
        call_args = mock_get.call_args[0][0]
        assert "2024-12-30" in call_args  # Dec 30

    @patch("revolut_pit.nbp.requests.get")
    def test_t1_5_jan_2_uses_dec_31(self, mock_get, nbp_client):
        """T1.5: Jan 2 transaction → use Dec 31 (D-1, skips Jan 1 holiday)"""
        jan_2 = datetime(2025, 1, 2)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"rates": [{"mid": 4.32}]}
        mock_get.return_value = mock_response

        rate = nbp_client.get_rate("USD", jan_2, use_d_minus_1=True)

        assert rate == Decimal("4.32")
        call_args = mock_get.call_args[0][0]
        # Jan 1 is a Polish holiday (New Year), so it should skip back to Dec 31, 2024
        assert "2024-12-31" in call_args

    @patch("revolut_pit.nbp.requests.get")
    def test_t1_6_fallback_to_table_b(self, mock_get, nbp_client):
        """T1.6: Currency not in Table A → fallback to Table B"""
        transaction_date = datetime(2025, 3, 5)

        # Table A returns 404
        mock_response_404 = MagicMock()
        mock_response_404.status_code = 404

        # Table B returns rate
        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"rates": [{"mid": 4.10}]}

        mock_get.side_effect = [mock_response_404, mock_response_200]

        rate = nbp_client.get_rate("XYZ", transaction_date, use_d_minus_1=True)

        assert rate == Decimal("4.10")

    @patch("revolut_pit.nbp.requests.get")
    def test_t1_7_404_steps_back(self, mock_get, nbp_client):
        """T1.7: 404 response → step back, try previous day"""
        transaction_date = datetime(2025, 3, 5)

        # First attempt (Tuesday) returns 404
        mock_response_404 = MagicMock()
        mock_response_404.status_code = 404

        # Second attempt (Monday) returns rate
        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"rates": [{"mid": 4.28}]}

        mock_get.side_effect = [mock_response_404, mock_response_404, mock_response_200]

        rate = nbp_client.get_rate("USD", transaction_date, use_d_minus_1=True)

        assert rate == Decimal("4.28")

    def test_t1_8_cache_hit(self, nbp_client):
        """T1.8: Cache hit doesn't make HTTP request"""
        transaction_date = datetime(2025, 3, 5)

        # Manually set cache
        nbp_client._cache["USD_2025-03-04"] = "4.25"

        with patch("revolut_pit.nbp.requests.get") as mock_get:
            rate = nbp_client.get_rate("USD", transaction_date, use_d_minus_1=True)

            assert rate == Decimal("4.25")
            assert not mock_get.called

    @patch("revolut_pit.nbp.requests.get")
    def test_t1_9_429_backoff_and_retry(self, mock_get, nbp_client):
        """T1.9: 429 rate limit → backoff and retry"""
        transaction_date = datetime(2025, 3, 5)

        # First attempt: 429 (rate limited)
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429

        # Retry: 200 success
        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"rates": [{"mid": 4.23}]}

        mock_get.side_effect = [mock_response_429, mock_response_200]

        with patch("revolut_pit.nbp.time.sleep"):  # Don't actually sleep
            rate = nbp_client.get_rate("USD", transaction_date, use_d_minus_1=True)

        assert rate == Decimal("4.23")

    @patch("revolut_pit.nbp.requests.get")
    def test_t1_10_same_date_single_call(self, mock_get, nbp_client):
        """T1.10: Same date queried twice → 1 HTTP call only"""
        transaction_date = datetime(2025, 3, 5)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"rates": [{"mid": 4.25}]}
        mock_get.return_value = mock_response

        rate1 = nbp_client.get_rate("USD", transaction_date, use_d_minus_1=True)
        rate2 = nbp_client.get_rate("USD", transaction_date, use_d_minus_1=True)

        assert rate1 == rate2 == Decimal("4.25")
        # Only one call (first time); second is cached
        assert mock_get.call_count == 1


class TestPolishPublicHolidays:
    """Test that Polish public holidays are excluded from D-1 business day rule."""

    def test_easter_monday_is_not_business_day(self, nbp_client):
        """Easter Monday (Apr 21, 2025) should not be a business day."""
        from datetime import datetime

        # Easter Monday 2025 = Apr 21
        easter_monday = datetime(2025, 4, 21)

        assert not nbp_client._is_business_day(easter_monday)

    def test_good_friday_is_not_business_day(self, nbp_client):
        """Good Friday (Apr 18, 2025) should not be a business day."""
        from datetime import datetime

        # Good Friday 2025 = Apr 18
        good_friday = datetime(2025, 4, 18)

        assert not nbp_client._is_business_day(good_friday)

    def test_corpus_christi_is_not_business_day(self, nbp_client):
        """Corpus Christi (Jun 19, 2025) should not be a business day."""
        from datetime import datetime

        # Corpus Christi 2025 = Jun 19
        corpus = datetime(2025, 6, 19)

        assert not nbp_client._is_business_day(corpus)

    def test_fixed_holiday_new_year(self, nbp_client):
        """New Year (Jan 1) should not be a business day."""
        from datetime import datetime

        new_year = datetime(2025, 1, 1)

        assert not nbp_client._is_business_day(new_year)

    def test_fixed_holiday_independence_day(self, nbp_client):
        """Independence Day (Nov 11) should not be a business day."""
        from datetime import datetime

        independence = datetime(2025, 11, 11)

        assert not nbp_client._is_business_day(independence)

    def test_transaction_after_easter_monday_skips_holiday(self, nbp_client):
        """
        Transaction on Apr 22, 2025 (Tuesday after Easter Mon) should use D-1 from Apr 17 (Thursday).

        Date sequence:
        - Apr 22 (Tue): transaction date
        - Apr 21 (Mon): Easter Monday (holiday, skip)
        - Apr 20 (Sun): Easter Sunday (weekend, skip)
        - Apr 19 (Sat): weekend (skip)
        - Apr 18 (Fri): Good Friday (holiday, skip)
        - Apr 17 (Thu): ✓ business day
        """
        from datetime import datetime

        transaction_date = datetime(2025, 4, 22)

        # D-1 calculation should step back from Apr 21 (holiday)
        # and land on Apr 17 (Thursday)
        query_date = transaction_date - timedelta(days=1)  # Apr 21
        while not nbp_client._is_business_day(query_date):
            query_date -= timedelta(days=1)

        assert query_date.month == 4
        assert query_date.day == 17
        assert query_date.weekday() == 3  # Thursday

    def test_fixed_holiday_may_1(self, nbp_client):
        """Labour Day (May 1) should not be a business day."""
        from datetime import datetime

        labour_day = datetime(2025, 5, 1)

        assert not nbp_client._is_business_day(labour_day)

    def test_christmas_holidays(self, nbp_client):
        """Christmas holidays (Dec 25-26) should not be business days."""
        from datetime import datetime

        christmas = datetime(2025, 12, 25)
        christmas_2 = datetime(2025, 12, 26)

        assert not nbp_client._is_business_day(christmas)
        assert not nbp_client._is_business_day(christmas_2)


from datetime import timedelta


class TestPolishPublicHolidays:
    """Test that Polish public holidays are excluded from D-1 business day rule."""

    @pytest.fixture
    def nbp_client(self):
        """Create NBP client with temp cache for testing."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            client = NBPClient(cache_dir=tmp_dir)
            yield client

    def test_easter_monday_is_not_business_day(self, nbp_client):
        """Easter Monday (Apr 21, 2025) should not be a business day."""
        # Easter Monday 2025 = Apr 21
        easter_monday = datetime(2025, 4, 21)

        assert not nbp_client._is_business_day(easter_monday)

    def test_good_friday_is_not_business_day(self, nbp_client):
        """Good Friday (Apr 18, 2025) should not be a business day."""
        # Good Friday 2025 = Apr 18
        good_friday = datetime(2025, 4, 18)

        assert not nbp_client._is_business_day(good_friday)

    def test_corpus_christi_is_not_business_day(self, nbp_client):
        """Corpus Christi (Jun 19, 2025) should not be a business day."""
        # Corpus Christi 2025 = Jun 19
        corpus = datetime(2025, 6, 19)

        assert not nbp_client._is_business_day(corpus)

    def test_fixed_holiday_new_year(self, nbp_client):
        """New Year (Jan 1) should not be a business day."""
        new_year = datetime(2025, 1, 1)

        assert not nbp_client._is_business_day(new_year)

    def test_fixed_holiday_independence_day(self, nbp_client):
        """Independence Day (Nov 11) should not be a business day."""
        independence = datetime(2025, 11, 11)

        assert not nbp_client._is_business_day(independence)

    def test_transaction_after_easter_monday_skips_holiday(self, nbp_client):
        """
        Transaction on Apr 22, 2025 (Tuesday after Easter Mon) should use D-1 from Apr 17 (Thursday).

        Date sequence:
        - Apr 22 (Tue): transaction date
        - Apr 21 (Mon): Easter Monday (holiday, skip)
        - Apr 20 (Sun): Easter Sunday (weekend, skip)
        - Apr 19 (Sat): weekend (skip)
        - Apr 18 (Fri): Good Friday (holiday, skip)
        - Apr 17 (Thu): ✓ business day
        """
        transaction_date = datetime(2025, 4, 22)

        # D-1 calculation should step back from Apr 21 (holiday)
        # and land on Apr 17 (Thursday)
        query_date = transaction_date - timedelta(days=1)  # Apr 21
        while not nbp_client._is_business_day(query_date):
            query_date -= timedelta(days=1)

        assert query_date.month == 4
        assert query_date.day == 17
        assert query_date.weekday() == 3  # Thursday

    def test_fixed_holiday_may_1(self, nbp_client):
        """Labour Day (May 1) should not be a business day."""
        labour_day = datetime(2025, 5, 1)

        assert not nbp_client._is_business_day(labour_day)

    def test_christmas_holidays(self, nbp_client):
        """Christmas holidays (Dec 25-26) should not be business days."""
        christmas = datetime(2025, 12, 25)
        christmas_2 = datetime(2025, 12, 26)

        assert not nbp_client._is_business_day(christmas)
        assert not nbp_client._is_business_day(christmas_2)

    def test_wigilia_2025_is_holiday(self, nbp_client):
        """Christmas Eve 24 Dec 2025+ is a statutory holiday (Dz.U. 2024 poz. 1965).

        Regression for REVIEW-MODEL-QA Bug #5 — pre-fix, the code treated
        Wigilia as a normal business day, causing audit-trail entries with
        a date NBP never published.
        """
        wigilia_2025 = datetime(2025, 12, 24)
        assert not nbp_client._is_business_day(wigilia_2025)

    def test_wigilia_2024_is_still_business_day(self, nbp_client):
        """The Wigilia holiday only takes effect from 2025 onwards."""
        wigilia_2024 = datetime(2024, 12, 24)
        assert nbp_client._is_business_day(wigilia_2024)


class TestCurrencyValidation:
    """Regression for REVIEW-SECURITY Finding 5 (SSRF/path injection)."""

    @pytest.fixture
    def nbp_client(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            yield NBPClient(cache_dir=tmp_dir)

    @pytest.mark.parametrize(
        "bad",
        [
            "../../../etc/passwd",
            "USD/../A/USD",
            "usd",
            "US",
            "USDD",
            "US1",
            "",
            "USD\nfoo",
        ],
    )
    def test_invalid_currency_rejected(self, nbp_client, bad):
        with pytest.raises(ValueError, match="Invalid currency"):
            nbp_client.get_rate(bad, datetime(2025, 3, 5))
