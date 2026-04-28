# How revolut-pit Works

## Overview

The tool processes Revolut CSV exports through a pipeline:

```
1. Parse CSV
   └─> account_statement_YYYY.csv
   └─> profit_and_loss_YYYY.csv
   └─> crypto_account_statement_YYYY.csv

2. Fetch NBP Rates
   └─> For each transaction, get D-1 mid-rate
   └─> Cache locally to avoid duplicates

3. FIFO Calculation
   └─> Buy lots queued by date
   └─> Sell transactions matched to lots in order
   └─> Cost & proceeds converted to PLN

4. Aggregate
   └─> Part C: Securities gains
   └─> Part D: Dividends + WHT credit
   └─> Part E: Crypto gains

5. Generate Reports
   └─> Excel with detailed breakdowns
   └─> Markdown summary
   └─> PIT/ZG (foreign income attachment)
```

## Detailed Steps

### 1. CSV Parsing

#### account_statement_YYYY.csv

Columns: `Date, Ticker, Type, Quantity, Price per share, Total Amount, Currency, FX Rate`

Types supported:
- `BUY - MARKET`, `BUY - LIMIT`: Add to FIFO queue
- `SELL - MARKET`, `SELL - LIMIT`, `SELL - STOP`: Trigger FIFO matching
- `DIVIDEND`: Extract gross, currency, WHT (from P&L)
- `CUSTODY FEE`, `CASH TOP-UP`, `TRANSFER`: Ignored

**Note**: `Total Amount` has currency prefix (e.g., `USD 1500.00`). Parsed and currency extracted.
`FX Rate` is Revolut's internal rate — **ignored for tax math** (we use NBP D-1).

#### profit_and_loss_YYYY.csv

Multi-section CSV with:

**Income from Sells:**
- Columns: `Date acquired, Date sold, Symbol, ..., Cost basis, Gross proceeds, Gross PnL, Currency`
- Revolut pre-calculates FIFO matches; we trust and validate via our own FIFO

**Other income & fees:**
- Columns: `Date, Symbol, ..., Gross amount, Withholding tax, Net Amount, Currency`
- Used to extract dividend gross, WHT, currency

#### crypto_account_statement_YYYY.csv

Columns: `Symbol, Type, Quantity, Price, Value, Fees, Date`

Date format: `"Jan 3, 2025, 6:18:28 PM"` — parsed via pandas `to_datetime`

Types:
- `Buy`, `Sell`: Fiat transactions (taxable)
- `Buy - Revolut X`: Revolut referral bonus → cost basis = 0
- `Stake`: Move to staking (not taxable)
- `Staking reward`, `Learn reward`: Income at FMV; cost basis = receipt FMV
- `Receive`, `Send`: P2P transfers (non-taxable if you own both wallets)
- `Swap` (detected): Same quantity Sell+Buy at same timestamp → crypto-to-crypto (non-taxable)

### 2. NBP Rate Fetching

**Goal**: Get official mid-rate from last **business day before** transaction.

**Algorithm:**

```python
def get_rate(currency, transaction_date):
    # 1. Calculate D-1 (step back 1 day)
    query_date = transaction_date - 1 day
    
    # 2. If D-1 is weekend/holiday, keep stepping back
    while not is_business_day(query_date):
        query_date -= 1 day
    
    # 3. Check local cache; return if hit
    if cached(currency, query_date):
        return cache_get(currency, query_date)
    
    # 4. Try Table A (main currencies)
    for i in range(MAX_RETRIES):
        attempt_date = query_date - i days
        rate = fetch_nbp_table_a(currency, attempt_date)
        if rate:
            return rate
        
        # 5. Fallback to Table B (if not in A)
        rate = fetch_nbp_table_b(currency, attempt_date)
        if rate:
            return rate
    
    raise ValueError(f"Could not find rate for {currency}")
```

**Endpoint**: `https://api.nbp.pl/api/exchangerates/rates/A/{currency}/{date}/?format=json`

**Response**: `{"rates": [{"mid": 4.25, ...}]}`

**Backoff**:
- 429 (rate limited): exponential backoff (1s, 2s, 4s, ...)
- 404 (not found): step back 1 day, max 7 attempts
- Other errors: return None, try next

**Cache**: `~/.cache/revolut_pit/nbp_rates.json`

### 3. FIFO Calculation

#### Buy Transactions

Queued per symbol:

```python
buy_queue["AAPL"] = [
    {quantity: 10, cost_per_unit: 150, currency: USD, date: 2025-01-15, rate: 4.00},
    {quantity: 5, cost_per_unit: 160, currency: USD, date: 2025-02-01, rate: 4.05},
]
```

#### Sell Transactions

Match from front of queue (FIFO):

```python
def calculate_sell(symbol, qty_sold, price_per_unit, currency, date_sold):
    cost_pln = 0
    proceeds_pln = 0
    trades = []
    
    for buy_lot in buy_queue[symbol]:
        if qty_sold == 0:
            break
        
        qty_this_lot = min(qty_sold, buy_lot.quantity)
        
        # Get rates D-1 for each leg
        buy_rate = nbp.get_rate(buy_lot.currency, buy_lot.date, use_d_minus_1=True)
        sell_rate = nbp.get_rate(currency, date_sold, use_d_minus_1=True)
        
        # Convert to PLN
        cost = qty_this_lot * buy_lot.cost_per_unit * buy_rate
        proceeds = qty_this_lot * price_per_unit * sell_rate
        gain = proceeds - cost
        
        cost_pln += cost
        proceeds_pln += proceeds
        trades.append({qty, cost, proceeds, gain})
        
        qty_sold -= qty_this_lot
    
    return {
        symbol, qty_sold, cost_pln, proceeds_pln, gain_pln=proceeds_pln-cost_pln, trades
    }
```

