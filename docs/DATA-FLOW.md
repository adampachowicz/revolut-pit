# Data Flow — End-to-End Pipeline

This document explains the complete data flow through revolut-pit, from CSV upload to final PIT-38 calculation.

## High-Level Pipeline

```
    ┌─────────────────────────────────────────────────────────────────┐
    │                    REVOLUT CSV FILES                            │
    │  account_statement_*.csv, profit_and_loss_*.csv,                │
    │  crypto_account_statement_*.csv, crypto_profit_and_loss_*.csv   │
    └────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                     PARSERS (Auto-detect)                       │
    │  ┌───────────────────────────────────────────────────────────┐  │
    │  │ stocks.py:     Parse account_statement & P&L              │  │
    │  │ crypto.py:     Parse crypto CSVs, detect SWAPs            │  │
    │  │ base.py:       Abstract interfaces for plugin arch        │  │
    │  └───────────────────────────────────────────────────────────┘  │
    │  Output: Parsed transactions (List[Dict])                       │
    └────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                    NBP RATE FETCHING                            │
    │  For each transaction date, fetch NBP mid-rate (D-1)            │
    │  ┌───────────────────────────────────────────────────────────┐  │
    │  │ nbp.py:        Fetch from API, handle weekends/holidays,  │  │
    │  │                cache results, retry on 429                 │  │
    │  └───────────────────────────────────────────────────────────┘  │
    │  Output: Dict[str, Decimal] (e.g., "USD_2025-06-15": 4.1234)   │
    └────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                    PIPELINE PROCESSING                          │
    │  ┌───────────────────────────────────────────────────────────┐  │
    │  │ pipeline.py:                                              │  │
    │  │   1. process_stocks()    → closed positions (C+D)         │  │
    │  │   2. process_crypto()    → closed positions (E)           │  │
    │  │   3. Currency conversion: amount × NBP_rate → PLN         │  │
    │  │   4. FIFO matching (for stocks)                           │  │
    │  │   5. Dividend credit calculation (WHT)                    │  │
    │  └───────────────────────────────────────────────────────────┘  │
    │  Output: Dict with stocks, crypto, dividends, nbp_rates         │
    └────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                    PIT-38 CALCULATION                           │
    │  ┌───────────────────────────────────────────────────────────┐  │
    │  │ pit38.py:                                                 │  │
    │  │   Part C: sum(gains from stocks)                          │  │
    │  │   Part D: sum(dividend income, apply WHT credit)          │  │
    │  │   Part E: sum(gains from crypto, exclude SWAPs)           │  │
    │  │   Part G: apply loss carry-forward (max 5 years)          │  │
    │  │   Tax = Income × 19% (or foreign tax if higher)           │  │
    │  └───────────────────────────────────────────────────────────┘  │
    │  Output: Dict with all PIT-38 fields, warnings                  │
    └────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                    REPORT GENERATION                            │
    │  ┌───────────────────────────────────────────────────────────┐  │
    │  │ reports.py:                                               │  │
    │  │   - Excel: Summary, Stocks, Crypto, Dividends, NBP rates  │  │
    │  │   - Markdown: Human-readable summary                      │  │
    │  │   - JSON: Full audit trail with formulas                  │  │
    │  └───────────────────────────────────────────────────────────┘  │
    │  Output: .xlsx, .md, .json files                                │
    └────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                    USER DOWNLOAD                                │
    │  Excel, Markdown, JSON files ready for filing                   │
    └─────────────────────────────────────────────────────────────────┘
```

## Detailed Step-by-Step

### Step 1: Parsing

**Input:** Revolut CSV files (user uploads or provides path)

**Process:**
- Auto-detect file type (stocks, crypto, dividends)
- Parse CSV columns → standardized Dict format
- Validate dates, amounts (use Decimal, not float)
- Handle missing fields gracefully (default to 0)

**Output:** Lists of transactions
```python
[
  {
    'date_acquired': datetime(2025, 1, 15),
    'date_sold': datetime(2025, 6, 20),
    'symbol': 'AAPL',
    'quantity': Decimal('10'),
    'cost_basis': Decimal('1500.00'),
    'proceeds': Decimal('1600.00'),
    'currency': 'USD',
  },
  ...
]
```

