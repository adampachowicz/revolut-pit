# Bug #3 — Plan refaktoryzacji: per-lot FIFO + per-lot kursy NBP D-1 dla akcji

**Status:** Nie zaimplementowane w branchu `fix/critical-pit38-bugs` — wymaga osobnego PR ze względu na zakres i potrzebę walidacji formatu CSV Revoluta.

## Problem

[`src/revolut_pit/pipeline.py:113-122`](../../src/revolut_pit/pipeline.py#L113-L122) bierze zagregowany wiersz "Income from Sells" z `profit_and_loss_YYYY.csv` Revoluta i przelicza **całość kosztu jednym kursem NBP D-1** dla `date_acquired`. Gdy ten wiersz reprezentuje wiele lotów kupna z różnych dni (typowy przypadek: dokupy DCA przez kilka miesięcy, sprzedaż w jednym dniu), jeden kurs zastępuje wiele kursów per nabycie — naruszenie **art. 11a ust. 2 ustawy PIT**.

Konsekwencja: błąd kosztu rzędu 3-8% w okresach skoków kursu USD/PLN; podatek zaniżony lub zawyżony zależnie od kierunku dryfu.

[`src/revolut_pit/calculator.py`](../../src/revolut_pit/calculator.py) **już zawiera** poprawną implementację per-lot z `add_buy()` / `calculate_sell()` — ale `pipeline.process_stocks()` jej nie wywołuje. Dla akcji jest to **dead code**.

## Co jest potrzebne

1. **Pewność co do formatu Revolut P&L.** Czy "Income from Sells" daje:
   - **(a)** jeden wiersz na każdy match FIFO lot-by-lot (każdy `date_acquired` to konkretny zakup) — wtedy obecne podejście jest OK i wystarczy walidacja, **lub**
   - **(b)** wiersz zagregowany (jak twierdzi audyt) — wtedy trzeba zbudować FIFO samemu z `account_statement_YYYY.csv`.

   **Akcja:** sprawdzić ≥ 3 realne eksporty Revoluta z różnych lat z DCA i wieloma sprzedażami. Jeśli (b) — przejść do kroku 2.

2. **Refaktoryzacja `pipeline.process_stocks()`:**
   - Przed P&L: parse `account_statement_YYYY.csv` (oraz lat poprzednich, żeby zbudować FIFO carry-over) i wywołać `TaxCalculator.add_buy()` dla każdej transakcji BUY.
   - Dla każdej SELL z `account_statement` zawołać `TaxCalculator.calculate_sell()` — to per-lot D-1 załatwia.
   - Zachować P&L Revoluta jako **walidację cross-check** (drift > 0.5% → warning, jak już robi `audit.py`).

3. **Carry-over FIFO między latami.** Akcje kupione w 2020 a sprzedane w 2025 wymagają parsowania **wszystkich** poprzednich account_statementów. Tool obecnie patrzy tylko na rok `--year`. Wymaga to:
   - Nowej opcji CLI `--data-dir-history` lub konwencji `<data_dir>/<year>/...` z auto-discovery.
   - Cache stanu FIFO po roku (np. `~/.cache/revolut_pit/fifo_state_<broker>_<account>.json`).

4. **Walidacja per-lot match z Revolutem.** Jeśli nasz FIFO daje inny match niż P&L Revoluta (np. broker użył inne lot ze względu na specjalne wybranie LIFO/HIFO przez użytkownika), zalogować rozbieżność i pozwolić użytkownikowi wybrać.

## Szacowany rozmiar

- **Kod:** ~250-400 LOC (process_stocks + history loader + cache + CLI)
- **Testy:** ~10 nowych test cases (multi-lot, multi-year, drift validation)
- **Dokumentacja:** aktualizacja HOW-IT-WORKS.md, AUDIT-TRAIL.md, ADD-BROKER.md
- **Walidacja na realnych danych:** 1-2 dni z eksportami Revoluta różnych użytkowników

## Tymczasowe ostrzeżenie dla użytkowników (do dodania w PR `fix/critical-pit38-bugs`)

Aktualnie filing dla portfeli z **dokupami w różnych okresach** może być nieprecyzyjny. Rekomendacja:
- Sprawdź ręcznie pozycje, w których `date_acquired` jest > 6 miesięcy przed `date_sold`
- Dla tych pozycji policz koszt per-lot ze swoim własnym arkuszem (FIFO + NBP D-1 per zakup)

Ostrzeżenie zostanie dodane w `pipeline.process_stocks()` jako log + w docs/SAFETY.md.

## Priorytet

**HIGH** — ale niżej niż naprawiony już Bug #1 (mieszanie C/E) i Bug #6 (false-positive swap). Dla większości użytkowników z głównie krótkoterminowymi pozycjami impact jest mały. Krytyczne dla LTR (long-term retail) z wieloletnim DCA.

## Powiązane issues do zaadresowania w tym samym PR

- Issue #10 z REVIEW-MODEL-QA: walidacja `date_acquired <= date_sold` — łatwo dodać w trakcie refaktoryzacji.
- Issue #11: ujednolicenie klucza cache NBP między pipeline i calculator.
- Bug #8: dywidendy w PLN obchodzą NBP — przy okazji dodać warning.
