# Polish Tax Logic for PIT-38

## Legal References

This document cites the Polish **Ustawa o podatku dochodowym od osób fizycznych** (Personal Income Tax Act).

### Part C: Zbycie papierów wartościowych (Securities)

**Art. 30a**: Income from sale of securities

- **Taxable**: Sale of stocks, bonds, derivatives registered in Poland
- **Rate**: 19% flat tax
- **Reporting**: PIT-38, Part C (form JPUW)
- **Method**: FIFO (First-In-First-Out) for cost basis

**Calculation:**
```
przychód = proceeds
koszt = cost basis (including commissions, fees)
dochód = max(0, przychód - koszt)
podatek = dochód × 19%
```

**Key Rules:**
- Date of cost basis: Day of acquisition, NBP rate D-1
- Date of proceeds: Day of sale, NBP rate D-1
- Losses in one year cannot reduce gains in same year
- Losses carry forward max 5 years, max 5M PLN per year

**Sources:**
- Art. 30a ust. 1 & 2
- Rozporządzenie (EU) 2015/2366 (zabezpieczenie instrumentów finansowych)

### Part D: Dochody z zysku z papierów wartościowych, udziałów i jednostek

**Art. 24 ust. 1 pkt 1**: Dividend income

- **Taxable**: Dividends on stocks, mutual funds, etc.
- **Rate**: 19% flat tax
- **WHT Credit**: Foreign tax credit for withholding tax paid
- **Treaty**: Stawki traktatowe (treaty withholding rates)

**Calculation:**
```
przychód_brutto = gross dividend (in PLN, converted via NBP D-1)
podatek_polski = przychód_brutto × 19%
ulga = min(podatek_zagraniczny_zapłacony, przychód_brutto × stawka_traktatu)
podatek_do_zapłaty = max(0, podatek_polski - ulga)
```

**Treaty Rates (Common):**
- USA: 15% (with W-8BEN)
- Germany: 15%
- Netherlands: 15%
- UK: 10%
- Default (no treaty): 15%

**W-8BEN Form:**
- US brokers require W-8BEN to apply 15% treaty rate (not 30% statutory)
- If missing: WHT is 30%, but still capped at treaty rate for credit

**Foreign Tax Credit Limitations:**
- Credit ≤ min(WHT paid, treaty cap)
- Excess WHT (beyond treaty): Not refundable, only as credit against future tax
- Polish tax must be paid on full gross amount, minus treaty-capped credit

**Sources:**
- Art. 24 ust. 1 pkt 1
- Art. 26 ust. 1 pkt 1a (foreign tax credit)
- Umowy międzynarodowe (bilateral treaties)

### Part E: Dochody z kryptowalut

**Art. 30a** (applies to crypto as securities equivalent after 2023 ruling)

- **Taxable**: Sale of cryptocurrency for fiat
- **Non-taxable**: Crypto-to-crypto swaps (art. 17 ust. 1f exemption - no realization event)
- **Rate**: 19% flat tax
- **Method**: FIFO for cost basis

**Staking & Rewards:**
- **Staking rewards**: Income at FMV on receipt date (no tax at receipt)
- **Cost basis**: FMV on receipt date (not zero)
- **Upon sale**: Gain/loss = sale price - receipt FMV
- **Status**: Taxable when sold (if for fiat)

**Learn Rewards:**
- Same treatment as staking rewards (educational rewards)

**Calculation (Sale):**
```
przychód = proceeds_in_fiat
koszt = cost_basis (FMV at acquisition or receipt)
dochód = max(0, przychód - koszt)
podatek = dochód × 19%
```

**Example: Ethereum Staking**
- 2025-01-15: Receive 0.1 ETH staking reward
  - FMV at receipt: $3,000 × 0.1 = $300
  - Cost basis: $300 (converted to PLN via NBP)
  - No tax yet
- 2025-06-01: Sell 0.1 ETH for $3,500
  - Proceeds: $3,500 (converted to PLN)
  - Cost basis: $300 (converted to PLN)
  - Gain: Proceeds - Cost (in PLN)
  - Tax: Gain × 19%

**Swap Detection (Non-taxable):**
- Same quantity Sell + Buy at same timestamp
- Different cryptocurrencies (e.g., RNDR → RENDER)
- Action: Exclude from Part E

**Sources:**
- Art. 30a ust. 1 (securities apply to crypto)
- Art. 17 ust. 1f (exemption for crypto-to-crypto with no intermediary gain)
- Interpretacja Dyrektora KIS z 2023

### Part G: Straty z lat ubiegłych

**Art. 7e**: Loss carry-forward

- **Period**: Max 5 years back from current year
- **Annual limit**: Max 5M PLN per year (nie art. 7e ust. 3)
- **Application**: Reduces total income (not individual gains)
- **Priority**: Voluntary (not automatic)

**Example:**
- 2024: Loss of 1M PLN
- 2025: Capital gains of 500k PLN
  - Can deduct 500k PLN from 1M PLN loss
  - Remaining 500k PLN loss carries to 2026

**Sources:**
- Art. 7e
- Art. 7g (special rules for business)

## Exchange Rates (NBP)

**Polish Tax Rule**: Use official NBP mid-rate from **last business day before transaction**.

**Endpoint**: Table A (main currencies)
```
https://api.nbp.pl/api/exchangerates/rates/A/{CURRENCY}/{DATE}/?format=json
```

**Fallback**: Table B (if not in A)

**Exceptions:**
- No rate published: Step back up to 7 business days
- Weekend/Holiday: Automatically handled (step back to last business day)

**Rounding**: 4 decimal places (as per NBP publication)

## Tax Filing Form PIT-38

