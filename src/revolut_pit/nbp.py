"""
NBP (National Bank of Poland) API client for exchange rates.

Uses Table A mid-rates from the last business day before the transaction date.
Caches results to ~/.cache/revolut_pit/nbp_rates.json
"""

import json
import os
import time
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Optional, Dict, Set, Tuple

import requests


# Polish public holidays for 2020-2026
# Fixed holidays: (month, day)
# Moveable holidays (Easter-based): calculated per year
POLISH_FIXED_HOLIDAYS = {
    (1, 1),      # New Year
    (1, 6),      # Three Kings Day
    (5, 1),      # Labour Day
    (5, 3),      # Constitution Day
    (8, 15),     # Assumption of Mary
    (11, 1),     # All Saints Day
    (11, 11),    # Independence Day
    (12, 25),    # Christmas Day
    (12, 26),    # Second Day of Christmas
}

# Moveable holidays (Easter-based) for 2020-2026
# Format: (year, month, day) for Good Friday, Easter Monday, Corpus Christi
MOVEABLE_HOLIDAYS_BY_YEAR = {
    2020: [(4, 10), (4, 12), (4, 13), (6, 11)],  # Good Fri, Easter Sun, Easter Mon, Corpus
    2021: [(4, 2), (4, 4), (4, 5), (6, 3)],
    2022: [(4, 15), (4, 17), (4, 18), (6, 16)],
    2023: [(4, 7), (4, 9), (4, 10), (6, 8)],
    2024: [(3, 29), (3, 31), (4, 1), (5, 30)],
    2025: [(4, 18), (4, 20), (4, 21), (6, 19)],
    2026: [(4, 3), (4, 5), (4, 6), (6, 4)],
}


def _get_all_holidays(year: int) -> Set[Tuple[int, int]]:
    """Get all Polish public holidays for a given year (as month, day tuples)."""
    holidays = set(POLISH_FIXED_HOLIDAYS)

    # Add moveable holidays for this year
    if year in MOVEABLE_HOLIDAYS_BY_YEAR:
        holidays.update(MOVEABLE_HOLIDAYS_BY_YEAR[year])

    return holidays


class NBPClient:
    """Client for NBP Table A exchange rates with caching and fallback logic."""

    BASE_URL = "https://api.nbp.pl/api/exchangerates/rates"
    MAX_RETRIES = 7
    BACKOFF_BASE = 1.0

    def __init__(self, cache_dir: Optional[str] = None):
        """Initialize NBP client with optional cache directory."""
        if cache_dir is None:
            cache_dir = os.path.join(Path.home(), ".cache", "revolut_pit")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "nbp_rates.json"
        self._cache: Dict = self._load_cache()

    def _load_cache(self) -> Dict:
        """Load rates from cache file."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_cache(self):
        """Save rates to cache file."""
        with open(self.cache_file, "w") as f:
            json.dump(self._cache, f, indent=2)

    def _is_business_day(self, date: datetime) -> bool:
        """
        Check if date is a business day (Mon-Fri) and not a Polish public holiday.
        
        Args:
            date: Date to check
            
        Returns:
            True if date is a weekday and not a Polish public holiday
        """
        # Check if weekday (Monday=0 to Friday=4)
        if date.weekday() >= 5:
            return False

        # Check if it's a Polish public holiday
        holidays = _get_all_holidays(date.year)
        if (date.month, date.day) in holidays:
            return False

        return True

    def get_rate(
        self, currency: str, date: datetime, use_d_minus_1: bool = True
    ) -> Decimal:
        """
        Get NBP exchange rate for currency on the last business day before date.

        Args:
            currency: ISO 4217 currency code (e.g., 'USD', 'EUR')
            date: Transaction date
            use_d_minus_1: If True, use D-1 (previous business day). If False, use given date.

        Returns:
            Exchange rate as Decimal

        Raises:
            ValueError: If rate cannot be found after max retries
        """
        if use_d_minus_1:
            # Find last business day before transaction
            query_date = date - timedelta(days=1)
            while not self._is_business_day(query_date):
                query_date -= timedelta(days=1)
        else:
            query_date = date

        cache_key = f"{currency}_{query_date.strftime('%Y-%m-%d')}"

        # Check cache first
        if cache_key in self._cache:
            return Decimal(str(self._cache[cache_key]))

        # Try to fetch from NBP, stepping back up to MAX_RETRIES days
        for attempt in range(self.MAX_RETRIES):
            current_date = query_date - timedelta(days=attempt)
            date_str = current_date.strftime("%Y-%m-%d")

            # Try Table A first
            rate = self._fetch_rate("A", currency, date_str)
            if rate is not None:
                self._cache[cache_key] = str(rate)
                self._save_cache()
                return rate

            # Fallback to Table B if not found in Table A
            rate = self._fetch_rate("B", currency, date_str)
            if rate is not None:
                self._cache[cache_key] = str(rate)
                self._save_cache()
                return rate

        raise ValueError(
            f"Could not find exchange rate for {currency} "
            f"in last {self.MAX_RETRIES} business days before {date.strftime('%Y-%m-%d')}"
        )

    def _fetch_rate(self, table: str, currency: str, date_str: str) -> Optional[Decimal]:
        """
        Fetch rate from NBP API with backoff on 429 errors.

        Args:
            table: 'A' or 'B'
            currency: ISO 4217 code
            date_str: YYYY-MM-DD format

        Returns:
            Exchange rate as Decimal, or None if 404 (not found)
        """
        url = f"{self.BASE_URL}/{table}/{currency}/{date_str}/?format=json"

        for retry in range(3):
            try:
                response = requests.get(url, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    # Table A/B have different structures
                    if "rates" in data and len(data["rates"]) > 0:
                        rate = data["rates"][0].get("mid")
                        if rate:
                            return Decimal(str(rate))
                    return None

                elif response.status_code == 404:
                    return None

                elif response.status_code == 429:
                    # Rate limited - backoff exponentially
                    wait_time = self.BACKOFF_BASE * (2 ** retry)
                    time.sleep(wait_time)
                    continue

                else:
                    return None

            except requests.RequestException:
                return None

        return None

    def clear_cache(self):
        """Clear the entire rate cache."""
        self._cache.clear()
        if self.cache_file.exists():
            self.cache_file.unlink()
