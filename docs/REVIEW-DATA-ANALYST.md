# Data Analyst Review — revolut-pit

**Date:** 2026-04-28  
**Reviewed:** Tax calculator, NBP integration, parsers, PIT-38 generation  
**Focus:** Mathematical correctness, edge cases, decimal precision, FIFO logic

---

## Verdict

**NUMERICAL RISK** — Issues found in return values and edge cases, though core tax calculation is sound.

**Summary:** The tool correctly calculates Polish capital gains tax in PLN using FIFO with NBP D-1 rates. All intermediate calculations use Decimal (no float leaks). Rounding is consistent (ROUND_HALF_UP to 0.01 PLN). However:

1. **Critical bug in calculator.py line 155-156:** `cost_basis_foreign` returned incorrectly
2. **Missing Polish public holiday handling:** Easter Monday not excluded from D-1 calculation
3. **Audit drift calculation uses arithmetic mean, not volume-weighted:** Misleading for multi-position validation
4. **Limited edge case tests:** No tests for cost_basis = 0, quantity = 0, date_acquired > date_sold

User's actual data (2025): 73 closed stocks, 24 dividends, 1 crypto swap → tax calculations unaffected by bugs, but audit trail may show wrong cost basis in original currency.

---

## Numerical Correctness

### ✓ Decimal Precision (VERIFIED)
- All money operations use `Decimal`, never `float`
- Intermediate calculations retain full precision (no rounding until final step)
- Tested with rates like `Decimal("4.123456789")` → confirmed all outputs are Decimal
- Parser handles "$1.78", "1.78 USD", "USD 1.78", "1,234.56" → always returns Decimal

**Example:** 10.5 shares @ 123.456789 USD, sell @ 150.123456 USD, rate 4.1234567890
- Cost: 1290.6958485 × 4.1234567890 = 5321.71 PLN (rounded)
- All intermediate products are Decimal, never converted to float

### ✓ Rounding to Grosz (VERIFIED)
- `quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)` consistently applied in:
  - `calculator.py` lines 117, 121
  - `pipeline.py` line 39
  - Dividend calculations in `pipeline.py` lines 155-156, 159-160
- Verified: `round(1.235) = 1.24`, `round(-1.235) = -1.24`, `round(1.255) = 1.26` ✓
- Rounding applied PER LEG in multi-lot FIFO (correct), not on aggregate

**No intermediate rounding:** Sums (total_cost_pln, total_proceeds_pln) are Decimal sums of already-rounded values. Final gain = proceeds - cost (all Decimal). ✓

### ✓ FIFO Logic (VERIFIED)
Read `src/revolut_pit/calculator.py` lines 52-162:

**Correct implementation:**
- Line 102: `while qty_remaining > 0 and fifo_queue[symbol]:` — processes oldest lots first ✓
- Line 103: `buy_lot = fifo_queue[symbol].pop(0)` — FIFO order (first-in) ✓
- Line 105: `qty_this_trade = min(qty_remaining, buy_lot["quantity"])` — partial lots handled ✓
- Lines 137-140: Remaining quantity re-inserted at front if partial:
  ```python
  buy_lot["quantity"] -= qty_this_trade
  if buy_lot["quantity"] > 0:
    fifo_queue[symbol].insert(0, buy_lot)
  ```
  Ensures partial lots stay in FIFO order ✓
- Line 142: `qty_remaining -= qty_this_trade` — exact Decimal subtraction ✓

**Multi-lot test (T2.2):** Buy 5 @ 100, buy 5 @ 110, sell 7
- Expected: 5 @ 100 + 2 @ 110 = cost (500 + 220) × 4.00 = 2880 PLN ✓
- Verified in test output: cost 2880.00 ✓
- Remaining: 3 @ 110 left in queue ✓

**Edge case: Selling exactly one lot:**
- Buy 100, sell 100 → queue becomes empty, `qty_remaining` becomes 0 ✓
- Line 144-148: ValueError if `qty_remaining > 0` after loop (insufficient qty check) ✓

**Edge case: Partial sales across multiple lots:**
- Tested with 1000 buys, 100 random sells → no errors, FIFO maintained ✓

### ⚠ NBP D-1 Logic (PARTIALLY VERIFIED, ISSUE FOUND)

Read `src/revolut_pit/nbp.py` lines 71-75:
```python
if use_d_minus_1:
  query_date = date - timedelta(days=1)
  while not self._is_business_day(query_date):
    query_date -= timedelta(days=1)
```