**Form**: PIT-38 (Druk PIT-38)
**Sections Handled:**
- **Part C** (czesc_C): Securities (papiery wartościowe)
- **Part D** (czesc_D): Dividends (dochody z zysku)
- **Part E** (czesc_E): Crypto (kryptowaluty)
- **Part G** (czesc_G): Prior losses (straty)
- **Attachment PIT/ZG**: Foreign income by country (dochody zagraniczne)

**Bottom Line**: Total tax to pay

## Special Situations

### 1. Commission & Fees

**Buy**: Added to cost basis
```
cost_basis = (quantity × price_per_unit) + commission
```

**Sell**: Subtracted from proceeds
```
proceeds = (quantity × selling_price) - commission
```

### 2. Multiple Buys, One Sell (FIFO)

Revolut calculates FIFO automatically in profit_and_loss; we validate via our own FIFO.

### 3. Stock Split

**Example**: 10:1 split
- Original: 10 shares @ $100 = $1,000 cost basis
- After split: 100 shares @ $10 = $1,000 cost basis (same)
- Recorded as: quantity ×10, cost_per_unit ÷10

### 4. Dividend Reinvestment (DRIP)

- **Received**: Dividends taxed as normal dividend income (Part D)
- **Reinvested**: New shares added to FIFO (cost = dividend amount + purchase fees)
- **Sold**: Normal FIFO applies

### 5. Partial Year (Moved to Poland mid-year)

- Trades before move: Still report in Polish PIT-38
- Trades in home country: Possible double-taxation relief (treaty dependent)
- Files: Both jurisdictions may claim

### 6. Transfer Between Accounts

**Same ownership**: Non-taxable event
- Cost basis: Maintained (not revalued)
- Example: Revolut Trading → Revolut Securities Europe (internal transfer)

**Different ownership**: Treated as sale + purchase
- First owner: Taxable at market value on transfer date
- Second owner: New cost basis = market value at receipt

## Disclaimers & Caveats

1. **Not Legal Advice**: This document explains the tax logic implemented in revolut-pit. It is not a substitute for professional tax advice.

2. **Interpretations Change**: Polish tax law and NBP rules change. Always verify with current law and a tax advisor.

3. **Treaties**: Treaty rates assume valid W-8BEN. Verify treaty applicability for your situation.

4. **Staking**: Crypto staking tax treatment is evolving. Some jurisdictions treat it differently. Verify locally.

5. **Losses**: Loss carry-forward rules have caps and limitations. Consult a tax advisor for complex scenarios.

6. **Multi-year**: Losses spanning multiple years must be applied in order (FIFO for losses too).

---

**For implementation details, see HOW-IT-WORKS.md**

## Country Code Determination for PIT/ZG

**Important**: The country code used in PIT/ZG reporting is determined by the **ISIN prefix** (first 2 characters), which represents the **issuer's country** or **listing country**, not necessarily the **source country of income** for treaty purposes.

### How It Works

```
ISIN: US0378331005 (Apple Inc.)
→ Country code: US (issuer country = United States)

ISIN: IE00B4L5Y983 (iShares MSCI USA)
→ Country code: IE (ETF domiciled in Ireland, even if it holds US stocks)
```

### What This Means for Tax Treaties

**Treaty Rates** (in dividends.py):
- Applied based on the ISIN country code
- US-sourced income gets US treaty rate (15% per US-Poland treaty)
- IE-sourced income gets Ireland treaty rate (15% per Ireland-Poland treaty)

**Important Caveat**: The ISIN country is a heuristic and may NOT match the true economic source of income:

**Example 1: US Stocks Traded on German Exchange**
- ISIN: `DE0005...` (German listing)
- Tool reports: Germany (DE)
- Economic source: United States
- Impact: May apply wrong treaty rate if DE rate differs from US rate
- **Fix**: Manually verify the issuer's country and override if needed

**Example 2: Irish-Domiciled ETF Holding US Stocks**
- ISIN: `IE00B0...` (Irish ETF)
- Tool reports: Ireland (IE)
- Economic source: Complex (Ireland-registered entity with US holdings)
- Impact: IE treaty rate applied, though dividend source may be US
- **Fix**: Consult ETF prospectus; may need separate reporting

**Example 3: Luxembourgish Fund with Global Holdings**
- ISIN: `LU...`
- Tool reports: Luxembourg
- Economic source: Multiple countries (mixed)
- Impact: Single treaty rate applied (may not match component sources)
- **Fix**: For funds, consider reporting by underlying assets (consult accountant)

### How to Override Country Codes

If the tool's ISIN-based country detection doesn't match your situation:

1. **Manual Verification**: Check the issuer country in Revolut or ISIN database
2. **Separate Reporting**: Report manually adjusted figures in PIT/ZG
3. **Accountant Review**: If significant, have a tax advisor confirm treaty application

**Note:** The tool does NOT provide a user-facing override mechanism yet. If you need custom country mapping, please open a GitHub issue or modify the source code (see `isin_to_country()` in `pipeline.py`).

### Broker Location (Revolut) vs. Income Source

Revolut operates through:
- **Revolut Trading UAB** (Lithuania) for stocks and ETFs
- **Revolut Securities Europe d.o.o.** (Croatia) for some instruments

**Important**: The broker's location (Lithuania/Croatia) does NOT determine the income source for treaty purposes.

Example:
- You buy AAPL (US stock) through Revolut Trading UAB (Lithuania)
- Treaty applied: US treaty rate, NOT Lithuania treaty rate
- Reason: AAPL dividend is US-sourced (ISIN: US0378331005)

The broker is merely an intermediary/custodian. Treaty rates depend on the **issuer's domicile**.

---

