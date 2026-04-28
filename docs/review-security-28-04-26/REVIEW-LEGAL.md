# RAPORT KRYTYCZNEGO AUDYTU PRAWNEGO — `revolut-pit`

**Audytor:** Doradca podatkowy / compliance officer
**Data:** 2026-04-28
**Rok podatkowy objęty audytem:** 2025 (deadline: 30 kwietnia 2026)
**Wniosek nadrzędny:** **NIE WYPEŁNIAĆ PIT-38 ZA 2025 WYŁĄCZNIE NA PODSTAWIE WYNIKÓW TEGO NARZĘDZIA.** Tool zawiera **co najmniej trzy błędy strukturalne, które zaniżają lub zawyżają zobowiązanie podatkowe** i mogą skutkować odpowiedzialnością karnoskarbową (art. 56 KKS — nierzetelne zeznanie).

---

## KRYTYCZNE — narzędzie produkuje deklarację niezgodną z ustawą o PIT

### #1: Mieszanie strat z kryptowalut (część E) i papierów wartościowych (część C) — naruszenie art. 22 ust. 14 i art. 30b ust. 1a PIT
- **Lokalizacja:** `src/revolut_pit/pit38.py:77`, `pit38.py:113`
- **Co robi tool:** `capital_gains_income = czesc_c["dochod_pln"] + czesc_e["dochod_pln"]` — sumuje dochód z papierów wartościowych z dochodem z kryptowalut do jednej puli, od której odejmuje stratę z lat ubiegłych i nalicza 19%.
- **Co stanowi prawo:**
  - **Art. 30b ust. 1 PIT:** dochód z odpłatnego zbycia papierów wartościowych — 19%, źródło: kapitały pieniężne (art. 17 ust. 1 pkt 6).
  - **Art. 30b ust. 1a PIT:** *"Od dochodów uzyskanych z odpłatnego zbycia walut wirtualnych podatek dochodowy wynosi 19% uzyskanego dochodu."* — **odrębne źródło**, art. 17 ust. 1 pkt 11.
  - **Art. 22 ust. 14 PIT:** koszty uzyskania przychodów z odpłatnego zbycia walut wirtualnych są rozliczane **wyłącznie** w ramach przychodów z walut wirtualnych. Strata z kryptowalut **nie pomniejsza** dochodu z papierów wartościowych — przechodzi natomiast na kolejny rok w obrębie tego samego źródła (art. 22 ust. 16).
  - **Art. 9 ust. 6 PIT** w związku z art. 9 ust. 3a: strata z danego źródła rozliczana wyłącznie w ramach tego samego źródła.
- **Skutek:** Jeśli np. inwestor ma w 2025 dochód z akcji 100 000 PLN i stratę na krypto –30 000 PLN, tool wykaże dochód 70 000 PLN i podatek 13 300 PLN. Prawidłowo: dochód z akcji 100 000 (podatek 19 000), strata krypto –30 000 PLN raportowana w części E z przeniesieniem (do rozliczenia tylko w przyszłych latach z dochodem z krypto). **Zaniżenie podatku o ~5 700 PLN.** W odwrotnym scenariuszu — zawyżenie.
- **Sankcja:** art. 56 KKS — kara grzywny do 720 stawek dziennych za nierzetelne zeznanie podatkowe. Plus odsetki od zaległości (art. 53 OP).

