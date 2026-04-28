# Safety & Guarantees

What revolut-pit guarantees, what it doesn't, and when NOT to use it.

## What We Guarantee

✅ **Open Source**: All code is publicly available on GitHub. No hidden logic.

✅ **Math is Documented**: Every calculation is explained in TAX-LOGIC.md with legal article references.

✅ **Traceable Numbers**: Every PLN value can be traced back to source data. NBP rates have API URLs.

✅ **Uses Official NBP Rates**: Fetches from https://api.nbp.pl/ (official Polish National Bank API). No 3rd-party rates.

✅ **Grosz Rounding**: Compliant with Polish tax law (art. 63 § 1 Ordynacji Podatkowej). Uses ROUND_HALF_UP.

✅ **FIFO Method**: Correctly implements art. 30b ust. 6 (stocks sold using FIFO).

✅ **Crypto SWAP Exclusion**: Correctly identifies crypto-to-crypto swaps and excludes them (art. 17 ust. 1f).

✅ **WHT Credits**: Applies treaty rates correctly (max is min(WHT paid, income × treaty_rate)).

✅ **Loss Carry-Forward**: Correctly implements 5-year limit and 5M PLN annual limit (art. 9 ust. 3).

✅ **No Network Phoning Home**: Your data is never sent anywhere. All processing is local.

✅ **Tests Pass**: 52+ automated tests verify core calculations against fixtures.

## What We DON'T Guarantee

❌ **Correctness for YOUR Situation**: Every investor is unique. Exemptions, deductions, special cases exist. We handle common cases but may miss yours.

❌ **Completeness**: We don't handle every edge case or instrument type. See "Known Limitations" below.

❌ **Replacement for Tax Advisor**: This tool is NOT tax advice. Always verify with a licensed tax advisor.

❌ **No Liability**: If you file wrong and get audited, we're not responsible. You are.

❌ **No Auto-Filing**: We generate numbers, not the actual PIT-38 form. You must copy values manually.

❌ **No Integration with e-Podatki**: We don't generate codes or submit electronically.

## Known Limitations

### Data Format
- ❌ Only supports Revolut (for now)
- ❌ Only accepts CSV (no API access to Revolut)
- ❌ Does not auto-import from email attachments

### Instruments
- ❌ CFDs (Contracts for Difference)
- ❌ Options
- ❌ Warrants
- ❌ Structured products
- ❌ Funds (mutual, ETFs in some scenarios)

### Account Types
- ❌ IKE (Individual Retirement Account)
- ❌ IKZE (Long-term savings account)
- ❌ LSPO (Young Investor Account)
- ❌ Corporate accounts (use business/CIT forms, not PIT)

### Situations
- ❌ Forex trading (currency pairs, not asset holdings)
- ❌ Margin trading
- ❌ Lending/Staking income (partial support)
- ❌ Tax-deferred dividends (special handling)

### Multi-Year Scenarios
- ❌ Loss carry-forward only goes back 5 years
- ❌ Doesn't track LSPO/IKE exemptions across years
- ❌ Assumes consistent treaty rates (treaties can change)

## When NOT to Use This Tool

### ❌ Do NOT use if you have:

1. **CFDs or Options**
   - These are trading derivatives, not asset holdings
   - Tax treatment is different (margin trading tax)
   - Use PIT-36 or PIT-28S instead

2. **IKE/IKZE/LSPO in Revolut**
   - These accounts have special tax-free treatment
   - revolut-pit doesn't track account-level tax status
   - Filing requirements are different

3. **W-8BEN Issues**
   - If you've NEVER filed W-8BEN with your US brokerage (including Revolut)
   - Your WHT rate is 30% (not 15%)
   - The tool warns you but doesn't fix it
   - Go file W-8BEN with Revolut immediately

4. **Unusual Transactions**
   - Corporate actions (splits, spinoffs, mergers)
   - Warrants or other exotic securities
   - Peer-to-peer lending income
   - Talk to your accountant first

5. **Business/Professional Trading**
   - If you trade for a living (PIT-36), not investment income
   - If you're a registered trader (PIT-28S)
   - Use the appropriate tax form instead

6. **Lack of Confidence**
   - If you don't understand how FIFO works
   - If you don't trust NBP exchange rates
   - If you have any doubt about treaty rates
   - STOP and ask your accountant before filing

## Disclaimer

### PL

⚠️ **To narzędzie nie jest poradą podatkową ani prawną.**

Opracowane dla informacyjnie dla społeczności inwestorów. Każdy inwestor ma obowiązek prawidłowego rozliczenia podatków w Polsce. Używając tego narzędzia, ponosisz odpowiedzialność za:

- Poprawność danych wejściowych (CSV z Revolut)
- Interpretację wyników
- Zweryfikowanie obliczeń u doradcy podatkowego
- Złożenie prawidłowego zeznania PIT w terminie

Autor narzędzia (revolut-pit contributors) nie bierze odpowiedzialności za:
- Błędy w obliczeniach
- Niezgodność z przepisami prawa podatkowego
- Sankcje lub odszkodowania wynikające z nieprawidłowego rozliczenia
- Zmianę interpretacji przepisów

**Zawsze zweryfikuj wyniki z licencjonowanym doradcą podatkowym przed złożeniem.**