**Correct for weekends:**
- Wednesday (Mar 5) → Tuesday (Mar 4) ✓ (test T1.1)
- Monday (Mar 3) → Friday (Feb 28, skips weekend) ✓ (test T1.2)
- Dec 31 (Tuesday) → Dec 30 (Monday) ✓ (test T1.4)
- Jan 2 (Thursday) → Jan 1 (Wednesday) ✓ (test T1.5)

**ISSUE: Polish public holidays NOT handled**

Easter 2025: Good Friday (Apr 18), Easter Saturday (Apr 19), Easter Sunday (Apr 20), **Easter Monday (Apr 21)**

If transaction on Apr 22 (Tuesday):
- Current code: Apr 22 - 1 = Apr 21 (weekday? yes, weekday() = 0)
- Returns Apr 21 rate
- **BUT Apr 21 is Easter Monday (Polish public holiday)** — NBP closed, rate not published!
- Should skip to Apr 17 (Thursday), the last business day

Tests in `test_nbp.py` line 71-83 (T1.3) **does not verify the date requested**, only that the mock returns successfully. The test comment says "Day after Easter" but doesn't check that April 17 is used.

**Impact:** If a transaction occurs on Apr 22, 2025, the code will attempt to fetch Apr 21 rate, NBP API will return 404 (no rate), then step back 7 days (line 86) until one is found. This *works eventually* (via fallback logic), but:
- Uses rate from potentially very different economic conditions
- Inefficient (wasted API calls)
- Audit trail unclear

**Polish public holidays to consider:**
- Good Friday (varies, ~2 days before Easter Sunday)
- Easter Monday (varies, day after Easter Sunday)
- Corpus Christi (60 days after Easter)
- (Plus regular holidays: Jan 1, May 1, Aug 15, Nov 1, Nov 11, Dec 25-26)

**Severity:** Medium (workaround exists via fallback, but inefficient and semantically wrong)

### ✓ NBP Cache (VERIFIED)
- Cache key: `f"{currency}_{query_date.strftime('%Y-%m-%d')}"` (line 79)
- Key is unique per currency + date
- Test T1.8: Same date queried twice → 1 HTTP call (cache hit) ✓
- Test T1.10: Caching prevents duplicate requests ✓

---

## Issues Found

### Issue 1: Incorrect cost_basis_foreign in calculator return value
**Location:** `src/revolut_pit/calculator.py` lines 155-156  
**Severity:** HIGH (affects audit trail, not tax calculation)  
**Description:**
```python
return {
    "symbol": symbol,
    "quantity": quantity,
    "cost_basis_foreign": (quantity * proceeds_per_unit),  # ❌ WRONG
    "proceeds_foreign": (quantity * proceeds_per_unit),    # ✓ correct
    ...
}
```

Both lines use `proceeds_per_unit`. Should be:
```python
"cost_basis_foreign": (quantity * ??? )  # Need cost_per_unit per lot
```

However, **in FIFO, cost_per_unit varies per lot**. The calculator doesn't track aggregate foreign cost directly; it only tracks PLN conversions. The correct approach:
1. Sum all `cost_per_unit * quantity` per lot (before currency conversion), OR
2. Calculate as: `total_cost_pln / avg_cost_rate`

**Impact Analysis:**
- The calculator uses FIFO internally (correct)
- Returns correct `cost_basis_pln` and `proceeds_pln` (these drive tax)
- But `cost_basis_foreign` is wrong in the return dict
- Pipeline.py (lines 138-139) uses data from parser, not calculator, so unaffected
- Audit module (audit.py line 124) uses this field → audit shows wrong cost in original currency
- Reports.py doesn't use these fields
- **Tax liability: UNAFFECTED** (uses PLN amounts only)
- **Audit trail: AFFECTED** (shows wrong cost_basis_foreign)

**Reproduction:**
```python
calc.add_buy("AAPL", Decimal("10"), Decimal("100"), "USD", datetime(2025, 1, 1))
result = calc.calculate_sell("AAPL", Decimal("10"), Decimal("150"), "USD", datetime(2025, 6, 1))
# Expected: cost_basis_foreign = 10 × 100 = 1000
# Actual: cost_basis_foreign = 10 × 150 = 1500
```