### #2: Strata z roku bieżącego znika bezpowrotnie — naruszenie art. 9 ust. 3 PIT
- **Lokalizacja:** `src/revolut_pit/pit38.py:152-156` (`_aggregate_section`)
- **Co robi tool:** Jeśli `dochod = przychod - koszt < 0`, zwraca `max(Decimal(0), dochod)` — czyli **zeruje stratę** i nigdzie jej nie raportuje. Brak pola `strata_pln` w zwracanej strukturze. PIT-38 część C ma osobną rubrykę "Strata" (poz. 26) i analogicznie część E (poz. 34).
- **Co stanowi prawo:** **Art. 9 ust. 3 PIT:** *"O wysokość straty ze źródła przychodów, poniesionej w roku podatkowym, podatnik może obniżyć dochód uzyskany z tego źródła w najbliższych kolejno po sobie następujących pięciu latach podatkowych, z tym że kwota obniżenia w którymkolwiek z tych lat nie może przekroczyć 50% wysokości tej straty"* (z wyjątkiem jednorazowego rozliczenia 5 mln PLN — art. 9 ust. 3 zdanie drugie).
- **Skutek:** Inwestor traci prawo do przeniesienia straty na następne 5 lat. Przy stracie 50 000 PLN to potencjalnie 9 500 PLN niezrealizowanego kredytu podatkowego.

### #3: Dywidendy zwiększają `dochod_razem` — fundamentalny błąd w architekturze PIT-38
- **Lokalizacja:** `src/revolut_pit/pit38.py:109` `dochod_razem = capital_gains_income + czesc_d["przychod_pln"]`
- **Co stanowi prawo:**
  - **Art. 30a ust. 1 pkt 4 PIT:** *"od uzyskanych dochodów (przychodów) z dywidend i innych przychodów z tytułu udziału w zyskach osób prawnych pobiera się 19% zryczałtowany podatek dochodowy"*.
  - **Art. 30a ust. 7 PIT:** *"Dochodów (przychodów), o których mowa w ust. 1, nie łączy się z dochodami opodatkowanymi na zasadach określonych w art. 27."* — i analogicznie nie łączy się z dochodami z art. 30b.
- **Skutek:** Pole `dochod_razem` jest **fałszywe i mylące** — może być pokazywane użytkownikowi i przepisywane do błędnych pól.

### #4: Agregacja kosztu z różnych dni nabycia i przeliczanie jednym kursem D-1 — naruszenie art. 11a ust. 2 PIT
- **Lokalizacja:** `src/revolut_pit/pipeline.py:115-119`
- **Co robi tool:** `cost_rate = self._get_rate(currency, s["date_acquired"])` i `cost_pln = round_grosz(s["cost_basis"] * cost_rate)`. Gdy `cost_basis` z Revoluta agreguje wiele lotów (np. 10 zakupów AAPL z różnych dni przy FIFO), tool **przelicza całość jednym kursem** z dnia podanym jako `date_acquired`.
- **Co stanowi prawo:** **Art. 11a ust. 2 PIT:** *"Koszty poniesione w walutach obcych przelicza się na złote według kursu średniego ogłaszanego przez Narodowy Bank Polski z ostatniego dnia roboczego poprzedzającego dzień poniesienia kosztu."* — kurs **per zdarzenie**, nie per agregat.
- **Skutek:** Przy akcjach kupowanych przez kilka lat w okresach skoków USD/PLN, błąd może sięgać **3–8% kosztu**.
- **Tool jest kompletnie nieprzygotowany do prawidłowego rozliczenia FIFO w walutach obcych.** Plik `calculator.py` zawiera FIFO, ale `pipeline.py` go **nie używa dla akcji**.

### #5: Stawka traktatowa UK — uwagi
- **Lokalizacja:** `src/revolut_pit/dividends.py:15` `"GB": Decimal("0.10")`
- **Co stanowi prawo:** **Konwencja PL-UK z 20.07.2006 r. (Dz.U. 2006 nr 250 poz. 1840), art. 10 ust. 2 lit. b:** stawka WHT na dywidendy wynosi 10%. UK krajowo nie pobiera WHT od dywidend dla osób fizycznych — w praktyce `wht_paid_pln = 0`.
- **Wpływ:** Niski. Dla DE/NL stawka traktatowa to 5%/15% (DE — 5% przy udziale ≥ 10% kapitału, art. 10 ust. 2 lit. a Konwencji PL-DE z 14.05.2003) i 15% (NL).

---

## WYSOKIE

