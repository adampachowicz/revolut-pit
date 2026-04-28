**[PL](#polski) | [EN](#english)**

---

# Polski

## revolut-pit — Kalkulator PIT-38 dla inwestorów

Automatyczne obliczenie polskiego formularza PIT-38 bezpośrednio z eksportów danych Revolut.

revolut-pit to narzędzie open-source przeznaczone dla inwestorów, którzy prowadzą transakcje na platformie Revolut (akcje, kryptowaluty, dywidendy) i muszą rozliczać się podatkowo w Polsce. Oblicza automatycznie:

- **Część C (Papiery wartościowe)**: dochody ze sprzedaży akcji, ETF-ów
- **Część D (Dywidendy)**: przychody z dywidend, kredyty zagraniczne (WHT)
- **Część E (Kryptowaluty)**: dochody ze sprzedaży kryptowalut (z wyłączeniem SWAP-ów)
- **Część G (Straty)**: przeniesienie strat z lat ubiegłych
- **PIT/ZG (Załącznik)**: dochody zagraniczne i podatki

### Cechy

- ✅ **Pełna automatyzacja**: Z eksportu CSV do gotowego PIT-38
- ✅ **Wielojęzyczność**: PL i EN
- ✅ **Oficjalne kursy NBP**: Automatyczne pobieranie kursów D-1 z API NBP
- ✅ **Zaokrąglanie groszem**: Zgodne z polskim prawem (art. 63 Ordynacji)
- ✅ **Ślad audytowy**: Każda liczba posiada link do źródła (NBP API URL)
- ✅ **FIFO dla akcji**: Automatyczne stosowanie metody FIFO (art. 30b ust. 6)
- ✅ **Krzyżowa weryfikacja**: Sprawdzenie precyzji obliczeń
- ✅ **Eksport do Excel/Markdown/JSON**: Łatwa integracja z księgową
- ✅ **Architektura plug-in**: Łatwe dodawanie kolejnych brokerów
- ✅ **Open-source**: MIT License, w pełni przejrzyste

### Wymagania systemowe

- Python 3.8+
- pip

### Instalacja

```bash
pip install git+https://github.com/TODO/revolut-pit.git
# lub lokalnie:
pip install -e .
```

### Użycie

#### CLI (command-line)

```bash
revolut-pit calc \
  --year 2025 \
  --data-dir ./data \
  --output-dir ./output \
  --prior-loss 50000  # PLN z lat ubiegłych
```

Plik będzie eksportowany do `./output/pit38_2025.xlsx`

#### Streamlit UI (graficzny interfejs)

```bash
streamlit run app.py
```

Otworzy się aplikacja webowa na `http://localhost:8501/`

**Kroki:**
1. Prześlij pliki CSV z Revolut
2. Ustaw rok podatkowy i stratę z lat ubiegłych (jeśli dotyczy)
3. Kliknij "Oblicz PIT-38"
4. Przejrzyj wyniki w interaktywnych kartach
5. Pobierz raport (Excel, Markdown, JSON)

### Obsługiwane formaty danych

Aktualne:
- Revolut account_statement_YYYY.csv (akcje)
- Revolut profit_and_loss_YYYY.csv (akcje, dywidendy)
- Revolut crypto_account_statement_YYYY.csv (kryptowaluty)
- Revolut crypto_profit_and_loss_YYYY.csv (kryptowaluty)

Architektura plug-in umożliwia łatwe dodawanie kolejnych brokerów.

### Przykład wyniku

```
Tax Year: 2025

Part C - Securities (Papiery wartościowe)
  Revenue:      100,000.00 PLN
  Cost:          80,000.00 PLN
  Income:        20,000.00 PLN
  Tax @ 19%:      3,800.00 PLN

Part E - Crypto
  Revenue:       50,000.00 PLN
  Cost:          40,000.00 PLN
  Income:        10,000.00 PLN
  Tax @ 19%:      1,900.00 PLN

Part D - Dividends
  Gross:         10,000.00 PLN
  WHT Paid:      -3,000.00 PLN
  Tax to Pay:         0.00 PLN (kredyt zagraniczny)

TOTAL TAX TO PAY: 5,700.00 PLN
```

### Dokumentacja

Zanim zaczniesz, przeczytaj:
- [docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md) — algorytm FIFO, fallback NBP, zaokrąglanie
- [docs/TAX-LOGIC.md](docs/TAX-LOGIC.md) — artykuły prawa, interpretacje
- [docs/AUDIT-TRAIL.md](docs/AUDIT-TRAIL.md) — jak ręcznie weryfikować każdą liczbę
- [docs/SAFETY.md](docs/SAFETY.md) — co gwarantujemy, co nie

### Zastrzeżenia

⚠️ **To narzędzie nie jest poradą podatkową.**

Każdy obywatel ma obowiązek prawidłowego rozliczenia podatków. Narzędzie to:
- ✅ Pomaga w obliczeniach
- ❌ Nie zastępuje doradcy podatkowego
- ❌ Nie bierze odpowiedzialności za błędy w zeznaniu

**Zawsze zweryfikuj wyniki z księgową lub doradcą podatkowym przed złożeniem.**

### Znane ograniczenia

- Obsługuje tylko Revolut (na razie)
- Nie obsługuje: CFD, opcje, warranty, fundusze strukturyzowane
- Nie obsługuje: IKE, IKZE, LSPO w Revolut
- Nie auto-wypełnia formularza PIT-38 (musisz go skopiować ręcznie)
- Nie integruje się z e-podatkami (generator kodu)

### Contributing / Jak wnieść wkład

1. Fork, commit, push, pull request
2. Napisz test dla nowej funkcjonalności
3. Upewnij się, że 100% testów przechodzi
4. Opisz, co się zmieniło

Oto jak dodać nowego brokera: [docs/ADD-BROKER.md](docs/ADD-BROKER.md)

### Licencja

MIT License — używaj, modyfikuj, dystrybuuj swobodnie.

### Podziękowania

Opracowane dla polskiej społeczności inwestorów. NBP API za kursy walut.

---

# English

## revolut-pit — PIT-38 Calculator for Investors

Automatic calculation of the Polish PIT-38 tax form directly from Revolut export data.

revolut-pit is an open-source tool for investors who trade on Revolut (stocks, crypto, dividends) and need to file taxes in Poland. It automatically calculates:

- **Part C (Securities)**: income from stock and ETF sales
- **Part D (Dividends)**: dividend income, foreign tax credits (WHT)
- **Part E (Crypto)**: income from crypto sales (with SWAP exclusion)
- **Part G (Losses)**: loss carry-forward from prior years
- **PIT/ZG (Attachment)**: foreign income and foreign taxes

### Features

- ✅ **Full automation**: From CSV export to ready PIT-38
- ✅ **Bilingual**: PL and EN
- ✅ **Official NBP rates**: Auto-fetches D-1 rates from NBP API
- ✅ **Grosz rounding**: Compliant with Polish tax law (art. 63 Ordination)
- ✅ **Audit trail**: Every number links back to source (NBP API URL)
- ✅ **FIFO for stocks**: Automatic FIFO method (art. 30b sec. 6)
- ✅ **Cross-validation**: Verification of calculation precision
- ✅ **Export to Excel/Markdown/JSON**: Easy integration with accountants
- ✅ **Plugin architecture**: Easy to add additional brokers
- ✅ **Open-source**: MIT License, fully transparent

### System Requirements

- Python 3.8+
- pip

### Installation

```bash
pip install git+https://github.com/TODO/revolut-pit.git
# or locally:
pip install -e .
```

### Usage

#### CLI (command-line)

```bash
revolut-pit calc \
  --year 2025 \
  --data-dir ./data \
  --output-dir ./output \
  --prior-loss 50000  # PLN from prior years
```

File will be exported to `./output/pit38_2025.xlsx`

#### Streamlit UI (web interface)

```bash
streamlit run app.py
```

Opens web application at `http://localhost:8501/`

**Steps:**
1. Upload CSV files from Revolut
2. Set tax year and prior-year loss (if applicable)
3. Click "Calculate PIT-38"
4. Review results in interactive tabs
5. Download report (Excel, Markdown, JSON)

### Supported Data Formats

Currently supported:
- Revolut account_statement_YYYY.csv (stocks)
- Revolut profit_and_loss_YYYY.csv (stocks, dividends)
- Revolut crypto_account_statement_YYYY.csv (crypto)
- Revolut crypto_profit_and_loss_YYYY.csv (crypto)

Plugin architecture allows easy addition of other brokers.

### Example Output

```
Tax Year: 2025

Part C - Securities
  Revenue:      100,000.00 PLN
  Cost:          80,000.00 PLN
  Income:        20,000.00 PLN
  Tax @ 19%:      3,800.00 PLN

Part E - Crypto
  Revenue:       50,000.00 PLN
  Cost:          40,000.00 PLN
  Income:        10,000.00 PLN
  Tax @ 19%:      1,900.00 PLN

Part D - Dividends
  Gross:         10,000.00 PLN
  WHT Paid:      -3,000.00 PLN
  Tax to Pay:         0.00 PLN (foreign tax credit)

TOTAL TAX TO PAY: 5,700.00 PLN
```

### Documentation

Before you start, read:
- [docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md) — FIFO algorithm, NBP fallback, rounding
- [docs/TAX-LOGIC.md](docs/TAX-LOGIC.md) — legal articles, interpretations
- [docs/AUDIT-TRAIL.md](docs/AUDIT-TRAIL.md) — how to manually verify each number
- [docs/SAFETY.md](docs/SAFETY.md) — what we guarantee, what we don't

### Disclaimers

⚠️ **This tool is NOT tax advice.**

Every citizen has a duty to properly file taxes. This tool:
- ✅ Helps with calculations
- ❌ Does not replace a tax advisor
- ❌ Does not assume responsibility for filing errors

**Always verify results with an accountant or tax advisor before filing.**

### Known Limitations

- Supports Revolut only (for now)
- Does not support: CFDs, options, warrants, structured funds
- Does not support: IKE, IKZE, LSPO in Revolut
- Does not auto-fill PIT-38 form (you copy manually)
- Does not integrate with e-Tax system (code generator)

### Contributing

1. Fork, commit, push, pull request
2. Write tests for new features
3. Ensure 100% of tests pass
4. Describe what changed

See how to add a new broker: [docs/ADD-BROKER.md](docs/ADD-BROKER.md)

### License

MIT License — use, modify, distribute freely.

### Acknowledgments

Developed for the Polish investor community. NBP API for exchange rates.
