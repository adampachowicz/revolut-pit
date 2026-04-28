# Audit Trail — Manual Verification Guide

How to manually verify any number in the PIT-38 report in 5 steps.

## Example: Verify a Stock Sale Gain

You want to verify that your AAPL gain of 412.34 PLN is correct.

### Step 1: Find the Transaction

Open the **Stocks sheet** in the Excel report. Find your AAPL row:

```
Date Acquired  Date Sold    Symbol  Qty  Cost (Foreign)  Proceeds (Foreign)  NBP Rate (Acq)  NBP Rate (Sold)  Cost (PLN)  Proceeds (PLN)  Gain (PLN)
2025-01-15     2025-06-20   AAPL    10   1500.00        1600.00            4.1234          4.1234          6185.10    6597.44        412.34
```

### Step 2: Note the Dates and NBP Rates

- **Acquisition Date**: 2025-01-15
- **Acquisition NBP Rate**: 4.1234
- **Sale Date**: 2025-06-20
- **Sale NBP Rate**: 4.1234

### Step 3: Open NBP API URLs (Provided in Report)

The **NBP Rates sheet** lists all rates used. Find:
- `USD_2025-01-15` → rate 4.1234
- `USD_2025-06-20` → rate 4.1234

Click the hyperlink to verify at NBP:
- https://api.nbp.pl/api/exchangerates/rates/A/USD/2025-01-15/?format=json
- https://api.nbp.pl/api/exchangerates/rates/A/USD/2025-06-20/?format=json

The JSON response will show "mid" field with the rate.

### Step 4: Manually Calculate in PLN

**Cost basis in PLN:**
```
1500.00 USD × 4.1234 = 6185.10 PLN
```

**Proceeds in PLN:**
```
1600.00 USD × 4.1234 = 6597.44 PLN
```

**Gain in PLN:**
```
6597.44 - 6185.10 = 412.34 PLN
```

### Step 5: Compare to Report

Your manual calculation (412.34 PLN) matches the report. ✓

## Example: Verify Dividend Income

Verify a dividend of 10,000 PLN with 3,000 PLN WHT and 0 PLN tax to pay.

### Find the Transaction

Open the **Dividends sheet**:

```
Date        Symbol  Country  Gross (Foreign)  Currency  NBP Rate  Gross (PLN)  WHT (PLN)  Treaty Rate  WHT Credit  Tax to Pay
2025-03-15  AAPL    US       10000            USD       4.1234    41234        12370      15%          6185        0.00
```

### Verify the Conversion

**Gross PLN:**
```
10000 USD × 4.1234 = 41234 PLN (after rounding to grosz)
```

Verify NBP rate in **NBP Rates sheet** and click link to https://api.nbp.pl/api/exchangerates/rates/A/USD/2025-03-14/?format=json (D-1).

### Verify the WHT Credit

According to the **TAX-LOGIC.md** document:

1. **Polish tax**: 41234 × 19% = 7834.46 PLN
2. **WHT paid**: 12370 PLN (already paid abroad)
3. **Treaty rate (USA)**: 15% of 41234 = 6185.10 PLN
4. **Credit allowed**: min(12370, 6185.10) = 6185.10 PLN
5. **Tax to pay**: 7834.46 - 6185.10 = 1649.36 PLN

But the report shows 0.00 PLN. This means WHT exceeded the Polish tax. The calculation:
```
Tax to Pay = max(0, (Gross × 19%) - WHT Credit)
           = max(0, 7834.46 - 12370)
           = max(0, -4535.54)
           = 0.00 PLN ✓
```

## Example: Verify Crypto Sale

Verify a Bitcoin sale with automatic SWAP exclusion.

### Check for Excluded SWAPs

Open the **Crypto sheet** and look for the **Excluded SWAPs** expander:

```
Excluded SWAPs:
- BTC 2025-02-15 (Sell, 0.5 BTC) → converted to another coin (SWAP detected, non-taxable)
- ETH 2025-02-15 (Sell, 10 ETH) → converted to another coin (SWAP detected, non-taxable)
```

These are listed but NOT included in the gain calculation (Part E).