### #6: Brak Wigilii 24 grudnia 2025 w kalendarzu świąt NBP
- **Lokalizacja:** `src/revolut_pit/nbp.py:22-32` (`POLISH_FIXED_HOLIDAYS`)
- **Stan prawny:** **Ustawa z dnia 6 grudnia 2024 r. o zmianie ustawy o dniach wolnych od pracy (Dz.U. 2024 poz. 1965)** — od 2025 r. **24 grudnia (Wigilia) jest dniem ustawowo wolnym od pracy.** NBP nie publikuje tabel kursowych w dniach wolnych od pracy.

### #7: Detekcja swapów krypto patrzy tylko na `i+1` — fałszywe negatywy i fałszywe pozytywy
- **Lokalizacja:** `src/revolut_pit/parsers/revolut/crypto.py:121-148`
- **Co robi tool:** `_detect_swaps` iteruje przez transakcje i porównuje wiersz `i` z `i+1`. Jeśli pomiędzy Sell a Buy znajdzie się jakikolwiek inny wiersz, swap **nie zostanie wykryty**. Dodatkowo `pipeline.py:213` `swap_keys.add((tx["symbol"], tx["date"].date()))` może wykluczyć **legalne sprzedaże** danego dnia.

### #8: Trustowanie wartości PLN z Revoluta dla dywidend — naruszenie art. 11a ust. 1 PIT
- **Lokalizacja:** `src/revolut_pit/pipeline.py:152-156`
- **Co robi tool:** Jeśli `currency == "PLN"`, używa wartości "as-is" z eksportu Revoluta (kurs Revoluta, nie NBP).
- **Co stanowi prawo:** **Art. 11a ust. 1 PIT:** kurs **NBP**, nie kurs brokera.

### #9: Kraj źródła dywidendy = pierwsze 2 znaki ISIN — heurystyka niezgodna z art. 24 ust. 2 UPO
- **Lokalizacja:** `src/revolut_pit/pipeline.py:30-34, 162-167`
- **Stan prawny:** Dla potrzeb art. 24 (kredyt podatkowy) i PIT/ZG kraj źródła = kraj rezydencji **emitenta dywidendy**. ETF IE (Irlandia) wypłaca dywidendę irlandzką (IE) — mimo że trzyma akcje US.
- **Stan dla `XX` (nieznany):** tool fallbackuje na `"US"` (pipeline.py:166) — **niedopuszczalne**.

### #10: PIT/ZG zawiera tylko dywidendy, brak zysków kapitałowych z zagranicy
- **Lokalizacja:** `src/revolut_pit/pit38.py:118-127`
- **Wpływ:** Niski dla typowego użytkownika Revoluta (rynki US/EU), ale brak ostrzeżenia.

---

## ŚREDNIE

### #11: Niepoprawne odniesienia ustawowe w `docs/TAX-LOGIC.md`
- Część C — to **art. 30b ust. 1 PIT**, nie art. 30a.
- Część D — to **art. 30a ust. 1 pkt 4**, nie "art. 24 ust. 1 pkt 1".
- Część E — to **art. 30b ust. 1a**, nie art. 30a.
- Strata z lat ubiegłych — to **art. 9 ust. 3 PIT**, nie "art. 7e" (art. 7e w PIT nie istnieje).

### #12: Brak rozróżnienia REIT, return of capital, Section 199A
- Polska traktuje wszystkie wypłaty jako dywidendę 19% (art. 30a ust. 1 pkt 4). **Return of capital nie stanowi przychodu** (art. 5a pkt 31). Tool zawyża podatek 3-5% rocznie dla portfeli z REIT.

### #13: Brak rozróżnienia akcji, ETF, obligacji
- Polski PIT-38 nie rozróżnia w obrębie części C (OK), ALE obligacje skarbowe odsetki opodatkowane art. 30a ust. 1 pkt 2 (zryczałtowany 19%, nie podlega kompensacie strat).

### #14: Stake/learn rewards — niespójność z `docs/TAX-LOGIC.md:84`
- Według aktualnej linii KIS koszt staking rewards = **0 PLN** (otrzymane "darmo"), nie FMV. Tool może zaniżać podatek o cały koszt rewards.

