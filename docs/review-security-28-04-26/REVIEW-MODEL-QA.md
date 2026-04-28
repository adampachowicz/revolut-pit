# Model QA Report — revolut-pit (PIT-38 calculator)

**Data:** 2026-04-28

## POTWIERDZONE BŁĘDY (z reproducerem)

### Bug #1: ❌ FALSE POSITIVE — Revolut emituje per-lot wiersze P&L
- **Lokalizacja:** `src/revolut_pit/pipeline.py:113-122`
- **Pierwotna hipoteza:** Revolut P&L agreguje wiele lotów do jednego wiersza, pipeline aplikuje jeden kurs D-1 do całości.
- **Weryfikacja na realnych danych (`data/2020`–`data/2025`):** **Pierwotna hipoteza była błędna.** Revolut "Income from Sells" emituje **per-lot match** — np. Boeing sprzedany 2025-05-13 ma 11 osobnych wierszy P&L z różnymi `date_acquired` (od 2020-08-11 do 2021-05-13). Pojedynczy lot rozsmarowany na dwie sprzedaże (np. 2021-05-14 BA → 2025-05-13 + 2025-10-02) jest dzielony proporcjonalnie. Pipeline `_get_rate(currency, s["date_acquired"])` per wiersz = **per-lot D-1**.
- **Severity:** ✅ NOT A BUG dla Revoluta. Pełna analiza: [`BUG-3-PER-LOT-FIFO-PLAN.md`](BUG-3-PER-LOT-FIFO-PLAN.md).
- **Caveat:** `TaxCalculator` w `calculator.py` pozostaje przydatny dla brokerów, którzy w przyszłości okażą się agregatorami (eToro, IB). Wymóg dla nowych parserów: zweryfikować format P&L przed mergem.

### Bug #2: Strata bieżącego roku jest "zerowana" i znika z wyników — brak raportu carry-forward
- **Lokalizacja:** `src/revolut_pit/pit38.py:155` (`"dochod_pln": max(Decimal(0), dochod)`), brak nigdzie eksportu pola `loss_to_carry`/`strata_biezacego_roku`.
- **Dowód:**
  - Stocks: proceeds = 50 000, koszt = 60 000 → dochod = -10 000.
  - **Tool:** `czesc_C.dochod_pln = 0`, `dochod_razem = 0`, `podatek = 0`. Nigdzie NIE pojawia się `10 000` jako "strata do przeniesienia".
- **Severity:** **HIGH** — `docs/SAFETY.md` deklaruje "Loss Carry-Forward: Correctly implements 5-year limit". Aktualny kod implementuje wyłącznie *zużycie* przekazanej straty, nie *generowanie* jej.

### Bug #3: Mieszanie strat części C (papiery) z dochodem części E (krypto) w `prior_year_loss`
- **Lokalizacja:** `src/revolut_pit/pit38.py:77`, `pit38.py:83-89`
- **Dowód:**
  - Część C: dochod = 100 000 PLN. Część E: dochod = 0. Prior_year_loss z **kryptowalut** = 50 000 PLN.
  - **Tool:** `capital_gains_income = 100 000`. Strata 50 000 odejmowana → 50 000. Podatek = **9 500**.
  - **Poprawnie:** strata krypto może odliczyć się TYLKO od dochodu krypto. Podatek powinien wynosić **19 000 PLN**, strata krypto przechodzi dalej.
  - **Różnica:** **9 500 PLN zaniżonego podatku** + nielegalna konsumpcja straty krypto.
- **Severity:** **CRITICAL**.

### Bug #4: `dochod_razem` mylnie dodaje GROSS dywidend
- **Lokalizacja:** `src/revolut_pit/pit38.py:109` `dochod_razem = capital_gains_income + czesc_d["przychod_pln"]`.
- **Dowód:**
  - C = 1000 PLN dochód, E = 0, D = 5000 PLN gross. **Tool:** `dochod_razem = 6000`. Powinno być 1000.
- **Severity:** **MEDIUM** — display only; `podatek_do_zaplaty` nie używa `dochod_razem`.

### Bug #5: Brak Wigilii (24 grudnia) w POLISH_FIXED_HOLIDAYS dla 2025
- **Lokalizacja:** `src/revolut_pit/nbp.py:22-32`.
- **Dowód:** Transakcja 2025-12-29 → D-1 cofa się przez weekend i święta do 12-24 (środa, brak w holidays). Tool zapyta API NBP o kurs z 12-24, dostanie 404, fallback przez `MAX_RETRIES=7` ratuje. Cache zapisze kurs pod **kluczem 2025-12-24** którego nie ma.
- **Severity:** **LOW** kwotowo, **MEDIUM** dla audit trail.

### Bug #6: Detekcja swapów krypto — fragile O(N) sprawdza tylko `i+1`
- **Lokalizacja:** `src/revolut_pit/parsers/revolut/crypto.py:121-148`.
- **False negatives:**
  1. Buy przed Sell — pętla pomija Buy.
  2. Wstawiony Fee/Stake między Sell a Buy — `i+1` to nie Buy.
  3. Quantity różni się o rounding.
  4. Timestamp różni się o sekundy.
- **False positives (CRITICAL):**
  5. Sprzedaż 1.5 BTC za fiat + zakup 1.5 ETH za fiat → wykryte jako swap, **legalna sprzedaż BTC zniknie** z PIT.
  6. **`pipeline.py:213` `swap_keys.add((tx["symbol"], tx["date"].date()))`** — jeśli tego samego dnia jest swap BTC→ETH **i** sprzedaż BTC za fiat, to `(BTC, 2025-06-01)` w `swap_keys` wykluczy także **legalną sprzedaż za fiat**.
