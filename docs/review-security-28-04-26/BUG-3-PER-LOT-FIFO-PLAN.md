# Bug #4 (LEGAL) / Bug #1 (MODEL-QA) — STATUS: FALSE POSITIVE

**Resolution date:** 2026-04-28 (same day as audit, after empirical verification)
**Status:** ❌ **NIE JEST BUGIEM** dla danych z Revoluta. Hipoteza audytu była spekulatywna.

## Co twierdziły audyty

[`REVIEW-LEGAL.md` #4](REVIEW-LEGAL.md#4-agregacja-kosztu-z-różnych-dni-nabycia-i-przeliczanie-jednym-kursem-d-1--naruszenie-art-11a-ust-2-pit) i [`REVIEW-MODEL-QA.md` Bug #1](REVIEW-MODEL-QA.md#bug-1-pipeline-nie-używa-taxcalculator-dla-akcji--przelicza-koszt-jednym-kursem-d-1-dla-date_acquired-zwróconym-przez-revolut-pl) postawiły hipotezę:

> Revolut P&L agreguje wiele lotów kupna do jednego wiersza z `date_acquired = data najwcześniejszego lotu`. Pipeline przelicza całość jednym kursem D-1, naruszając art. 11a ust. 2 PIT.

Hipoteza była opatrzona zastrzeżeniem _"do potwierdzenia na realnym CSV"_.

## Co pokazują realne dane

Po sprawdzeniu eksportów z [`data/2020/`](../../data/2020/) – [`data/2025/`](../../data/2025/):

**Revolut emituje JEDNĄ LINIĘ NA LOT.** Sekcja "Income from Sells" w `profit_and_loss_statment_YYYY.csv` zawiera per-lot match — Revolut wewnętrznie prowadzi FIFO i eksportuje każde dopasowanie sprzedaży do lotu kupna jako osobny wiersz.

### Dowód 1: Boeing 2020 → 2025 — 11 osobnych wierszy z różnymi `date_acquired`

```csv
2020-08-11,2025-05-13,BA,...,0.27,50.28,54.00,3.72,USD
2020-10-06,2025-05-13,BA,...,0.57471264,100.00,114.94,14.94,USD
2020-11-04,2025-05-13,BA,...,0.33670033,52.00,67.34,15.34,USD
2020-11-06,2025-05-13,BA,...,0.30691421,47.94,61.38,13.44,USD
2020-11-09,2025-05-13,BA,...,0.27411053,49.00,54.82,5.82,USD
... (kolejne 6 lotów)
```

Każdy wiersz dostaje swój własny kurs NBP D-1 dla swojego `date_acquired` w `pipeline._get_rate()` — **per-lot per art. 11a ust. 2 PIT**.

### Dowód 2: jeden lot sprzedany w dwóch transakcjach

```csv
2021-05-14,2025-05-13,BA,...,0.94576924,214.80,189.17,-25.63,USD
2021-05-14,2025-10-02,BA,...,0.08012015,18.20,17.39,-0.81,USD
```

Lot kupiony 2021-05-14 podzielony na dwie sprzedaże (maj i październik 2025) — Revolut proporcjonalnie rozdziela `cost_basis` (214.80 + 18.20 = 233.00). Pipeline poprawnie stosuje **dwa kursy sell-rate** (dla 2025-05-13 i 2025-10-02) oraz **jeden kurs cost-rate** (dla 2021-05-14) — zgodnie z prawem.

### Dowód 3: dopasowanie account_statement → P&L

```
account_statement (BUY): 2025-02-11 AMD qty=4.3023768
P&L (rows with date_acquired=2025-02-11):
  - qty=0.98287499, cost=107.10 (sold 2025-10-01)
  - qty=3.31950181, cost=361.73 (sold 2025-11-03)
  Σ qty = 4.3023768 ✓
```

Jeden BUY rozsmarowany na dwa wiersze P&L o tym samym `date_acquired` — pipeline aplikuje ten sam kurs cost-rate dla obu, każdy ma własny sell-rate.

## Wniosek

Pipeline `process_stocks()` w obecnej formie **jest zgodny z art. 11a ust. 2 PIT** dla danych Revoluta. Audyty były spekulatywne i opierały się na założeniu, którego rzeczywistość nie potwierdza.

## Co zrobiono

- W commicie `9eaab36` dodano 180-day warning jako mitygację — **wycofany** w follow-up commicie po weryfikacji formatu.
- `calculator.py` (TaxCalculator) pozostaje dostępny dla brokerów, którzy faktycznie agregują loty (np. eToro w niektórych eksportach) — przyszli kontrybutorzy parserów dla innych brokerów MUSZĄ zweryfikować format swojego brokera przed pisaniem parsera.

## Co warto dodać (osobno, niski priorytet)

1. Test e2e weryfikujący że dla wielo-lotowych pozycji w realnych danych, pipeline aplikuje per-lot kursy D-1.
2. W [`docs/ADD-BROKER.md`](../ADD-BROKER.md) dopisać sekcję "Verify your broker's P&L format: per-lot or aggregated?".
3. Wskaźnik integralności w `audit.py`: jeśli inny broker ma single-row-per-symbol z wieloma `date_acquired` zlepianymi w jeden, ostrzec.