**Key Files:**
- `src/revolut_pit/parsers/revolut/stocks.py` — Stock parser
- `src/revolut_pit/parsers/revolut/crypto.py` — Crypto parser (with SWAP detection)

### Step 2: NBP Rate Fetching

**Input:** Set of unique (currency, date) pairs from transactions

**Process:**
- For each transaction date, fetch NBP mid-rate for D-1 (previous business day)
- If date is Saturday/Sunday, use Friday's rate
- If date is a holiday, step back until rate found
- Cache results to avoid re-fetching
- Retry on HTTP 429 (rate limited) with exponential backoff

**Output:** Dict mapping currency+date → rate
```python
{
  'USD_2025-06-13': Decimal('4.1234'),
  'USD_2025-06-12': Decimal('4.1256'),
  'EUR_2025-06-13': Decimal('4.5678'),
}
```

**Key Files:**
- `src/revolut_pit/nbp.py` — NBP API client

**Edge Cases:**
- Weekend: Use previous Friday's rate
- Holiday (PL or US): Step back to next business day with available rate
- First trading day of year: Step back to last rate of prior year
- Cache miss → live fetch

### Step 3: Pipeline Processing

**Input:**
- Parsed transactions (stocks, crypto)
- NBP rates Dict

**Process:**

#### 3a. Stocks Processing

1. Read profit_and_loss file → sells, other_income
2. For each sell:
   - Get cost_rate from NBP (date_acquired D-1)
   - Get sell_rate from NBP (date_sold D-1)
   - Calculate: cost_pln = cost_basis × cost_rate
   - Calculate: proceeds_pln = proceeds × sell_rate
   - Calculate: gain_pln = proceeds_pln - cost_pln
   - Store as closed position
3. For each dividend:
   - If currency == USD/EUR/etc:
     - Get nbp_rate for dividend date D-1
     - Convert gross and WHT to PLN
   - If currency == PLN: use as-is
   - Pass to DividendCalculator for WHT credit logic

#### 3b. Crypto Processing

1. Read crypto_profit_and_loss file
2. For each crypto position:
   - Check if marked as SWAP (from account_statement detection)
   - If SWAP: skip (non-taxable in Poland)
   - Otherwise: same logic as stocks (cost_rate, sell_rate, conversions)

#### 3c. Dividend Credit Calculation

See `src/revolut_pit/dividends.py`:
- Input: gross_pln, wht_pln, country_code, symbol
- Apply treaty rate based on country
- Calculate credit: min(wht_paid, gross × treaty_rate)
- Calculate tax_to_pay: max(0, gross × 0.19 - credit)

**Output:** Dict with all converted values
```python
{
  'stocks': [
    {
      'symbol': 'AAPL',
      'cost_basis_foreign': Decimal('1500.00'),
      'cost_basis_pln': Decimal('6185.10'),
      'proceeds_foreign': Decimal('1600.00'),
      'proceeds_pln': Decimal('6597.44'),
      'gain_pln': Decimal('412.34'),
      'cost_rate_nbp': Decimal('4.1234'),
      'sell_rate_nbp': Decimal('4.1234'),
    }
  ],
  'crypto': [...],
  'dividends': [...],
  'nbp_rates_used': {...},
}
```

**Key Files:**
- `src/revolut_pit/pipeline.py` — Orchestrator
- `src/revolut_pit/dividends.py` — WHT credit logic

### Step 4: PIT-38 Calculation

**Input:** Processed data from Pipeline

**Process:**

1. **Part C (Papiery wartościowe)**
   - Sum all stock gains: dochod_pln = Σ(gain_pln for stocks)
   - If negative, can carry forward (Part G)
   - Tax = dochod_pln × 0.19 (if positive)

2. **Part E (Kryptowaluty)**
   - Sum all crypto gains: dochod_pln = Σ(gain_pln for crypto, exclude SWAPs)
   - Same tax calculation as Part C

3. **Part D (Dywidendy)**
   - Handled by DividendCalculator
   - przychod_pln = Σ(gross_pln)
   - podatek_do_zaplaty = Σ(individual tax_to_pay with WHT credits)