Verify: Count the BTC rows in the **Crypto sheet**. If you have 5 buy transactions and 4 sell transactions, but 1 sell is marked SWAP, you should see only 3 taxable sells. ✓

### Verify a Non-SWAP Sale

Find your taxable BTC sale:

```
Date Acquired  Date Sold    Symbol  Qty   Cost (Foreign)  Proceeds (Foreign)  NBP Rate (Acq)  NBP Rate (Sold)  Cost (PLN)  Proceeds (PLN)  Gain (PLN)
2025-01-20     2025-06-25   BTC     1     50000           60000              4.1234          4.1234          206170     247404         41234
```

Same verification as stocks:
1. Get NBP rates from **NBP Rates sheet** and verify via API
2. Calculate: 50000 × 4.1234 = 206170 PLN
3. Calculate: 60000 × 4.1234 = 247404 PLN
4. Calculate: 247404 - 206170 = 41234 PLN ✓

## Example: Verify Loss Carry-Forward

You have prior-year loss of 50,000 PLN and current income of 40,000 PLN.

### Check Part G

**Taxes sheet** or **Summary tab** shows:

```
Part G - Prior-year losses
Prior-year loss: 50,000.00 PLN
Applied: 40,000.00 PLN
Remaining (for next year): 10,000.00 PLN
```

Calculation:
```
Current income: 40,000 PLN
Prior loss available: 50,000 PLN
Applied loss: min(40,000, 50,000) = 40,000 PLN
Taxable income after loss: max(0, 40,000 - 40,000) = 0 PLN
Tax to pay: 0 × 19% = 0 PLN ✓
```

Verify: Your **Total income** in the summary should be 0 PLN after loss applied.

## Cross-Validation Check

The report includes a **Cross-validation sheet** comparing:

```
Our calculated total proceeds (PLN converted back): 1,234,567.89 USD
Revolut's reported total proceeds: 1,234,560.00 USD
Drift: 0.063% (< 0.5% threshold) ✓
```

This checks that our NBP conversions are consistent. If drift > 0.5%, investigate:
1. Did we miss any transactions?
2. Are our NBP rates unusual?
3. Did Revolut change an exchange rate in their P&L?

## Rounding Verification

All amounts are rounded to grosz (0.01 PLN) using **ROUND_HALF_UP**:

```
6185.105 PLN → rounds to 6185.11 PLN (0.005 rounds up)
6185.104 PLN → rounds to 6185.10 PLN (< 0.005 rounds down)
```

If you see a 1 grosz difference from your manual calculation, it's due to rounding. This is correct per Polish tax law (art. 63 Ordynacji Podatkowej).

## Full Audit Trail in JSON

For maximum transparency, download the **pit38_YYYY_audit.json** file. It contains:

```json
{
  "metadata": {
    "tax_year": 2025,
    "generated_at": "2025-04-01T10:30:00",
    "language": "en"
  },
  "audit_trail": {
    "stocks": [
      {
        "symbol": "AAPL",
        "date_acquired": "2025-01-15",
        "date_sold": "2025-06-20",
        "quantity": "10",
        "cost_basis_foreign": "1500.00",
        "nbp_rate_acquired": "4.1234",
        "cost_basis_pln": "6185.10",
        "nbp_url_acquired": "https://api.nbp.pl/api/exchangerates/rates/A/USD/2025-01-15/?format=json",
        "formulas": {
          "cost_pln": "1500.00 * 4.1234",
          "proceeds_pln": "1600.00 * 4.1234",
          "gain_pln": "6597.44 - 6185.10"
        }
      }
    ]
  }
}
```

Every field is documented with:
- Raw input values
- NBP rates with URLs for verification
- Calculation formulas
- Final rounded result

## When to Contact Your Accountant

Verify manually if:
- ❌ Drift > 0.5% (possible missed transaction)
- ❌ Rounding seems off (should be ±0.01 PLN at most)
- ❌ Tax calculation doesn't match your expectation
- ⚠️ W-8BEN warning (you should file it to reduce WHT)
- ⚠️ Loss carry-forward warning (confirm calculation)

All other cases should reconcile exactly.