### 4. Rounding

**Polish Tax Rounding Rule**: Round to 1 grosz (0.01 PLN), with .5 rounding up (ROUND_HALF_UP).

```python
from decimal import Decimal, ROUND_HALF_UP

gain_pln = Decimal("1234.567")
gain_rounded = gain_pln.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)  # 1234.57
```

Apply rounding **at the END** of each transaction, not during intermediate calculations.

### 5. Dividend Tax Calculation

```python
def calculate_dividend(gross_pln, wht_pln, country_code):
    polish_tax = gross_pln * 0.19  # 19%
    treaty_rate = TREATY_RATES.get(country_code, 0.15)
    treaty_cap = gross_pln * treaty_rate
    
    # Tax credit = min(WHT paid, treaty cap)
    tax_credit = min(wht_pln, treaty_cap)
    
    # Tax to pay = Polish tax - credit
    tax_to_pay = max(0, polish_tax - tax_credit)
    
    if wht_pln > treaty_cap:
        warning = f"WHT {wht_pln} exceeds treaty cap {treaty_cap}. Check W-8BEN."
    
    return {gross_pln, wht_pln, polish_tax, treaty_cap, tax_credit, tax_to_pay, warning}
```

### 6. Aggregation & PIT-38 Structure

```python
pit38 = {
    "rok_podatkowy": 2025,
    
    "czesc_C": {  # Securities
        "przychod_pln": sum(all proceeds),
        "koszt_pln": sum(all costs),
        "dochod_pln": max(0, przychod - koszt),
    },
    
    "czesc_D": {  # Dividends
        "przychod_pln": sum(all gross dividends),
        "podatek_pl_19": sum(gross × 0.19),
        "podatek_zagraniczny": sum(WHT paid),
        "podatek_do_zaplaty": sum(tax_to_pay),
    },
    
    "czesc_E": {  # Crypto
        "przychod_pln": sum(all proceeds),
        "koszt_pln": sum(all costs),
        "dochod_pln": max(0, przychod - koszt),
    },
    
    "czesc_G": {  # Prior losses
        "strata_z_lat_ubieglych": prior_loss,
    },
    
    "pit_zg": [  # Foreign income attachment
        {kraj: "US", dochod_pln: ..., podatek_zagraniczny_pln: ...},
        ...
    ],
    
    "dochod_razem": C + E + D - G,
    "podatek_do_zaplaty": tax_c + tax_e + tax_d,
}
```

### 7. Excel Export

Sheets:
- **Summary**: Totals per section
- **Stocks**: All stock transactions (symbol, qty, cost, proceeds, gain)
- **Crypto**: All crypto sales
- **Dividends**: All dividends (symbol, country, gross, WHT, treaty rate, tax)
- **NBP Rates**: All rates used (currency, date, rate)

Formatting:
- Dates: `YYYY-MM-DD`
- Money: `#,##0.00 PLN`
- Rates: `0.0000`

### 8. Markdown Report

Summary of key sections:
- Part C/D/E totals
- Bottom line (total income, total tax)
- Any warnings (WHT > treaty, data issues, etc)

## Example Walkthrough

### Buy AAPL (USD)

Date: 2025-03-15 (Saturday)
Qty: 10
Price: $150
Total: $1,500 USD

Processing:
1. Parse: ticker=AAPL, qty=10, price=150, currency=USD
2. Queue to FIFO: `buy_queue["AAPL"].append({qty: 10, price: 150, date: 2025-03-15})`

### Sell AAPL (USD)

Date: 2025-06-20 (Friday)
Qty: 10
Price: $160
Total: $1,600 USD

Processing:
1. Parse sell
2. Get rates:
   - Buy date: 2025-03-15 (Sat) → D-1 is 2025-03-14 (Fri) → NBP rate = 4.00
   - Sell date: 2025-06-20 (Fri) → D-1 is 2025-06-19 (Thu) → NBP rate = 4.10
3. Calculate:
   - Cost: 10 × 150 × 4.00 = 6,000 PLN
   - Proceeds: 10 × 160 × 4.10 = 6,560 PLN
   - Gain: 6,560 - 6,000 = 560 PLN
4. Round: 560.00 PLN (already 2 decimals)
5. Tax: 560 × 0.19 = 106.40 PLN (Part C)

### Dividend (USD → US)

Gross: $100 USD
WHT: $15 USD (15% treaty)
Date: 2025-03-01

Processing:
1. Get rate for 2025-02-28 (D-1, skip weekend): NBP = 4.00
2. Convert:
   - Gross PLN: 100 × 4.00 = 400 PLN
   - WHT PLN: 15 × 4.00 = 60 PLN
3. Calculate:
   - Polish tax: 400 × 0.19 = 76 PLN
   - Treaty cap (15%): 400 × 0.15 = 60 PLN
   - Tax credit: min(60, 60) = 60 PLN
   - Tax to pay: max(0, 76 - 60) = 16 PLN
4. Add to Part D

## Special Cases

### Stock Split

Revolut's account statement doesn't explicitly mark splits. Manual adjustment:

```python
# 10:1 split
fifo_lot["quantity"] *= 10
fifo_lot["cost_per_unit"] /= 10
```

### Crypto SWAP (RNDR → RENDER)

Detected: same qty Sell + Buy at same timestamp
Action: Mark `is_swap=True`, exclude from Part E

### Loss on Transaction

If proceeds < cost:
```python
gain = proceeds - cost  # Negative
dochod_czesc_c = max(0, total_gain)  # Losses do not reduce in PIT-38
```

Losses carry forward 5 years, max 5M PLN applied in next year.

---

**For legal references and tax logic details, see TAX-LOGIC.md**
