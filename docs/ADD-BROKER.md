# Adding a New Broker — Step-by-Step Guide

> **Audience:** developer who wants to extend revolut-pit to a broker other
> than Revolut (Interactive Brokers, eToro, Trading 212, Saxo, XTB, mBank,
> DEGIRO, Trade Republic, etc.).
>
> **Prerequisites:** working Python environment, familiarity with `pandas`
> and `Decimal`, ability to obtain a real CSV export from the broker for at
> least one tax year.
>
> **Time estimate:** 1–2 days for a parser that handles the common cases;
> 3–5 days if you need to add new treaty rates, support new currencies, or
> add a custom format like XLSX/PDF.

---

## Table of contents

0. [Phase 0 — Preflight: do you actually need a new parser?](#phase-0--preflight)
1. [Phase 1 — Get sample data and anonymize it](#phase-1--sample-data)
2. [Phase 2 — Verify your broker's P&L format (CRITICAL)](#phase-2--verify-pl-format)
3. [Phase 3 — Scaffold the parser package](#phase-3--scaffold-package)
4. [Phase 4 — Implement `detect()`](#phase-4--implement-detect)
5. [Phase 5 — Implement `parse_account_statement()`](#phase-5--account-statement)
6. [Phase 6 — Implement `parse_profit_and_loss()`](#phase-6--profit-and-loss)
7. [Phase 7 — Standardized output schema (the contract)](#phase-7--schema-contract)
8. [Phase 8 — Currency, ISIN, country code policy](#phase-8--currency-isin-country)
9. [Phase 9 — Add treaty rates if your broker covers new countries](#phase-9--treaty-rates)
10. [Phase 10 — Register the parser](#phase-10--register-parser)
11. [Phase 11 — Required tests](#phase-11--tests)
12. [Phase 12 — Manual verification on real data](#phase-12--manual-verification)
13. [Phase 13 — Document broker quirks](#phase-13--document-quirks)
14. [Phase 14 — PR checklist](#phase-14--pr-checklist)
15. [Common pitfalls (read before you start)](#common-pitfalls)
16. [Worked example — Interactive Brokers stub](#worked-example)

---

<a name="phase-0--preflight"></a>
## Phase 0 — Preflight: do you actually need a new parser?

Before you write a single line of code, answer these in writing (in the PR description):

| Question | Why it matters |
|---|---|
| What broker, what file format(s)? CSV / XLSX / PDF / JSON | XLSX/PDF need extra dependencies; PDFs are usually unreliable |
| Does the broker cover stocks, crypto, dividends, bonds, derivatives? | Bonds and derivatives are **not** in scope for revolut-pit — they go on PIT-36, not PIT-38 |
| What account type? Standard, IKE, IKZE, OIPE, professional? | Only **standard accounts** are in scope. IKE/IKZE/OIPE are tax-deferred and must NOT be put through this tool |
| What currencies appear? | Every currency must be ISO 4217 (3 uppercase letters) and resolvable via NBP Tabela A or B |
| What countries (ISIN prefixes) appear? | Each country must be in `dividends.TREATY_RATES` or fall back to the 15% default — unfamiliar countries need a manual treaty check |
| Is the user a Polish tax resident? Do they file PIT-38? | Tool is **only** for Polish PIT-38 filers (art. 3 ust. 1 PIT). Non-residents have different rules |

If any answer is "out of scope", stop here and document the limitation in [`docs/SAFETY.md`](SAFETY.md#known-limitations) instead of writing a half-correct parser.

---

<a name="phase-1--sample-data"></a>
## Phase 1 — Get sample data and anonymize it

You will need:

1. **At least one year of real export** from the broker. Two or more years
   is much better, because cross-year FIFO matching reveals format quirks.
2. **A test fixture** — anonymized CSV checked into `examples/sample_data/`.

### Anonymization rules

Before committing **any** sample data to the repo:

- Strip account numbers, full names, addresses, IBANs, tax IDs.
- Replace tickers with realistic-but-fake symbols (`AAPL`, `BA`, `BTC` are
  fine — they are public. Personal portfolio shape is what's sensitive).
- Round quantities and amounts so the totals don't match the user's real
  return.
- Keep the **format** (column names, separators, encoding, timezone strings,
  date formats) byte-for-byte identical to the broker's real export.

A good fixture is small (10–30 rows), covers edge cases (multi-lot,
multi-currency, fees, dividends, splits if applicable), and parses cleanly.

### Where to put it

```
examples/sample_data/<broker_slug>/
├── account_statement_2025.csv
├── profit_and_loss_2025.csv
├── crypto_account_statement_2025.csv      # if applicable
└── README.md                               # short description of the fixture
```

---

<a name="phase-2--verify-pl-format"></a>
## Phase 2 — Verify your broker's P&L format (CRITICAL)

This is the single most important step. **Get it wrong and the tool will
silently produce wrong tax numbers.**

### The question

> Does each row in the broker's "closed positions" / "P&L" / "realized
> gains" report represent ONE buy lot, or is it a SUM of multiple buy lots?

### Why it matters

Polish art. 11a ust. 2 ustawy o PIT requires that **costs in foreign
currency are converted to PLN using the NBP D-1 mid-rate from the day
before each cost was incurred** — per event, not per aggregate.

- **Per-lot format** (Revolut): the parser is straightforward. Each row's
  `date_acquired` carries the original buy date; pipeline applies the
  correct D-1 NBP rate per row. ✅ Compliant.
- **Aggregated format** (some brokers may emit one row per symbol with a
  single "weighted average cost basis" and the date of the *first* buy):
  the parser **cannot** simply use the row's `date_acquired` — it would
  apply one rate to costs incurred on different days. ❌ Violation.

### The decision procedure

Take a real export, pick **one symbol that you bought on three or more
different dates and then sold all at once**. Run this check:

```bash
grep ',YOUR_TICKER,' /path/to/profit_and_loss_2025.csv
```

**Pattern A — per-lot (good):**
```
2024-01-15,2025-06-01,YOUR_TICKER,...,5,500.00,650.00,150.00,USD
2024-03-20,2025-06-01,YOUR_TICKER,...,5,520.00,650.00,130.00,USD
2024-08-04,2025-06-01,YOUR_TICKER,...,5,540.00,650.00,110.00,USD
```
Three rows with three different `Date acquired` values, summing to the
total quantity sold. **You're good — go to Phase 3.**

**Pattern B — aggregated (bad):**
```
2024-01-15,2025-06-01,YOUR_TICKER,...,15,1560.00,1950.00,390.00,USD
```
One row, with `date_acquired` = the *earliest* buy date. **Stop. You
cannot trust this row's `cost_basis`.**

### What to do if your broker produces Pattern B

1. **Do not** route the parser through the same `pipeline.process_stocks`
   path as Revolut. The `cost_basis` × single D-1 rate path is not
   compliant for aggregated formats.
2. **You must** parse the broker's `account_statement` (raw buy/sell
   history), feed each BUY into [`TaxCalculator.add_buy()`](../src/revolut_pit/calculator.py),
   and call [`TaxCalculator.calculate_sell()`](../src/revolut_pit/calculator.py)
   for each SELL. The calculator computes per-lot D-1 internally.
3. Cross-validate the calculator's totals against the broker's aggregated
   P&L row (drift should be < 0.5%; if larger, **block** the run).
4. Add a regression test analogous to
   `tests/test_pipeline_e2e.py::test_revolut_pl_per_lot_uses_per_lot_d_minus_1_rate`
   that proves your parser produces *separate cost rates* per buy lot.

### Multi-year FIFO carry-over

If a sell in year N matches buy lots from year N−1, N−2, …, you need access
to the broker's account statements from those earlier years too. Either:

- **(a)** rely on the broker's pre-matched P&L (per-lot Pattern A above), or
- **(b)** require the user to provide statements from all relevant years
  and merge them before building FIFO.

Document the choice in `docs/BROKER-<NAME>.md`.

---

<a name="phase-3--scaffold-package"></a>
## Phase 3 — Scaffold the parser package

```bash
BROKER=interactive_brokers   # use snake_case
mkdir -p src/revolut_pit/parsers/$BROKER
touch src/revolut_pit/parsers/$BROKER/__init__.py
touch src/revolut_pit/parsers/$BROKER/stocks.py
touch src/revolut_pit/parsers/$BROKER/crypto.py    # only if broker supports crypto
```

Minimal `__init__.py`:

```python
"""Parsers for <Broker Name>."""
from .stocks import IBStocksParser
# from .crypto import IBCryptoParser   # uncomment if implemented

__all__ = ["IBStocksParser"]
```

---

<a name="phase-4--implement-detect"></a>
## Phase 4 — Implement `detect()`

[`auto_detect()`](../src/revolut_pit/parsers/__init__.py) calls every
registered parser's `detect()` until one returns `True`. Your `detect()`
must be:

- **Cheap** — only read the first ~1 KiB of the file. Don't `pd.read_csv`
  the whole thing.
- **Specific** — return `True` only for files that you can reliably parse.
  False positives will mis-route Revolut files to your parser.
- **Defensive** — wrap I/O in `try/except` and return `False` on any error.

### Recommended detection signals

Combine 2–3 of these for a unique fingerprint:

| Signal | Example |
|---|---|
| Filename pattern | Filename contains `IBKR_Activity_Statement` |
| Header row | First line contains `Statement,Header,Field Name,...` |
| A unique column name | `BrokerCommission`, `IB Cost Basis`, etc. |
| File-level metadata | "Interactive Brokers" string in the first ~200 bytes |

```python
def detect(self, filepath: Path) -> bool:
    name = filepath.name.lower()
    if "crypto" in name:           # IB doesn't do crypto: skip crypto files
        return False
    if not name.endswith(".csv"):
        return False
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            head = f.read(4096)
    except OSError:
        return False
    return "Interactive Brokers" in head and "Trades,Header" in head
```

---

<a name="phase-5--account-statement"></a>
## Phase 5 — Implement `parse_account_statement()`

Returns the raw stream of broker transactions, **standardized to the dict
shape declared in [`base.BrokerStockParser.parse_account_statement`](../src/revolut_pit/parsers/base.py#L43)**.

For stocks:

```python
{
    "date": datetime,            # tz-naive or tz-aware OK; pipeline normalizes
    "ticker": str,
    "type": str,                 # broker-specific verb; pipeline tolerates anything,
                                 # but standardize to BUY / SELL / DIVIDEND / FEE / etc.
                                 # so audit reports stay readable.
    "quantity": Decimal,
    "price_per_share": Decimal,
    "total_amount": Decimal,
    "currency": str,             # ISO 4217 — see Phase 8
    "fx_rate_revolut": Decimal,  # broker's FX rate, ignored by tax math (informational only)
}
```

### Mandatory rules

1. **Always return `Decimal`, never `float`.** Use [`parse_amount()`](../src/revolut_pit/parsers/_common.py)
   from `parsers/_common.py` — it strips `$`, `€`, `£`, `PLN`, commas, and
   handles `nan`/empty.
2. **Always use `pd.to_datetime`** for date parsing — handles timezone
   strings, ISO 8601, and the goofy formats brokers emit (`Jan 3, 2025,
   6:18:28 PM`).
3. **Don't drop rows you don't recognise.** Log a warning with row index
   (NOT the raw row content — that may contain PII; see Phase 11) and
   continue.
4. **Don't sanitize at the parser layer for reports.** Leave that to
   `reports._safe_cell` — it's centralized for a reason (CVE class:
   formula injection).

### Treating broker-specific transaction types

Map broker verbs to a small, stable vocabulary:

| Broker verb (any of) | Standardized `type` |
|---|---|
| BUY, BUY - MARKET, BUY - LIMIT, "B" | `BUY` |
| SELL, SELL - MARKET, SELL - LIMIT, SELL - STOP, "S" | `SELL` |
| DIVIDEND, DIV, "Cash Dividend" | `DIVIDEND` |
| FEE, COMMISSION, CUSTODY FEE, "Withholding Tax" | `FEE` |
| TRANSFER, INTERNAL TRANSFER, CASH TOP-UP | `TRANSFER` (ignored) |
| SPLIT, STOCK SPLIT | `SPLIT` (handle specially — see SAFETY.md) |

If your broker has types that don't map (e.g. corporate actions, options
assignments), **stop and check with maintainers** — those need PIT-36
treatment, not PIT-38.

---

<a name="phase-6--profit-and-loss"></a>
## Phase 6 — Implement `parse_profit_and_loss()`

Returns `(sells, other_income)` per
[`base.BrokerStockParser.parse_profit_and_loss`](../src/revolut_pit/parsers/base.py#L68).

### `sells` schema

```python
{
    "date_acquired": datetime,    # day the lot was bought
    "date_sold": datetime,        # day this lot was sold
    "symbol": str,                # ticker
    "security_name": str,         # full name, for reports
    "isin": str,                  # 12-char ISIN, optional but strongly recommended
    "country": str,               # ISO 3166-1 alpha-2 if broker provides it; else ""
    "quantity": Decimal,          # shares of THIS lot sold
    "cost_basis": Decimal,        # cost in original currency, FOR THIS LOT only
    "gross_proceeds": Decimal,    # proceeds in original currency, FOR THIS LOT only
    "gross_pnl": Decimal,         # broker's pre-computed P&L, used as a sanity check
    "currency": str,              # ISO 4217
}
```

**Recall Phase 2:** if your broker emits aggregated rows, `cost_basis` and
`date_acquired` here will not be per-lot. **Do not** route them through the
default pipeline path; build FIFO via `TaxCalculator` and use this output
only for cross-validation.

### `other_income` schema (dividends, interest, fees, withholding)

```python
{
    "date": datetime,             # day the income was received
    "symbol": str,                # ticker that paid the dividend (or empty for cash)
    "security_name": str,
    "isin": str,
    "country": str,
    "gross_amount": Decimal,      # gross dividend BEFORE foreign withholding
    "withholding_tax": Decimal,   # tax already withheld by the foreign payer
    "net_amount": Decimal,        # what actually landed in the account
    "currency": str,              # ISO 4217 — if the broker pre-converts to PLN, see below
}
```

### Bullet 8 from REVIEW-LEGAL — PLN-denominated dividends

If your broker pre-converts foreign dividends to PLN at its own FX rate
(Revolut does this in newer exports), you have two options:

1. **Preferred:** parse the *original* foreign-currency amount (some
   brokers keep both fields in the export — read the documentation).
   Pipeline will apply NBP D-1 correctly via `_get_rate(currency, date)`.
2. **Acceptable with warning:** trust the broker's PLN value and emit a
   per-row warning. The drift between broker FX and NBP D-1 is typically
   0.5–1.5%, which can shift the dividend tax by a similar percentage.
   See [`pipeline.process_stocks`](../src/revolut_pit/pipeline.py) lines
   handling `currency == "PLN"`.

If your broker does **not** support option 1 and the user has > 5000 PLN of
PLN-converted dividends per year, recommend they obtain a per-event report
from the broker (in PL, this is "raport historyczny w walucie nabycia").

---

<a name="phase-7--schema-contract"></a>
## Phase 7 — Standardized output schema (the contract)

The pipeline expects exact field names and types. This is a hard contract.

### Stocks — every key is required

| Key | Type | Notes |
|---|---|---|
| `date` (account stmt) / `date_acquired`+`date_sold` (P&L) | `datetime` | tz-naive UTC or tz-aware; pipeline normalizes |
| `ticker` / `symbol` | `str` | non-empty |
| `quantity` | `Decimal` | positive |
| `cost_basis` / `gross_proceeds` | `Decimal` | always positive in original currency |
| `currency` | `str` | **must** match `^[A-Z]{3}$` — `nbp.get_rate` rejects anything else |
| `isin` | `str` | 12 chars, may be `""` if broker doesn't supply |
| `country` | `str` | 2-letter; pipeline falls back to `isin[:2]` if empty |

### Crypto — every key is required

| Key | Type | Notes |
|---|---|---|
| `date` | `datetime` | with second-level precision if available (used by swap detection) |
| `symbol` | `str` | uppercase ticker (`BTC`, `ETH`) |
| `type` | `str` | one of `Buy`, `Sell`, `Stake`, `Staking reward`, `Receive`, `Send` (case-insensitive checks done in `_detect_swaps`) |
| `quantity` / `price` / `value` / `fees` | `Decimal` | all in the broker's reporting fiat |
| `value_currency` | `str` | ISO 4217 |
| `is_swap` | `bool` | leave `False`; the parser's `_detect_swaps()` populates this |

### Type enforcement

Add a smoke-test that asserts every dict your parser returns matches the
schema:

```python
def test_schema_compliance(parser):
    txs = parser.parse_account_statement(SAMPLE)
    REQUIRED = {"date", "ticker", "type", "quantity", "price_per_share",
                "total_amount", "currency"}
    for tx in txs:
        assert REQUIRED <= set(tx.keys())
        assert isinstance(tx["quantity"], Decimal)
        assert isinstance(tx["currency"], str) and len(tx["currency"]) == 3
```

---

<a name="phase-8--currency-isin-country"></a>
## Phase 8 — Currency, ISIN, country code policy

### Currency must be ISO 4217

[`nbp.get_rate`](../src/revolut_pit/nbp.py) **raises `ValueError`** unless
currency matches `^[A-Z]{3}$`. This is intentional — it closes a path-
injection vector against the NBP API and keeps the cache key well-formed.

If your broker emits currency as `"$"`, `"USD$"`, `"usd"`, normalize in the
parser with [`parse_amount_with_currency()`](../src/revolut_pit/parsers/_common.py)
or your own mapping.

### ISIN

ISIN is 12 characters: 2 country letters + 9 alphanumerics + 1 check digit.
If your broker doesn't include ISIN, the pipeline falls back to symbol-only
country detection — much weaker. Strongly prefer brokers that export ISIN.

### Country code

Two-letter ISO 3166-1 alpha-2. Important caveats from the audit:

- **ISIN prefix ≠ source country of dividend** in many cases. An IE-domiciled
  ETF holding US stocks pays an *Irish-source* dividend (treaty PL-IE
  applies, not PL-US). The current pipeline uses the ISIN prefix as a
  heuristic and accepts that limitation.
- **Don't fall back to "US"** if country detection fails. The pipeline
  currently does this in `process_stocks` (legacy behavior); for new
  parsers, return `"XX"` or `""` and let downstream code emit a warning
  rather than guessing.

---

<a name="phase-9--treaty-rates"></a>
## Phase 9 — Add treaty rates if your broker covers new countries

[`dividends.TREATY_RATES`](../src/revolut_pit/dividends.py) currently
contains only `US`, `DE`, `NL`, `GB`. Anything else falls back to 15%.

If your broker exposes you to new countries, **verify the treaty rate
yourself** before adding. Sources:

- The treaty text on isap.sejm.gov.pl (search for "umowa z [country]")
- The Multilateral Instrument (MLI) modifications, if applicable
- The Ministerstwo Finansów's tax treaty list:
  https://www.gov.pl/web/finanse/wykaz-umow-o-unikaniu-podwojnego-opodatkowania

Add the rate:

```python
TREATY_RATES = {
    "US": Decimal("0.15"),
    "DE": Decimal("0.15"),
    "NL": Decimal("0.15"),
    "GB": Decimal("0.10"),
    "IE": Decimal("0.15"),   # NEW — verify against PL-IE treaty Art. 10
    # always cite the treaty article and Dziennik Ustaw reference in the commit message
}
```

**Do not** silently add a rate without citing the treaty article. The
maintainer will block the PR.

---

<a name="phase-10--register-parser"></a>
## Phase 10 — Register the parser

Edit [`src/revolut_pit/parsers/__init__.py`](../src/revolut_pit/parsers/__init__.py):

```python
from .interactive_brokers.stocks import IBStocksParser
# from .interactive_brokers.crypto import IBCryptoParser  # if applicable

_PARSER_REGISTRY: List[Type[BrokerParser]] = [
    RevolutStocksParser,
    RevolutCryptoParser,
    IBStocksParser,                # ADD HERE
    # IBCryptoParser,
]
```

Run:

```bash
python -c "from revolut_pit.parsers import list_parsers; print([p.__name__ for p in list_parsers()])"
```

You should see `IBStocksParser` in the output.

---

<a name="phase-11--tests"></a>
## Phase 11 — Required tests

Place tests under `tests/test_<broker>_parser.py`. **The PR will be
blocked** without these categories:

### 11.1 Detection tests

```python
def test_detect_positive(parser):
    """detect() returns True for a real fixture."""
    fixture = Path("examples/sample_data/ib/account_statement_2025.csv")
    assert parser.detect(fixture)

def test_detect_negative_revolut_file(parser):
    """detect() returns False for Revolut files (no cross-routing)."""
    fixture = Path("examples/sample_data/revolut/account_statement_2025.csv")
    assert not parser.detect(fixture)

def test_detect_negative_garbage(parser, tmp_path):
    """detect() returns False on random garbage, not crash."""
    p = tmp_path / "garbage.csv"
    p.write_bytes(b"\x00\x01\x02not,a,csv")
    assert not parser.detect(p)
```

### 11.2 Schema tests

```python
def test_account_statement_schema(parser, fixture):
    txs = parser.parse_account_statement(fixture)
    REQUIRED = {"date", "ticker", "type", "quantity", "price_per_share",
                "total_amount", "currency"}
    for tx in txs:
        assert REQUIRED <= set(tx.keys()), f"missing keys: {REQUIRED - tx.keys()}"
        assert isinstance(tx["quantity"], Decimal)
        assert re.match(r"^[A-Z]{3}$", tx["currency"])
```

### 11.3 Per-lot regression (Phase 2 outcome)

```python
def test_pl_is_per_lot_or_calculator_used(parser, fixture):
    """If your broker emits per-lot rows, prove it; else prove TaxCalculator
    is used to rebuild FIFO."""
    sells, _ = parser.parse_profit_and_loss(fixture)
    # If per-lot:
    by_symbol = {}
    for s in sells:
        by_symbol.setdefault(s["symbol"], set()).add(s["date_acquired"])
    multi_lot_symbols = [s for s, dates in by_symbol.items() if len(dates) > 1]
    assert multi_lot_symbols, (
        "fixture has no multi-lot symbol; either fix the fixture or, if "
        "your broker aggregates, write the calculator-based test instead."
    )
```

### 11.4 Decimal precision (no float leaks)

```python
def test_no_float_leak(parser, fixture):
    txs = parser.parse_account_statement(fixture)
    for tx in txs:
        for k in ("quantity", "price_per_share", "total_amount"):
            assert isinstance(tx[k], Decimal), f"{k} is {type(tx[k]).__name__}"
```

### 11.5 Malformed input resilience

```python
def test_empty_csv(parser, tmp_path):
    p = tmp_path / "empty.csv"
    p.write_text("")
    # Must not raise; either return [] or skip cleanly.
    assert parser.parse_account_statement(p) == []

def test_extra_columns_ignored(parser, tmp_path):
    """Adding a column the parser doesn't know about must not break parsing."""
    # Take a real fixture, add an extra column, re-parse.
```

### 11.6 Run the full test suite

```bash
python -m pytest tests/ -v
```

All previously green tests must still pass. Expect ~90+ tests for the core
parsers; your new parser typically adds 8–15 more.

---

<a name="phase-12--manual-verification"></a>
## Phase 12 — Manual verification on real data

**Automated tests are necessary but not sufficient.** Before you submit a
PR, do this with your own real export:

1. Run the pipeline:
   ```bash
   python -m revolut_pit.cli calc \
       --year 2025 \
       --data-dir /path/to/your/real/data \
       --output-dir /tmp/pit38_out
   ```
2. Open `/tmp/pit38_out/pit38_2025.xlsx`.
3. Pick **3 random rows** from the Stocks sheet. For each:
   - Look up the buy date and sell date in the broker's source CSV.
   - Open the NBP API URL from the audit trail in your browser. Verify
     `mid` field matches the rate the report shows.
   - Hand-calculate `cost_basis × cost_rate` and `proceeds × sell_rate`.
   - Compare to the report's `cost_basis_pln` and `proceeds_pln`.
   - **They must match within ±0.01 PLN** (rounding tolerance).
4. Pick **1 dividend row**. Verify the WHT credit logic by hand:
   `min(wht_paid, gross × treaty_rate)`.
5. Check the warnings list. **Read every warning.** Anything you don't
   understand is a sign your parser is wrong, not the warning.
6. Cross-check the Polish PIT-38 form fields with what your accountant
   would expect, **before** filing.

Document this manual verification in the PR description ("Tested on N=37
closed positions across years 2021–2025; spot-checked 4; no drift > 0.01
PLN.").

---

<a name="phase-13--document-quirks"></a>
## Phase 13 — Document broker quirks

Create `docs/BROKER-<NAME>.md`. Required sections:

```markdown
# <Broker Name> Parser

## Tested with
- export type: Activity Statement (CSV) / Tax Report (CSV) / etc.
- years validated: 2023, 2024, 2025
- account types: standard cash account (NOT IKE/IKZE — out of scope)

## CSV format

### account_statement
- delimiter: `,` / `;` / `\t`
- encoding: UTF-8 / Windows-1250
- date format: `YYYY-MM-DD HH:MM:SS UTC` / etc.
- column names: ...

### profit_and_loss
- per-lot or aggregated? **per-lot, verified 2026-04-XX**
- FIFO method used? broker-side: yes/no
- partial sells split proportionally? yes/no

## Known quirks

- The export uses `;` as separator on Windows but `,` on macOS — handled.
- `Cost basis` includes commissions but excludes financing costs — see line ...
- Crypto is NOT supported; broker doesn't expose it.

## Currencies and countries seen
- USD, EUR, GBP, CHF
- US, DE, NL, GB, IE, CH (CH treaty rate added in dividends.py)

## How to export
1. Log in
2. Click ...
3. Settings ...
4. Save as CSV (NOT XLSX)

## Limitations
- Margin trading: not supported (out of scope for PIT-38)
- Options: not supported (PIT-36 instrument)
- Bonds: not supported
```

---

<a name="phase-14--pr-checklist"></a>
## Phase 14 — PR checklist

Copy this into your PR description:

```markdown
## Broker
- [ ] Broker name and URL: ___
- [ ] Account type: standard cash / NOT IKE/IKZE/professional
- [ ] Years tested: 20__ – 20__
- [ ] Real export rows tested: ~___

## Format verification (Phase 2)
- [ ] P&L is **per-lot** / **aggregated** (delete one)
- [ ] If aggregated: parser routes through `TaxCalculator` with per-lot D-1
- [ ] Cross-validation drift vs broker totals: ___% (must be < 0.5%)

## Implementation
- [ ] `detect()` is cheap and specific (does not false-positive on Revolut files)
- [ ] All amounts are `Decimal`, no `float`
- [ ] All currencies are ISO 4217 (`^[A-Z]{3}$`)
- [ ] Strings flowing into reports are unaltered (sanitization happens centrally)
- [ ] No `print()` of raw CSV row content (PII leak)
- [ ] No `os.system`, `subprocess.run(shell=True)`, `eval`, `exec`

## Treaty rates
- [ ] No new country codes, OR
- [ ] New countries added with treaty article + Dziennik Ustaw reference

## Tests
- [ ] Detection: positive + negative + garbage (Phase 11.1)
- [ ] Schema compliance (Phase 11.2)
- [ ] Per-lot regression (Phase 11.3)
- [ ] Decimal precision (Phase 11.4)
- [ ] Empty CSV / malformed input (Phase 11.5)
- [ ] All 90+ previously green tests still pass

## Manual verification (Phase 12)
- [ ] Spot-checked at least 3 closed positions against NBP API
- [ ] Spot-checked at least 1 dividend
- [ ] Warnings list reviewed; nothing unexplained

## Documentation
- [ ] `docs/BROKER-<NAME>.md` created
- [ ] `docs/SAFETY.md` updated if new limitations
- [ ] `docs/TAX-LOGIC.md` updated if new treaty rate or special handling

## Sample data
- [ ] Anonymized fixture in `examples/sample_data/<broker>/`
- [ ] Fixture covers multi-lot, multi-currency, dividend
- [ ] No real account numbers, names, or amounts in fixture
```

---

<a name="common-pitfalls"></a>
## Common pitfalls (read before you start)

These are the mistakes that have shown up most often in the audit trail.

### 1. Trusting the broker's pre-converted PLN values
Brokers often pre-convert foreign dividends/proceeds to PLN at *their own*
FX rate. NBP D-1 differs by 0.5–1.5%. Either parse the original-currency
fields (preferred) or warn the user.

### 2. Aggregating multi-lot rows in P&L
See Phase 2. **The single most consequential mistake.** A parser that
treats an aggregated row as if it were a single buy lot will silently
emit a wrong PIT-38.

### 3. Falling back to `country = "US"` on unknown ISINs
Bites you whenever the broker ever lists a non-US security. Use `"XX"`
or `""` and let the warning channel surface it.

### 4. Letting the broker's `FX Rate` column influence tax math
Broker FX rates are **not** Polish-tax-compliant. NBP Tabela A D-1 is.
Parse the broker rate as `fx_rate_revolut` (informational) and never use
it in the calculator.

### 5. Importing `pytz` / `arrow` / `dateutil` for date parsing
`pd.to_datetime` handles every format brokers emit. Adding a date library
is dependency bloat that has historically broken on Python upgrades.

### 6. Logging the raw row in `except` handlers
```python
# WRONG
print(f"Could not parse: {row}")
# RIGHT
print(f"Could not parse row {idx}: {type(e).__name__}")
```
The first form leaks PII to stdout (which may be captured by systemd, log
aggregators, etc.). The second is safe.

### 7. Reading the entire CSV with `pd.read_csv` in `detect()`
`detect()` runs for every file the user uploads, against every registered
parser. A 200 MB file × 5 parsers = 1 GB of pointless allocations. Read
the first 4096 bytes and pattern-match.

### 8. Adding a new dependency without justification
Every dep is a CVE surface. The audit already pinned `reportlab>=3.6.13`
because of CVE-2023-33733. Don't add `xlrd`, `tablib`, `pdfplumber`,
`tabula-py` etc. unless you've documented why `pandas` + `openpyxl` can't
do it.

### 9. Skipping `is_swap` detection for crypto
Polish art. 17 ust. 1 pkt 11 PIT exempts crypto-to-crypto exchanges. If
your broker exposes them as separate Sell+Buy rows, you must implement
swap detection. Copy the patterns from
[`parsers/revolut/crypto.py:_detect_swaps`](../src/revolut_pit/parsers/revolut/crypto.py)
— window-based matching, value-equality with tolerance, different-symbol
requirement.

### 10. Forgetting that PIT-38 covers calendar years, not broker fiscal years
If your broker's "Activity Statement" runs Apr–Mar, you must filter to
calendar Jan 1 – Dec 31 of the requested tax year. Pipeline assumes
calendar year.

---

<a name="worked-example"></a>
## Worked example — Interactive Brokers stub

A minimal stub showing the Phase 3–4 scaffold:

```python
# src/revolut_pit/parsers/interactive_brokers/stocks.py
"""Parser for Interactive Brokers Activity Statement CSVs."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

from .._common import parse_amount, parse_amount_with_currency
from ..base import BrokerStockParser


class IBStocksParser(BrokerStockParser):
    """Parse Interactive Brokers Activity Statement and Tax Report CSVs.

    IB emits "Trades" and "Closed Positions" sections in the same CSV with
    a `Statement,Header,Field Name,...` header marker per section.
    Verified per-lot in 2026-04 against three years of real exports.
    """

    @property
    def name(self) -> str:
        return "Interactive Brokers"

    @property
    def version(self) -> str:
        return "0.1.0"

    def __init__(self, year: int):
        self.year = year

    def detect(self, filepath: Path) -> bool:
        if filepath.suffix.lower() != ".csv":
            return False
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                head = f.read(4096)
        except OSError:
            return False
        return "Interactive Brokers" in head and ",Statement,Header," in head

    def parse_account_statement(self, filepath: Path) -> List[Dict]:
        # IB's "Trades" section. Implementation left as exercise — follow
        # Phase 5 schema rules. Use parse_amount() for every numeric field.
        raise NotImplementedError

    def parse_profit_and_loss(self, filepath: Path) -> Tuple[List[Dict], List[Dict]]:
        # IB's "Closed Positions" + "Dividends" sections. Implementation
        # left as exercise — follow Phase 6 schema rules.
        raise NotImplementedError
```

Once `parse_*` methods are real and tests in Phase 11 are green, register
in `parsers/__init__.py` per Phase 10 and submit the PR per Phase 14.

---

## Help and questions

- **Architecture or interface questions:** open a GitHub issue with the
  `parser` label.
- **Tax-treatment questions** (treaty rates, REIT distributions, return of
  capital, staking rewards): consult a Polish tax advisor first; the
  maintainers do not provide tax advice.
- **Broker quirks** (specific column meanings, edge cases in their export):
  best to ask the broker's support and post your finding in the PR
  description for future contributors.

---

**Goal:** any Polish PIT-38 filer using any broker can generate a correct
declaration with revolut-pit. Each new broker that lands compliantly is
one fewer person filing by hand.
