# Audyt bezpieczeństwa i zgodności — 2026-04-28

Trzyrównoległy audyt repozytorium revolut-pit przed sezonem PIT-38 za rok 2025.

## Wyniki

- **[REVIEW-LEGAL.md](REVIEW-LEGAL.md)** — Audyt zgodności z polską ustawą PIT (art. 9, 11a, 22, 30a, 30b) + UPO. Werdykt: **NIE GOTOWE do filing**, naruszenie min. 4 artykułów ustawy.
- **[REVIEW-SECURITY.md](REVIEW-SECURITY.md)** — Audyt bezpieczeństwa (Streamlit, dane finansowe, ścieżki, dependencies). 2 CRITICAL, 5 HIGH, 5 MEDIUM, 3 LOW.
- **[REVIEW-MODEL-QA.md](REVIEW-MODEL-QA.md)** — Audyt poprawności obliczeń podatkowych i edge-cases. 8 potwierdzonych bugów, w tym 3 CRITICAL.

## Top 3 do natychmiastowej naprawy

1. **Bug #3 (legal+QA): Mieszanie strat C/E** — `pit38.py:77` — naruszenie art. 22 ust. 14 i art. 30b ust. 1a PIT ✅ NAPRAWIONE
2. ~~**Bug #1 (legal+QA): Pipeline nie używa TaxCalculator dla akcji**~~ — ❌ **FALSE POSITIVE.** Weryfikacja na realnych danych (`data/2020`–`data/2025`) wykazała, że Revolut emituje per-lot wiersze. Pipeline jest zgodny z art. 11a ust. 2 PIT. Patrz [`BUG-3-PER-LOT-FIFO-PLAN.md`](BUG-3-PER-LOT-FIFO-PLAN.md).
3. **Bug #6 (QA): Detekcja swapów krypto false positive wyklucza legalne sprzedaże** — `parsers/revolut/crypto.py:121-148` + `pipeline.py:213` ✅ NAPRAWIONE

## Pozostałe krytyczne

- **Sec #1+#2:** Path traversal + TOCTOU w upload (`app.py:224, 291, 521`)
- **Sec #4:** CSV injection w XLSX dla księgowej (`reports.py:170-230`)
- **Bug #2:** Strata bieżącego roku znika (`pit38.py:155`)
- **Bug #5:** Wigilia 24.12.2025 (`nbp.py:22-32`)

## Powiązane

Niniejszy audyt **uzupełnia/koryguje** istniejące dokumenty review w `docs/`:
- `docs/REVIEW-AUDITOR.md` — daje **PASS**, ale **fałszywie pozytywny** (sample 7/73 stocks; nie wykrywa Bug #1, #3)
- `docs/REVIEW-DATA-ANALYST.md` — wykrywa #1 częściowo (cost_basis_foreign), pomija agregację Revolut P&L
- `docs/REVIEW-TAX-ACCOUNTANT.md` — wykrywa loss carry-forward 5M cap (już naprawione w `pit38.py:79`), pomija mieszanie C/E i `dochod_razem`