- **Severity:** **CRITICAL** — przypadki #5 i #6 prowadzą do uniknięcia opodatkowania (kara KKS).

### Bug #7: Martwy/odwrócony kod heurystyki swapa w pipeline
- **Lokalizacja:** `src/revolut_pit/pipeline.py:236-238`.
- Warunek `(date_acq - date_sold).days < 365` jest semantycznie odwrócony.
- **Severity:** **LOW** (martwy kod).

### Bug #8: PLN dywidendy obchodzą kurs NBP
- **Lokalizacja:** `src/revolut_pit/pipeline.py:152-156`
- **Dowód:** Pole `gross_amount` w PLN jest wynikiem `gross_USD × revolut_FX`. Tool przyjmuje to jako `gross_pln` bez ponownego przeliczenia po NBP. Spread Revolut vs NBP ≈ 0.5-1%.
- **Severity:** **MEDIUM**.

## PRAWDOPODOBNE BŁĘDY (wymagają testu)

### Issue #9: WHT > gross_pln nie generuje twardego błędu
- **Lokalizacja:** `src/revolut_pit/dividends.py:53-58`.

### Issue #10: Brak walidacji `date_acquired <= date_sold`
- **Lokalizacja:** `src/revolut_pit/pipeline.py:114-122` i 226-249.

### Issue #11: `_get_rate` w pipeline.py nie używa cache klucza wspólnego z calculatorem
- **Lokalizacja:** `pipeline.py:66-80`.

### Issue #12: Tax = `dochod × 0.19` bez zaokrąglenia do pełnych złotych
- **Lokalizacja:** `pit38.py:113`.
- Polskie prawo (Ord. Podatkowa art. 63 § 1) wymaga zaokrąglenia podstawy do pełnych złotych.

## EDGE CASES NIETESTOWANE

W `tests/test_pit38.py` brakuje:
- Strata bieżąca C lub E (Bug #2 nie wykryty).
- Mieszanie strat C+E z prior_loss z innego źródła (Bug #3 nie wykryty).
- Negative `dochod_razem`.
- Strata C dodatnia, ale E ujemna.

W `tests/test_calculator.py` brakuje:
- Sell exact = qty lotu.
- Cost_per_unit = 0 (airdrop, referral bonus).
- Multi-currency w jednym FIFO.
- Buy 0 / Sell 0.
- Negative quantity.

W `tests/test_pipeline_e2e.py` brakuje:
- Test właściwej hipotezy Bug #1.
- Test detekcji swapa krypto z różnymi kolejnościami.
- Test Wigilii 2025.
- Test pełnego flow z `prior_year_loss` rozdzielonym C/E.

## ZWERYFIKOWANE POPRAWNIE

- **`TaxCalculator` (calculator.py)**: FIFO logika, podział lotów, per-lot D-1 jest **poprawnie zaimplementowane**. Problem: pipeline tego nie wywołuje dla akcji.
- **`Decimal` precision**: brak `float`, `parse_amount` zwraca `Decimal`.
- **Rounding `round_grosz`**: `ROUND_HALF_UP` zgodnie z art. 63 § 1 OP, na groszach.
- **`_is_business_day`**: poprawnie wyklucza Easter Monday 2025.
- **NBP fallback `MAX_RETRIES=7`**.
- **Treaty cap dla dywidend**: matematyka `min(wht, gross × treaty)` poprawna.
- **5M PLN cap dla `prior_year_loss`** w pojedynczym roku.

## REKOMENDACJE TESTÓW DO DODANIA

1. **Test multi-lot stocks per-lot D-1 vs Revolut zagregowany P&L** — wykryje Bug #1.
2. **Test straty bieżącego roku** — wykryje Bug #2.
3. **Test rozdzielenia źródeł `prior_year_loss`** (`prior_year_loss_c` i `prior_year_loss_e` osobno) — wykryje Bug #3.
4. **Test `dochod_razem` poprawnie wyklucza dywidendy** — wykryje Bug #4.
5. **Test Wigilii 2025** — wykryje Bug #5.
6. **Testy detekcji swapów krypto** — 6 scenariuszy — wykryje Bug #6.
7. **Test odwrócenia `date_acquired > date_sold`** — wykryje Issue #10.
8. **Test PLN-denominowanej dywidendy** — wykryje Bug #8.
9. **Test zaokrąglenia podstawy do pełnych złotych** — wykryje Issue #12.
10. **Test FIFO `cost_per_unit=0`** — airdrop / Revolut referral.

## Pliki analizowane

- `src/revolut_pit/calculator.py`
- `src/revolut_pit/pit38.py`
- `src/revolut_pit/pipeline.py`
- `src/revolut_pit/dividends.py`
- `src/revolut_pit/nbp.py`
- `src/revolut_pit/parsers/revolut/stocks.py`
- `src/revolut_pit/parsers/revolut/crypto.py`
- `src/revolut_pit/parsers/stocks.py`
- `tests/test_pit38.py`
- `tests/test_calculator.py`
- `tests/test_pipeline_e2e.py`
- `docs/HOW-IT-WORKS.md`
- `docs/SAFETY.md`

**Najpilniejsze do naprawy:** Bug #1 (CRITICAL kwotowy), Bug #3 (CRITICAL legalny), Bug #6 (CRITICAL — false positive swapów wyklucza opodatkowane sprzedaże).
