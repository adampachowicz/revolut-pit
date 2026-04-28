#!/usr/bin/env python3
"""
Independent auditor: sample 10% of transactions and verify manually.
"""

import sys
import csv
import random
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

# Setup path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from revolut_pit.pipeline import Pipeline, round_grosz
from revolut_pit.nbp import NBPClient


class RealisticMockNBP:
    """Mock NBP with realistic, varying rates by date."""
    def __init__(self):
        self._cache = {}

    def get_rate(self, currency, date, use_d_minus_1=True):
        """Return approximate realistic rates for 2025."""
        if isinstance(date, str):
            date = datetime.fromisoformat(date.replace("Z", "+00:00").split("T")[0]).date()
        elif hasattr(date, 'to_pydatetime'):
            date = date.to_pydatetime().date()
        elif hasattr(date, 'date'):
            date = date.date()

        # Before 2025: use fixed rates
        if date.year < 2025:
            if currency == "USD":
                return Decimal("4.00")
            elif currency == "EUR":
                return Decimal("4.30")
            return Decimal("4.00")

        # 2025: USD/PLN trajectory approximately 4.10 → 3.81
        days_in_2025 = (date - datetime(2025, 1, 1).date()).days
        if currency == "USD":
            # Start ~4.10, decline to ~3.81 by year end
            rate = Decimal("4.10") - Decimal(str(days_in_2025 * 0.0008))
            return rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        elif currency == "EUR":
            # EUR/PLN more stable, ~4.30 throughout
            rate = Decimal("4.30") - Decimal(str(days_in_2025 * 0.0001))
            return rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        return Decimal("4.00")

    def clear_cache(self):
        pass


def run_pipeline():
    """Run the pipeline with mock NBP."""
    print("\n" + "="*70)
    print("RUNNING PIPELINE WITH REALISTIC MOCK NBP")
    print("="*70)

    nbp = RealisticMockNBP()
    pipeline = Pipeline(
        year=2025,
        data_dir=Path("data/2025"),
        nbp_client=nbp,
        verbose=True
    )

    result = pipeline.run(prior_year_loss=Decimal("0"))

    print("\n" + "="*70)
    print("PIPELINE SUMMARY")
    print("="*70)
    print(f"Stocks (closed):       {len(result['_detail']['stocks'])}")
    print(f"Crypto (taxable):      {len(result['_detail']['crypto'])}")
    print(f"Dividends:             {len(result['_detail']['dividends'])}")
    print(f"Part C dochód (PLN):   {result.get('czesc_C', {}).get('dochod_pln', 'N/A')}")

    return result


def sample_transactions(result, sample_pct=0.10):
    """Randomly sample 10% of transactions."""
    stocks = result['_detail']['stocks']
    dividends = result['_detail']['dividends']
    crypto = result['_detail']['crypto']

    # Sample: 10% of stocks, 10% of dividends, all crypto (small set)
    stock_sample_size = max(1, int(len(stocks) * sample_pct))
    div_sample_size = max(1, int(len(dividends) * sample_pct))

    print(f"\nSampling {stock_sample_size} stocks (out of {len(stocks)})")
    print(f"Sampling {div_sample_size} dividends (out of {len(dividends)})")

    stock_indices = random.sample(range(len(stocks)), min(stock_sample_size, 8))
    div_indices = random.sample(range(len(dividends)), min(div_sample_size, 3))

    return {
        'stocks': [(i, stocks[i]) for i in stock_indices],
        'dividends': [(i, dividends[i]) for i in div_indices],
        'crypto': crypto,
    }


def read_pnl_csv(pnl_path):
    """Read the P&L CSV and index by symbol + dates for lookup."""
    pnl_stocks = {}
    pnl_divs = {}

    with open(pnl_path) as f:
        reader = csv.DictReader(f)
        section = None
        for row in reader:
            if row.get('Date acquired') is None:
                section = None
                continue

            if 'Income from Sells' in str(row) or (row.get('Date acquired') and row.get('Date sold') and row.get('Gross proceeds')):
                section = 'sells'

            if section == 'sells' or ('Date acquired' in row and 'Date sold' in row and 'Gross proceeds' in row):
                key = (row['Symbol'].strip(), row['Date acquired'].strip(), row['Date sold'].strip())
                pnl_stocks[key] = row
            elif 'Date' in row and 'Gross amount' in row and section is None:
                # Other income section
                key = (row['Symbol'].strip(), row['Date'].strip())
                pnl_divs[key] = row

    return pnl_stocks, pnl_divs