### EN

⚠️ **This tool is NOT tax or legal advice.**

Developed informally for the investor community. Every investor has a duty to properly file taxes in Poland. By using this tool, you assume responsibility for:

- Accuracy of input data (CSV from Revolut)
- Interpretation of results
- Verification of calculations with a tax advisor
- Timely and correct filing of tax returns

The author of this tool (revolut-pit contributors) assumes NO responsibility for:
- Calculation errors
- Non-compliance with tax law
- Penalties or damages from incorrect filing
- Changes in legal interpretation

**Always verify results with a licensed tax advisor before filing.**

## Getting Help

- **Technical bug?** Open an issue on GitHub
- **Tax question?** Consult your accountant (not the tool author)
- **Data issue?** Check AUDIT-TRAIL.md to verify manually
- **Missing instrument?** See ADD-BROKER.md for plugin architecture

## License

MIT License. You can use, modify, distribute freely. But doing so does NOT include tax consultation.

---

## ⚠️ UWAGA — Staking Rewards Tax Treatment (CRITICAL)

**IMPORTANT:** This tool treats staking rewards as **NOT taxed at receipt**, only when sold for fiat.

### The Issue

Staking rewards (from validators, delegation, or proof-of-stake protocols) have **unclear tax treatment in Poland**.

- **Tool's assumption** (optimistic): Staking rewards = taxable only when sold (like unrealized gains)
  - At receipt: Cost basis = fair market value (FMV) at receipt time (using NBP D-1 rate or external source)
  - Upon sale: Gain/loss = sale price - FMV at receipt
  - This follows the model used in some OECD countries

- **Polish KIS official position**: There is NO published official KIS interpretation (as of 2025)
  - KIS's 2023 crypto ruling (0113-KDIT-4.4011.287.2022.1.MJ) does NOT mention staking
  - Tax authorities have NOT clarified whether staking is:
    - "Zwykłe przychody" (ordinary income, taxed at receipt)
    - "Dochody z aktywów" (asset income, taxed on sale like regular gains)
    - Something else entirely

- **Conservative alternative** (safer, less favorable): Staking rewards = taxable at receipt as ordinary income
  - Gross income: FMV at receipt time
  - This matches OECD position and is more defensible in audit
  - Results in higher tax if staking rewards are significant

### Your Risk

If you use this tool's optimistic approach and KIS later rules differently:
- You may owe back taxes + interest + penalties on staking rewards
- Potential audit exposure if reward amounts are large

### What To Do

**If you have significant staking rewards:**
1. Obtain a private tax interpretation (Indywidualna Interpretacja Przepisów Prawa Podatkowego) from KIS
2. Consult a Polish tax advisor specializing in crypto
3. Consider using the `--staking-mode conservative` flag (see CLI options below)

**If rewards are minimal (< 1000 PLN/year):**
- Risk is low either way
- Tool's optimistic approach is acceptable for most cases

### CLI Option: --staking-mode

When running the tool:

```bash
# Optimistic (default): Tax staking rewards only at sale
revolut-pit --staking-mode optimistic --year 2025

# Conservative: Tax staking rewards at receipt as ordinary income (PIT-37)
revolut-pit --staking-mode conservative --year 2025
```

When set to `conservative`:
- A separate "Staking Rewards Report" is generated
- Shows staking income as if reported on PIT-37 (ordinary income) at FMV at receipt
- Allows you to compare both scenarios
- You can then choose which approach to file

### The Law (What We Know)

Polish sources do NOT provide clear guidance:
- Art. 30a PIT (crypto income): Silent on staking
- Art. 17 ust. 1f PIT (currency exchanges): Exempts crypto-to-crypto swaps, not staking
- KIS guidance: Only covers realized gains, not ongoing validator rewards

International references (for context only):
- **US (IRS)**: Staking income = ordinary income at FMV at receipt (Treasury guidance 2023)
- **Germany (BZSt)**: Staking rewards = taxable income at receipt
- **UK (HMRC)**: Staking income = miscellaneous income at receipt

### Example Scenario

Assume you received 2 ETH staking rewards in 2025:
- Receipt date: Jun 1, 2025
- FMV at receipt: EUR 3,500/ETH (NBP D-1 rate: 4.27 PLN/EUR) = 29,890 PLN
- Sale date: Dec 15, 2025
- Sale price: EUR 3,800/ETH (NBP D-1 rate: 4.30 PLN/EUR) = 32,680 PLN
- Gain on staking: 32,680 - 29,890 = 2,790 PLN

**Tool's optimistic calculation (Part E):**
- Cost basis: 29,890 PLN
- Proceeds: 32,680 PLN
- Taxable gain: 2,790 PLN × 19% tax = 530.10 PLN

**Conservative calculation (PIT-37, ordinary income):**
- Gross staking income at receipt: 29,890 PLN
- Tax on receipt (scaled rate, ~17% example): ~5,081 PLN
- Upon sale: cost basis = 29,890 PLN, gain = 2,790 PLN (same, no additional tax)
- Total tax scenario: Higher than optimistic

The difference is whether you pay tax on the 29,890 PLN receipt value (conservative) or only on the 2,790 PLN gain (optimistic).

**Before filing with significant staking, verify your approach with a tax advisor.**

---
