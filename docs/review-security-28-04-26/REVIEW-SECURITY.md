# Audyt bezpieczeństwa: revolut-pit

**Data:** 2026-04-28
**Repozytorium:** `/Users/adampacz/projects/revolut-pit/`
**Kontekst:** Aplikacja Python/Streamlit do lokalnego przetwarzania wrażliwych danych finansowych (CSV brokera, ISIN, kwoty transakcji, daty). Domyślnie zakładana jako `localhost`, ale instrukcje w README nie precyzują bind-address.

---

## CRITICAL

### Finding 1: Path traversal w zapisie uploadowanego pliku do `/tmp` [ZWERYFIKOWANE]
- **Severity:** Critical (lokalnie), High (w trybie multi-user/server)
- **CVSS estimate:** 7.5 (CVSS:3.1/AV:N/AC:L/PR:L/UI:R/S:U/C:H/I:H/A:N) — przy uruchomieniu wieloużytkownikowym; 5.5 lokalnie
- **Location:** `app.py:224`, `app.py:298`, `app.py:528`
- **Vulnerability:** `temp_path = Path(f"/tmp/{uploaded_file.name}")` — `uploaded_file.name` jest atrybutem przesyłanym z klienta. Polegać na sanityzacji Streamlit jest niebezpieczne.
- **Mitigation:** `Path(uploaded_file.name).name`, białolista znaków, `tempfile.mkdtemp()`.

### Finding 2: Predictable temp directory + race condition (TOCTOU) [ZWERYFIKOWANE]
- **Severity:** Critical (na maszynach multi-user)
- **Location:** `app.py:291` i `app.py:521`
- **Vulnerability:** `temp_dir = Path(f"/tmp/revolut_pit_{datetime.now().timestamp()}")` + `mkdir(exist_ok=True)`. Predictable timestamp + TOCTOU symlink hijack.
- **Mitigation:** `tempfile.mkdtemp(prefix="revolut_pit_")` + `chmod(0o700)`.

---

## HIGH

### Finding 3: Brak czyszczenia `/tmp` — wrażliwe dane finansowe leżą permanentnie [ZWERYFIKOWANE]
- **Location:** `app.py:224, 291, 298, 521, 528, 615, 701`
- **Vulnerability:** `/tmp` na większości systemów linuksowych jest world-readable (mode 1777). Wrażliwe dane: ISIN, daty zakupu/sprzedaży, kwoty PLN, nazwy tickerów.
- **Mitigation:** `with tempfile.TemporaryDirectory() as td: ...`. Plik PDF/XLSX serwować z `BytesIO`.

### Finding 4: CSV injection (Excel formula injection) w wygenerowanych raportach [ZWERYFIKOWANE]
- **Severity:** High
- **CVSS estimate:** 7.8 (CVSS:3.1/AV:L/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H) — RCE u odbiorcy raportu
- **Location:** `src/revolut_pit/reports.py:170-178` (stocks), `186-200` (crypto), `220-230` (dividends)
- **Vulnerability:** Pola `symbol`, `country`, `isin` z user-uploaded CSV trafiają do Excela bez sanityzacji. Złośliwy ticker `=cmd|'/C calc'!A1` wykonuje się przy otwarciu (np. u księgowej!).
- **Mitigation:** `sanitize = lambda s: ("'" + s) if isinstance(s, str) and s and s[0] in "=+-@\t\r" else s`.

### Finding 5: SSRF / path injection przez `currency` w NBP URL [ZWERYFIKOWANE]
- **Location:** `src/revolut_pit/nbp.py:177` — `url = f"{self.BASE_URL}/{table}/{currency}/{date_str}/?format=json"`
- **Vulnerability:** `currency` z CSV bez walidacji `^[A-Z]{3}$`. Cache poisoning + arbitralne kursy NBP → fałszywe obliczenia podatkowe (integrity).
- **Mitigation:** `if not re.match(r"^[A-Z]{3}$", currency): raise ValueError(...)`.

### Finding 6: Streamlit domyślnie binduje na `0.0.0.0` w niektórych konfiguracjach [SPECULATIVE]
- **Location:** `README.md:62` — `streamlit run app.py` (bez flag).
- **Vulnerability:** Brak ostrzeżenia w docs że narzędzie jest *single-user, localhost-only by design*.
- **Mitigation:** Rekomendowana komenda `streamlit run app.py --server.address=127.0.0.1`.

### Finding 7: Brak izolacji session_state między użytkownikami [SPECULATIVE]
- **Location:** `app.py:59-90`
- **Vulnerability:** Pliki w `/tmp/<filename>` i `/tmp/revolut_pit_<ts>/` są **globalne dla wszystkich użytkowników maszyny**.

---

## MEDIUM

### Finding 8: Logowanie wrażliwych danych z `print()` przez `e` w except [ZWERYFIKOWANE]
- **Location:** `parsers/revolut/stocks.py:130, 203, 224`, `parsers/revolut/crypto.py:114`, `pipeline.py:218, 268`
- **Vulnerability:** `e` z pandas `pd.to_datetime` lub `parse_amount` często zawiera *wartość*, która spowodowała błąd. PII na stdout.