def verify_stock_calculation(stock_data, pnl_data, mock_nbp):
    """Manually verify a single stock position."""
    symbol = stock_data['symbol']
    date_acq = stock_data['date_acquired']
    date_sold = stock_data['date_sold']
    currency = stock_data['currency']

    # Parse dates
    if isinstance(date_acq, str):
        date_acq = datetime.fromisoformat(date_acq).date()
    else:
        date_acq = date_acq.date() if hasattr(date_acq, 'date') else date_acq

    if isinstance(date_sold, str):
        date_sold = datetime.fromisoformat(date_sold).date()
    else:
        date_sold = date_sold.date() if hasattr(date_sold, 'date') else date_sold

    cost_foreign = stock_data['cost_basis_foreign']
    proceeds_foreign = stock_data['proceeds_foreign']

    # Manually fetch rates
    cost_rate = mock_nbp.get_rate(currency, date_acq, use_d_minus_1=True)
    sell_rate = mock_nbp.get_rate(currency, date_sold, use_d_minus_1=True)

    # Manually calculate
    cost_pln_manual = round_grosz(cost_foreign * cost_rate)
    proceeds_pln_manual = round_grosz(proceeds_foreign * sell_rate)
    gain_pln_manual = proceeds_pln_manual - cost_pln_manual

    # Compare to tool's output
    tool_cost_pln = stock_data['cost_basis_pln']
    tool_proceeds_pln = stock_data['proceeds_pln']
    tool_gain = stock_data['gain_pln']

    match = (cost_pln_manual == tool_cost_pln and
             proceeds_pln_manual == tool_proceeds_pln and
             gain_pln_manual == tool_gain)

    return {
        'symbol': symbol,
        'date_acquired': date_acq,
        'date_sold': date_sold,
        'currency': currency,
        'manual_cost_pln': cost_pln_manual,
        'tool_cost_pln': tool_cost_pln,
        'manual_proceeds_pln': proceeds_pln_manual,
        'tool_proceeds_pln': tool_proceeds_pln,
        'manual_gain_pln': gain_pln_manual,
        'tool_gain_pln': tool_gain,
        'cost_rate': cost_rate,
        'sell_rate': sell_rate,
        'match': match,
    }


def verify_dividend_calculation(div_data, mock_nbp):
    """Manually verify a single dividend."""
    symbol = div_data.get('symbol', 'UNKNOWN')
    date = div_data.get('date')
    currency = div_data.get('currency', 'USD')

    # Parse date
    if isinstance(date, str):
        date = datetime.fromisoformat(date).date()
    elif date:
        date = date.date() if hasattr(date, 'date') else date

    gross_foreign = Decimal(str(div_data.get('gross_foreign', '0')))
    wht_foreign = Decimal(str(div_data.get('wht_foreign', '0')))

    if currency == "PLN":
        # Already in PLN, use as-is
        rate = Decimal("1")
        gross_pln_manual = round_grosz(gross_foreign) if gross_foreign else Decimal("0")
        wht_pln_manual = round_grosz(wht_foreign) if wht_foreign else Decimal("0")
    else:
        rate = mock_nbp.get_rate(currency, date, use_d_minus_1=True) if date else Decimal("4.00")
        gross_pln_manual = round_grosz(gross_foreign * rate) if gross_foreign else Decimal("0")
        wht_pln_manual = round_grosz(wht_foreign * rate) if wht_foreign else Decimal("0")

    # Tool's values - from pipeline which adds gross_pln and wht_paid_pln from dividend calculator
    tool_gross_pln = div_data.get('gross_pln')
    tool_wht_pln = div_data.get('wht_paid_pln')

    # Convert to Decimal if strings
    if tool_gross_pln is not None:
        tool_gross_pln = Decimal(str(tool_gross_pln))
    if tool_wht_pln is not None:
        tool_wht_pln = Decimal(str(tool_wht_pln))

    match = tool_gross_pln is not None and tool_wht_pln is not None and (gross_pln_manual == tool_gross_pln and wht_pln_manual == tool_wht_pln)

    return {
        'symbol': symbol,
        'date': date,
        'currency': currency,
        'manual_gross_pln': gross_pln_manual,
        'tool_gross_pln': tool_gross_pln,
        'manual_wht_pln': wht_pln_manual,
        'tool_wht_pln': tool_wht_pln,
        'rate': rate,
        'match': match,
        'raw_div_data': div_data,
    }