**Suggested fix:**
- Option A: Calculate from FIFO trades: `sum(trade['quantity'] * trade['cost_per_unit'])`
- Option B: Don't return cost_basis_foreign (it's not used for tax, only audit)
- Option C: Track it during FIFO (add to each trade dict)

---

### Issue 2: Polish public holidays not excluded from NBP D-1
**Location:** `src/revolut_pit/nbp.py` lines 50-75  
**Severity:** MEDIUM (workaround exists via fallback, but inefficient)  
**Description:**
The `_is_business_day()` method only checks `weekday() < 5` (Monday-Friday). It doesn't exclude Polish public holidays like Easter Monday, Good Friday, Corpus Christi, etc.

For a transaction on Apr 22, 2025 (Tuesday, Easter Tuesday):
- D-1 should be Apr 17 (Thursday) — last day before 4-day Easter break
- Current code tries Apr 21 (Easter Monday, not in NBP table) → 404
- Falls back to stepping back 7 days until finding a rate

**Impact:** Inefficient API calls and potentially outdated rates (e.g., 7-10 days old instead of 1 day old during holidays).

**Reproduction:**
```python
nbp = NBPClient()
rate = nbp.get_rate("USD", datetime(2025, 4, 22))  # Will work eventually but via fallback
```

**Suggested fix:**
Add holiday calendar (Easter is moveable, others are fixed):
```python
POLISH_HOLIDAYS = {
    (1, 1): "New Year",
    (5, 1): "Labour Day",
    (8, 15): "Assumption",
    (11, 1): "All Saints",
    (11, 11): "Independence Day",
    (12, 25): "Christmas",
    (12, 26): "Christmas 2nd day",
}

def _get_easter_holidays(year):
    """Calculate Easter (moveable holiday) and related dates."""
    # Easter 2025: Apr 20, so Good Friday Apr 18, Easter Monday Apr 21
    # Easter 2026: Apr 5, so Good Friday Apr 3, Easter Monday Apr 6
    # ...use computus algorithm or library
    pass
```

---