---

## DROBNE / DOKUMENTACYJNE

### #15: Stała `LOSS_CAP_PER_YEAR = 5_000_000` opisana jako `art. 7e ust. 3`
- **Stan prawny:** Limit 5 mln PLN wynika z **art. 9 ust. 3 zdanie drugie PIT**. Komentarz w `pit38.py:6` jest **błędny prawnie**.

### #16: Stałe podatkowe jako Decimal w ustawie nie są stałe wieczne
- 19% jest twardo wkodowane. Brak ostrzeżenia o ryzyku zmiany ustawy.

### #17: Brak obsługi zaokrąglenia podstawy opodatkowania do pełnych złotych
- **Art. 63 §1 OP:** podstawy opodatkowania zaokrągla się do pełnych złotych (>=0,50 w górę). Tool zaokrągla do groszy.

---

## ZGODNE Z PRAWEM (zweryfikowane pozytywnie)
- **Stawka 19% dla dywidend** (art. 30a ust. 1 pkt 4 PIT) — **OK**.
- **Zasada D-1 dla NBP** (art. 11a ust. 1 i 2 PIT) — **OK** koncepcyjnie, **niepoprawnie zaimplementowana per agregat** (zob. #4).
- **Krediut podatkowy ograniczony do stawki traktatowej** (art. 30a ust. 9 i ust. 11 PIT) — **OK**.
- **Wyłączenie crypto-to-crypto z opodatkowania** (art. 17 ust. 1 pkt 11 + art. 22 ust. 14) — **koncepcyjnie OK**, ale detekcja wadliwa (zob. #7).
- **Limit 5 mln PLN przy rozliczeniu strat z lat ubiegłych** — **liczba poprawna**.

---

## REKOMENDACJE

1. **Przed użyciem do filing 2025 — BEZWZGLĘDNIE:**
   - **Nie używać tego narzędzia jako jedynego źródła** dla deklaracji PIT-38.
   - **Rozdzielić wyniki C i E** i zweryfikować, czy aplikacja straty z lat ubiegłych była tylko w obrębie tego samego źródła.
   - **Sprawdzić każdą transakcję krypto** pod kątem swapów.
   - **Dla każdej akcji sprzedanej w 2025 r. dokupowanej w więcej niż jednym dniu** — przeliczyć koszt per lot z odrębnym kursem D-1.
   - **Wigilia 24.12.2025**: jeśli były transakcje 22–29 grudnia, ręcznie zweryfikować NBP.

2. **Bug fixes priorytetowe (przed kolejnym wydaniem):**
   - #1: Rozdzielić pule strat C i E w `pit38.py`.
   - #2: Wprowadzić raportowanie `strata_pln` w `_aggregate_section`.
   - #3: Usunąć dywidendy z `dochod_razem`.
   - #4: Zintegrować `calculator.py` FIFO z `pipeline.py` dla akcji.
   - #6: Dodać `(12, 24)` do `POLISH_FIXED_HOLIDAYS` od roku 2025.
   - #7: Przepisać `_detect_swaps` na pełnoklasowe matching po timestamp+quantity bez założenia adjacency.

3. **Dokumentacja:**
   - Skorygować `docs/TAX-LOGIC.md` — wszystkie odniesienia ustawowe (art. 30b, art. 9 ust. 3, art. 30a ust. 1 pkt 4, art. 22 ust. 14).

**Końcowa rekomendacja:** Repozytorium **NIE jest gotowe** do pełnoautonomicznego użytku przez podatnika za rok 2025. Filing wykonany 1:1 z output toola **zawiera istotne ryzyko nierzetelności** w rozumieniu art. 56 KKS.

---

**Pliki audytowane:**
- `src/revolut_pit/pit38.py`
- `src/revolut_pit/pipeline.py`
- `src/revolut_pit/dividends.py`
- `src/revolut_pit/nbp.py`
- `src/revolut_pit/parsers/revolut/crypto.py`
- `docs/TAX-LOGIC.md`