def check_edge_cases(result):
    """Verify known edge cases."""
    issues = []

    # 1. RNDR swap exclusion
    crypto = result['_detail']['crypto']
    rndr_found = any(p['symbol'] == 'RNDR' for p in crypto)
    if rndr_found:
        issues.append("RNDR swap NOT excluded from crypto closed positions")

    # 2. Pre-2025 acquisitions
    stocks = result['_detail']['stocks']
    pre_2025_count = sum(1 for s in stocks if s['date_acquired'].year < 2025)
    print(f"\nStocks acquired before 2025: {pre_2025_count}")

    # 3. EUR stocks (VOW3)
    eur_stocks = [s for s in stocks if s['currency'] == 'EUR']
    print(f"EUR stocks in sample: {len(eur_stocks)}")
    if eur_stocks:
        for s in eur_stocks:
            if s['cost_rate_nbp'] == Decimal("4.00"):
                issues.append(f"{s['symbol']}: EUR rate not properly applied (looks like USD rate)")

    # 4. PLN dividends
    divs = result['_detail']['dividends']
    pln_divs = [d for d in divs if d['currency'] == 'PLN']
    print(f"PLN dividends: {len(pln_divs)}")
    if pln_divs:
        for d in pln_divs:
            if d['nbp_rate'] != Decimal("1"):
                issues.append(f"{d['symbol']}: PLN dividend incorrectly converted (rate={d['nbp_rate']})")

    return issues


if __name__ == '__main__':
    random.seed(42)  # For reproducibility

    result = run_pipeline()

    print("\n" + "="*70)
    print("SAMPLING 10% FOR INDEPENDENT VERIFICATION")
    print("="*70)

    sample = sample_transactions(result, sample_pct=0.10)
    mock_nbp = RealisticMockNBP()

    # Verify stocks
    print("\n" + "-"*70)
    print("STOCK VERIFICATION")
    print("-"*70)

    stock_results = []
    for idx, stock_data in sample['stocks']:
        result_dict = verify_stock_calculation(stock_data, None, mock_nbp)
        stock_results.append(result_dict)

        status = "✓ MATCH" if result_dict['match'] else "✗ MISMATCH"
        print(f"\n{status}: {result_dict['symbol']} ({result_dict['date_acquired']} → {result_dict['date_sold']})")
        print(f"  Cost:    manual={result_dict['manual_cost_pln']:>10} tool={result_dict['tool_cost_pln']:>10}")
        print(f"  Proceeds: manual={result_dict['manual_proceeds_pln']:>10} tool={result_dict['tool_proceeds_pln']:>10}")
        print(f"  Gain:     manual={result_dict['manual_gain_pln']:>10} tool={result_dict['tool_gain_pln']:>10}")
        print(f"  Rates: cost={result_dict['cost_rate']} sell={result_dict['sell_rate']}")

    # Verify dividends
    print("\n" + "-"*70)
    print("DIVIDEND VERIFICATION")
    print("-"*70)

    div_results = []
    for idx, div_data in sample['dividends']:
        # Debug: print raw data structure
        print(f"\n--- Raw dividend data keys: {list(div_data.keys())}")

        result_dict = verify_dividend_calculation(div_data, mock_nbp)
        div_results.append(result_dict)

        status = "✓ MATCH" if result_dict['match'] else "✗ MISMATCH" if result_dict['match'] is not None else "? UNABLE_TO_VERIFY"
        print(f"\n{status}: {result_dict['symbol']} ({result_dict['date']})")
        print(f"  Currency: {result_dict['currency']} (rate={result_dict['rate']})")
        if result_dict['tool_gross_pln'] is not None:
            print(f"  Gross:    manual={result_dict['manual_gross_pln']:>10} tool={result_dict['tool_gross_pln']:>10}")
            print(f"  WHT:      manual={result_dict['manual_wht_pln']:>10} tool={result_dict['tool_wht_pln']:>10}")
        else:
            print(f"  Tool data missing - raw data: {result_dict['raw_div_data']}")

    # Edge cases
    print("\n" + "-"*70)
    print("EDGE CASE VERIFICATION")
    print("-"*70)

    edge_issues = check_edge_cases(result)
    if edge_issues:
        for issue in edge_issues:
            print(f"✗ {issue}")
    else:
        print("✓ All edge cases pass")

    # Summary
    print("\n" + "="*70)
    print("AUDIT SUMMARY")
    print("="*70)

    stock_matches = sum(1 for r in stock_results if r['match'])
    div_matches = sum(1 for r in div_results if r['match'])

    print(f"\nStock matches:    {stock_matches}/{len(stock_results)}")
    print(f"Dividend matches: {div_matches}/{len(div_results)}")
    print(f"Edge case issues: {len(edge_issues)}")

    # Save detailed results for report
    with open('audit_results.txt', 'w') as f:
        f.write("STOCK RESULTS\n")
        for r in stock_results:
            f.write(f"{r}\n")
        f.write("\nDIVIDEND RESULTS\n")
        for r in div_results:
            f.write(f"{r}\n")
        f.write(f"\nEDGE ISSUES\n{edge_issues}\n")
        f.write(f"\nPIPELINE RESULT\n{result}\n")

    print("\nDetailed results saved to audit_results.txt")