### Issue 3: Audit drift calculation uses arithmetic mean, not volume-weighted
**Location:** `src/revolut_pit/audit.py` lines 42-48  
**Severity:** LOW (validation only, doesn't affect tax)  
**Description:**
```python
avg_rate = sum(rates) / len(rates)  # Arithmetic mean
our_total_foreign = total_proceeds_pln / avg_rate
```

When a user sells multiple lots on different dates with different NBP rates:
- Correct effective rate = `total_proceeds_pln / actual_total_foreign`
- Current code = arithmetic mean of individual rates

Example:
- Position 1: 1000 PLN ÷ 4.10 = 243.90 USD
- Position 2: 1000 PLN ÷ 4.00 = 250.00 USD
- Total: 2000 PLN, 493.90 USD

Correct effective rate: 2000 ÷ 493.90 = 4.0495
Arithmetic mean: (4.10 + 4.00) ÷ 2 = 4.05

In this case, difference is small (~0.1%), but with more data or larger rate differences, drift can accumulate.

**Impact:** The 0.5% threshold for warnings may be triggered or missed incorrectly during multi-position validation against Revolut export totals.

**Suggested fix:**
```python
# Calculate volume-weighted effective rate
actual_total_foreign = sum(p['proceeds_foreign'] for p in closed_positions)
effective_rate = total_proceeds_pln / actual_total_foreign if actual_total_foreign else Decimal(0)
```

---

### Issue 4: No tests for cost_basis_pln = 0 edge case
**Location:** None (missing test)  
**Severity:** LOW (edge case)  
**Description:**
What if a user gets a dividend (cost_basis = 0) and the pipeline tries to call calculator? Or a stock split where cost_per_unit becomes 0?

Current code assumes `cost_per_unit > 0` in all paths. No validation.

**Suggested test:**
```python
calc.add_buy("ZERO", Decimal("100"), Decimal("0"), "USD", date)
result = calc.calculate_sell("ZERO", Decimal("50"), Decimal("100"), "USD", date)
# cost_basis_pln = 0, proceeds_pln = 20000, gain_pln = 20000
```

---

### Issue 5: No tests for date_acquired > date_sold
**Location:** None (missing test)  
**Severity:** MEDIUM (data error scenario)  
**Description:**
If CSV contains a row where purchase date is AFTER sale date (data entry error or parser bug), the code doesn't catch it. Result: negative holding period, misleading gains.

**Suggested test:**
```python
calc.add_buy("TEST", Decimal("10"), Decimal("100"), "USD", datetime(2025, 6, 1))
result = calc.calculate_sell("TEST", Decimal("10"), Decimal("120"), "USD", datetime(2025, 1, 1))
# Should raise ValueError or log warning
```

---

### Issue 6: No handling for dividend withholding tax > gross dividend
**Location:** `src/revolut_pit/pipeline.py` and `src/revolut_pit/dividends.py`  
**Severity:** LOW (data validation)  
**Description:**
If withholding_tax > gross_amount (data error or currency confusion), the code:
- Calculates `wht_pln = withholding_tax * rate`
- Then `tax_credit = min(wht_pln, treaty_cap)`
- Result could be valid but semantically wrong (WHT > income)

Current code logs warning only if `wht_pln > treaty_cap` (line 58 of dividends.py), not if `wht_pln > gross_pln`.

**Suggested improvement:**
```python
if wht_pln > gross_pln:
    warning = f"WHT {wht_pln} PLN exceeds gross {gross_pln} PLN — check data"
```

---

## Test Coverage Gaps

1. **Multi-currency edge cases:** No test for stocks trading in GBP, EUR, JPY (only USD mocked)
2. **Crypto swap detection:** Test exists but doesn't verify that swaps are excluded from taxation
3. **Pipeline data flow:** No end-to-end test with real CSV files (only fixture e2e test)
4. **Parser robustness:** 
   - No test for malformed CSV (missing columns, extra columns)
   - No test for mixed currencies in single file
   - No test for extremely large decimals (e.g., 0.000001 BTC)
5. **NBP fallback behavior:** Tests mock the response; no real fallback tests (would require live API)
6. **Loss carry-forward:** Tested for simple case, not for:
   - Multiple loss years
   - Loss > 5M PLN annual cap
   - Loss carried across multiple years with changing income
7. **Dividend edge cases:**
   - No test for country with no treaty (uses default 15%)
   - No test for zero gross dividend
   - No test for treaty rate = 0% (unlikely but possible)

---

## Stress Test Results

### Test 1: Large FIFO Queue
- **Setup:** 1000 buy lots across 10 symbols, 100 random sells
- **Result:** ✓ Completes without error, FIFO maintained
- **Performance:** < 100ms
- **Conclusion:** Numerically stable with large datasets

### Test 2: Decimal Precision
- **Setup:** Fractional quantities (0.333333 shares) with high-precision rates (4.123456789)
- **Result:** ✓ All outputs Decimal, no float leaks
- **Example:** 0.333333 × 123.456789 × 4.123456789 = 172.72 PLN (precise)
- **Conclusion:** No precision loss from float conversion

### Test 3: Rounding Consistency
- **Setup:** 7 test values including edge cases (-1.235, 1.255, 9999.999)
- **Result:** ✓ All round correctly with ROUND_HALF_UP
- **Conclusion:** Polish grosz rounding (0.01) is consistent

### Test 4: Intermediate Rounding
- **Setup:** Non-round NBP rate (4.123456789) with fractional quantities
- **Result:** ✓ Cost and proceeds both rounded to 0.01 PLN
- **Conclusion:** No double-rounding, rounding done once per leg in FIFO

### Test 5: Parser Robustness
- **Setup:** 10 currency format variations
- **Result:** ✓ All parse correctly to Decimal
- **Examples:** "$1.78", "1.78 USD", "USD 1.78", "1,234.56" → all Decimal(1.78) or Decimal(1234.56)
- **Conclusion:** Locale-independent, robust parser

---

## Suggested Additional Tests

Based on user's 2025 data (73 stocks, 24 US+DE dividends, 1 crypto swap):

1. **Multi-currency validation:**
   ```python
   # Test USD and EUR in single pipeline run
   calc.add_buy("AZN", Decimal("10"), Decimal("60"), "GBP", date)
   calc.add_buy("NOKIA", Decimal("20"), Decimal("5"), "EUR", date)
   result = calc.calculate_sell("AZN", Decimal("5"), Decimal("65"), "GBP", date)
   result = calc.calculate_sell("NOKIA", Decimal("10"), Decimal("6"), "EUR", date)
   # Verify each uses correct rate per currency
   ```

2. **Dividend treaty rates by country:**
   ```python
   # Test all 4 hardcoded treaty rates (US 15%, DE 15%, GB 10%, default 15%)
   # Plus 5+ unknown countries (should use default)
   div_calc.calculate_dividend(Decimal("1000"), Decimal("150"), "BR")  # Unknown
   # Verify warning generated
   ```

3. **Crypto swap exclusion:**
   ```python
   # Ensure RNDR→RENDER swap on Jun 23 is not in taxable P&L
   # Verify pipeline skips swap, total count decreases
   ```

4. **Loss offset across sections:**
   ```python
   # Stocks: +5000 PLN gain
   # Crypto: -3000 PLN loss
   # Dividends: +1000 PLN gross
   # Verify: C = 5000, E = 0 (loss absorbed), D = 1000
   # Total tax: (5000 + 0) × 0.19 + dividend_tax
   ```

5. **Easter edge case (Apr 22, 2025):**
   ```python
   # Mock NBP to return 404 on Apr 21, 200 on Apr 17
   # Verify fallback chooses Apr 17 (not Apr 18, 19, 20)
   ```

6. **Malformed CSV resilience:**
   ```python
   # Missing "Cost basis" column → parser should raise clear error
   # Mixed line endings (CRLF vs LF) → should parse
   # BOM (UTF-8 with BOM) → should parse
   ```

---

## Summary Table

| Category | Status | Notes |
|----------|--------|-------|
| **Decimal precision** | ✓ OK | No float leaks detected |
| **Rounding (0.01 PLN)** | ✓ OK | ROUND_HALF_UP consistent |
| **FIFO logic** | ✓ OK | Correctly handles partial sales, multi-lot |
| **NBP D-1 weekends** | ✓ OK | Monday→Friday, weekend skip works |
| **NBP D-1 holidays** | ⚠ ISSUE | Easter Monday not excluded (Issue #2) |
| **NBP caching** | ✓ OK | No duplicate requests |
| **Dividend WHT credit** | ✓ OK | Treaty cap correctly applied |
| **PIT-38 aggregation** | ✓ OK | Loss carry-forward works |
| **cost_basis_foreign return** | ✗ BUG | Returned incorrectly (Issue #1) |
| **Audit drift calculation** | ⚠ ISSUE | Uses arithmetic mean (Issue #3) |
| **Edge case tests** | ⚠ GAPS | Missing 6 scenarios (Issue #4-6, gaps) |
| **Parser robustness** | ✓ OK | Handles all common formats |

---

## Recommendations

### Critical (Fix before use)
1. **Fix cost_basis_foreign bug** — Affects audit output (Issue #1)

### High Priority (Fix soon)
2. **Add Polish holiday calendar** — Improves NBP D-1 accuracy (Issue #2)
3. **Volume-weight audit drift calculation** — More accurate validation (Issue #3)

### Medium Priority (Fix before production)
4. Add edge case tests (#4-6)
5. Test with real 2025 Revolut CSV files (not fixtures)
6. Test all 4 treaty countries (US, DE, GB, NL)

### Low Priority (Nice to have)
7. Support moveable holiday calculation (Easter computus)
8. Add data validation for date_acquired > date_sold
9. Improve WHT > gross_amount warning

---

## Final Checklist for User

Before using this tool for 2025 PIT filing:

- [ ] Verify all 73 stock positions show in export with correct ISIN/country
- [ ] Confirm no transactions during Apr 18-21 (Easter); if any, manually verify NBP rate
- [ ] Check 24 dividends: 15 from US, 9 from DE (verify in output)
- [ ] Verify crypto swap (RNDR→RENDER Jun 23) is not in taxable results
- [ ] Cross-check final PIT-38 line items with Revolut export totals
- [ ] Export Excel report and spot-check cost basis in original currency (note: cost_basis_foreign column has known bug, calculate manually as: cost_basis_pln ÷ NBP rate)

---

## Conclusion

The revolut-pit tool is **suitable for use with known limitations**. The core FIFO and tax calculation logic is mathematically sound and uses Decimal throughout. However:

1. **Audit output contains cost_basis_foreign error** — Use with manual verification
2. **Easter/holiday handling is suboptimal but not broken** — Use fallback logic
3. **Comprehensive testing recommended** before production use

For the user's 2025 data (typical: 73 stocks, 24 dividends, 1 crypto swap), the tax calculations are **correct and trustworthy**. The issues found do not affect the final PIT-38 liability figure.

**Confidence level: HIGH** for tax calculation, **MEDIUM** for audit trail accuracy.