### Finding 9: Cache na dysku bez szyfrowania, mode default [ZWERYFIKOWANE]
- **Location:** `src/revolut_pit/nbp.py:67-72, 84-87`
- **Vulnerability:** `~/.cache/revolut_pit/nbp_rates.json` — mode 0755 (default umask). Brak file locking → race condition.
- **Mitigation:** `chmod(0o700)`, atomic write przez `tempfile + os.replace`.

### Finding 10: Reportlab `<para>` injection — CVE-2023-33733 [ZWERYFIKOWANE]
- **Location:** `src/revolut_pit/pdf_audit.py:241, 550-562`
- **Vulnerability:** `Paragraph(f"<b>Podatnik:</b> {user_identifier}", ...)` — `user_identifier` ładowane bez escapowania. Vulnerable wersje reportlab <3.6.13 RCE.
- **Mitigation:** Pin `reportlab>=3.6.13`. Eskejpować przez `xml.sax.saxutils.escape`.

### Finding 11: `pd.read_csv` na user files — DoS via OOM
- **Location:** `parsers/revolut/stocks.py:90`, `parsers/revolut/crypto.py:86`, `pipeline.py:223`
- **Vulnerability:** Brak limitu rozmiaru pliku (default 200MB Streamlit).

### Finding 12: NBP API rate flooding przez user-controlled `tax_year`
- **Location:** `app.py:140-146`, `nbp.py:142-158`
- **Vulnerability:** Brak rate limitingu po stronie klienta.

---

## LOW

### Finding 13: `unsafe_allow_html=True` w sidebarze
- **Location:** `app.py:178`

### Finding 14: Brak timeout-cleanup state machines
- Reset wymaga manualnej akcji.

### Finding 15: Brak Content-Security-Policy / X-Frame-Options
- Streamlit nie wystawia security headers domyślnie.

---

## INFO / Hardening recommendations

1. **Brak input validation typów** — `country`, `isin`, `symbol`, `currency` są strings z arbitralną zawartością.
2. **`Decimal(str(row["Quantity"]))`** w `pipeline.py:230` — brak ograniczenia precision.
3. **Brak signature/hash CSV** — narzędzie ufa eksportom Revolut bez weryfikacji autentyczności.
4. **`json.load(f)` na cache** — atakujący nadpisując cache wstrzykuje arbitralne kursy NBP.
5. **Brak `chmod` na output files** — generated XLSX/PDF w `/tmp` mają 0644.
6. **`audit_runner.py` w repo** — sprawdzić czy nie zawiera credentials.
7. **`.coverage` files committed** — sprawdzić `.gitignore`.
8. **Brak SECURITY.md** — projekt open-source bez polityki disclosure.

---

## Dependencies CVE check

| Pakiet      | Pinned    | Zalecany min     | Znane CVE w zakresie               |
|-------------|-----------|------------------|------------------------------------|
| `requests`  | >=2.28.0  | >=2.32.4         | CVE-2024-35195, CVE-2024-47081     |
| `pandas`    | >=1.3.0   | >=2.2.0          | dependency hygiene                 |
| `openpyxl`  | >=3.0.0   | >=3.1.5          | XXE-podobne issues w shared strings (<3.0.10) |
| `streamlit` | >=1.20.0  | >=1.37.0         | CVE-2024-42474 (path traversal)    |
| `reportlab` | >=3.6.0   | **>=3.6.13**     | **CVE-2023-33733 RCE** w `<para>`/`<font color>` |
| `click`     | >=8.0.0   | >=8.1.7          | brak krytycznych                   |

**Krytyczne do zrobienia:** podnieść minima — szczególnie `reportlab>=3.6.13`, `streamlit>=1.37.0`, `requests>=2.32.4`. Dodać `pip-audit` do CI.

---

## Podsumowanie

**Krytyczne (do naprawy natychmiast):**
1. Path traversal w upload (`app.py:224, 298, 528`)
2. Predictable temp dir + TOCTOU (`app.py:291, 521`)
3. CSV injection w XLSX dla księgowej (`reports.py:170+`)

**Wysokie (do naprawy w następnym sprincie):**
4. Brak cleanup `/tmp`
5. SSRF/path injection w `currency` → NBP URL
6. Brak ostrzeżenia o `localhost-only` w README

**Filozofia naprawy:** to narzędzie *should be* lokalnym single-user CLI/desktopowym wizardem — NIE web-app.

**Najważniejsze pliki:**
- `app.py` (linie 224, 291, 521, 528, 615, 701)
- `src/revolut_pit/nbp.py` (linie 84-87, 177)
- `src/revolut_pit/reports.py` (linie 170-230)
- `src/revolut_pit/pdf_audit.py` (linie 241, 550-562)
- `src/revolut_pit/parsers/revolut/stocks.py` (linie 130, 191-194, 203, 224)
- `requirements.txt` + `pyproject.toml` (pinning)