4. **Part G (Straty z lat ubiegłych)**
   - Apply loss carry-forward (if positive income and prior losses)
   - Max 5 years back, max 5M PLN per year
   - dochod_razem = max(0, dochod_razem - prior_year_loss)

5. **Total Tax**
   - podatek_do_zaplaty = tax_C + tax_D + tax_E

6. **Warnings**
   - Missing W-8BEN form (default 30% vs 15% treaty rate)
   - Zero income but prior loss used
   - Crypto SWAPs excluded (informational)

**Output:** PIT-38 Dict
```python
{
  'rok_podatkowy': 2025,
  'czesc_C': {
    'przychod_pln': Decimal('100000.00'),
    'koszt_pln': Decimal('80000.00'),
    'dochod_pln': Decimal('20000.00'),
  },
  'czesc_D': {
    'przychod_pln': Decimal('10000.00'),
    'podatek_do_zaplaty': Decimal('0.00'),  # WHT credit
  },
  'czesc_E': {
    'przychod_pln': Decimal('50000.00'),
    'koszt_pln': Decimal('40000.00'),
    'dochod_pln': Decimal('10000.00'),
  },
  'czesc_G': {
    'strata_z_lat_ubieglych': Decimal('0.00'),
  },
  'dochod_razem': Decimal('40000.00'),
  'podatek_do_zaplaty': Decimal('7600.00'),  # 40K × 19% - 100 WHT
  'pit_zg': [...],  # Foreign income by country
  'warnings': [...],
}
```

**Key Files:**
- `src/revolut_pit/pit38.py` — PIT-38 form generation

### Step 5: Reporting

**Input:** PIT-38 dict + detail data (stocks, crypto, dividends, nbp_rates)

**Process:**

#### 5a. Excel Report
- Summary sheet: all Part C/D/E/G values
- Stocks sheet: transaction-level detail with NBP rates
- Crypto sheet: same as stocks
- Dividends sheet: with treaty rate and WHT credit
- NBP Rates sheet: all rates used (with clickable URLs)
- Audit sheet: formulas and verification steps

#### 5b. Markdown Report
- Text summary of all sections
- Suitable for printing or sharing
- Human-readable format

#### 5c. JSON Report
- Full audit trail with all calculations
- Transaction-level detail
- NBP URLs for each rate
- Formulas for manual verification

**Output:** Three report files (.xlsx, .md, .json)

**Key Files:**
- `src/revolut_pit/reports.py` — Report generator
- `src/revolut_pit/audit.py` — Audit trail generation

## Rounding Rules

All monetary amounts are rounded to **grosz (0.01 PLN)** using **ROUND_HALF_UP**:
- 0.125 PLN → 0.13 PLN (round up)
- 0.124 PLN → 0.12 PLN (round down)

This is required by Polish tax law (art. 63 § 1 Ordynacji Podatkowej).

**Implementation:**
```python
from decimal import Decimal, ROUND_HALF_UP
def round_grosz(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
```

## Error Handling

### Parse Errors
- Missing file → Log warning, skip
- Invalid CSV format → Log warning, attempt recovery
- Missing column → Assume 0 or default

### NBP Errors
- API returns 404 → Step back to prior business day
- API returns 429 (rate limited) → Retry with exponential backoff
- Network timeout → Use cached value if available
- All dates searched back 90 days (fallback)

### Calculation Errors
- Negative income → Store as is (loss carry-forward eligible)
- Division by zero → Skip (should not occur)
- Decimal overflow → Use Python's Decimal (arbitrary precision)

## Audit Trail

Every calculation is traceable:
1. **Input**: CSV row → transaction
2. **Fetch**: NBP rate with exact date used
3. **Conversion**: amount × rate with all values shown
4. **Rounding**: before/after with rounding method
5. **Aggregation**: sum of individual items with count
6. **Tax**: income × tax_rate with applied credits

Reports include:
- URL to NBP API for each rate (for manual verification)
- Formulas for each calculated field
- Transaction-level detail
- All assumptions and defaults

## Performance

- **Memory**: All data loaded into memory (typical < 100 MB for 2 years of trading)
- **Network**: ~10-50 NBP API calls (depends on unique currency+date pairs)
- **Time**: ~30-60 seconds total (mostly NBP fetches)

No database required. All data is in-memory during run, then exported to files.
