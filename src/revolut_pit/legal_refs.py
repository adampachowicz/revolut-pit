"""Legal references for PIT-38 calculations.

Structured data with links to Polish tax law sources (ISAP, trakty).
"""

from dataclasses import dataclass
from typing import Dict, List, Literal

Language = Literal["pl", "en"]


@dataclass
class LegalRef:
    """A single legal reference with translations."""

    article: str  # e.g. "art. 30b ust. 6"
    act: str  # e.g. "ustawa o PIT"
    description_pl: str
    description_en: str
    url: str  # ISAP or trusted source


# Master registry of all legal references used in the wizard
LEGAL_REFS: Dict[str, LegalRef] = {
    "nbp_d_minus_1": LegalRef(
        article="art. 11a ust. 1",
        act="ustawa o podatku dochodowym od osób fizycznych",
        description_pl="Przychody w walutach obcych przelicza się na złote według kursu średniego ogłaszanego przez NBP z ostatniego dnia roboczego poprzedzającego dzień uzyskania przychodu.",
        description_en="Foreign currency income converts to PLN using the average NBP exchange rate published from the last business day preceding the transaction date.",
        url="https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU19910800350",
    ),
    "nbp_d_minus_1_definition": LegalRef(
        article="art. 11a ust. 3",
        act="ustawa o PIT",
        description_pl="Dzień poprzedzający — ostatni dzień roboczy poprzedzający dzień uzyskania przychodu.",
        description_en="Last business day before transaction date (weekend/holidays are skipped).",
        url="https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU19910800350",
    ),
    "crypto_crypto_exempt": LegalRef(
        article="art. 17 ust. 1f",
        act="ustawa o PIT",
        description_pl="Wymiana waluty wirtualnej na inną walutę wirtualną nie podlega opodatkowaniu (pod warunkiem braku pośrednika i bezpośredniej wymiany).",
        description_en="Crypto-to-crypto swaps are not taxable events (direct exchange without intermediary).",
        url="https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU19910800350",
    ),
    "capital_gains_19_percent": LegalRef(
        article="art. 30b ust. 1",
        act="ustawa o PIT",
        description_pl="Dochód ze zbycia papierów wartościowych jest opodatkowany stawką 19%.",
        description_en="Capital gains from securities sale are taxed at 19% flat rate.",
        url="https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU19910800350",
    ),
    "fifo_method": LegalRef(
        article="art. 30b ust. 6 + art. 24 ust. 10",
        act="ustawa o PIT",
        description_pl="Metoda FIFO (First In First Out) jest obowiązkowa do określenia kosztu uzyskania przychodu przy zbyciu papierów wartościowych.",
        description_en="FIFO method is mandatory for cost basis determination in securities sales.",
        url="https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU19910800350",
    ),
    "cost_of_revenue": LegalRef(
        article="art. 22",
        act="ustawa o PIT",
        description_pl="Kosztem uzyskania przychodu są wydatki poniesione w celu uzyskania przychodu, w tym prowizje brokerskie.",
        description_en="Cost of revenue includes expenses to obtain income, including broker commissions.",
        url="https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU19910800350",
    ),
    "dividend_19_percent": LegalRef(
        article="art. 30a ust. 1 pkt 4",
        act="ustawa o PIT",
        description_pl="Dochód z dywidend jest opodatkowany stawką 19%.",
        description_en="Dividend income is taxed at 19% flat rate.",
        url="https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU19910800350",
    ),
    "foreign_tax_credit": LegalRef(
        article="art. 30a ust. 9",
        act="ustawa o PIT",
        description_pl="Ulga za podatek zapłacony za granicą wynosi najmniejszą z następujących kwot: podatek zapłacony za granicą lub 19% przychodu × stawka traktatowa.",
        description_en="Foreign tax credit is the minimum of: tax paid abroad, or 19% of income × treaty rate.",
        url="https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU19910800350",
    ),
    "crypto_19_percent": LegalRef(
        article="art. 30b ust. 1a",
        act="ustawa o PIT",
        description_pl="Dochód ze zbycia kryptowalut jest opodatkowany stawką 19% (stosuje się art. 30b jak dla papierów wartościowych).",
        description_en="Capital gains from cryptocurrency sales are taxed at 19% (same as securities).",
        url="https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU19910800350",
    ),
    "loss_carry_forward": LegalRef(
        article="art. 9 ust. 3",
        act="ustawa o PIT",
        description_pl="Strata z lat ubiegłych może być stosowana przez 5 lat, jednak nie więcej niż 5 mln PLN rocznie.",
        description_en="Prior year losses can be carried forward for 5 years, but max 5M PLN per year.",
        url="https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU19910800350",
    ),
    "loss_5m_cap": LegalRef(
        article="art. 9 ust. 3",
        act="ustawa o PIT",
        description_pl="Limit 5 mln PLN rocznie przy przenoszeniu strat z lat ubiegłych.",
        description_en="Maximum 5M PLN annual deduction of prior losses.",
        url="https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU19910800350",
    ),
    "pit38_deadline": LegalRef(
        article="art. 45 ust. 1a pkt 1",
        act="ustawa o PIT",
        description_pl="PIT-38 należy złożyć do 30 kwietnia roku następującego po roku podatkowym.",
        description_en="PIT-38 must be filed by April 30th of the following year.",
        url="https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU19910800350",
    ),
    "grosz_rounding": LegalRef(
        article="art. 63 § 1",
        act="Ordynacja podatkowa",
        description_pl="Kwoty podatkowe zaokrąglić się do grosza (0,50 gr i więcej → w górę, poniżej 0,50 gr → w dół).",
        description_en="Tax amounts rounded to nearest grosz (0.01 PLN) with standard rounding rules.",
        url="https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU20191220000220",
    ),
    "czynny_zal": LegalRef(
        article="art. 16",
        act="Kodeks karny skarbowy",
        description_pl="Czynny żal — możliwość uzupełnienia podatku i uniknięcia sankcji w przypadku korekty.",
        description_en="Voluntary disclosure (czynny żal) allows correction before investigation to avoid penalties.",
        url="https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU199405420089",
    ),
    "treaty_pl_us": LegalRef(
        article="art. 13",
        act="Umowa o unikaniu podwójnego opodatkowania między Polską a USA (1974)",
        description_pl="Stawka traktatowa na dywidendy: 15% (z W-8BEN).",
        description_en="Treaty withholding rate on dividends: 15% (with W-8BEN form).",
        url="https://www.podatki.gov.pl/",
    ),
    "treaty_pl_de": LegalRef(
        article="art. 11",
        act="Umowa o unikaniu podwójnego opodatkowania między Polską a Niemcami (2005)",
        description_pl="Stawka traktatowa na dywidendy: 15%.",
        description_en="Treaty withholding rate on dividends: 15%.",
        url="https://www.podatki.gov.pl/",
    ),
    "treaty_pl_uk": LegalRef(
        article="art. 12",
        act="Umowa o unikaniu podwójnego opodatkowania między Polską a UK (2006)",
        description_pl="Stawka traktatowa na dywidendy: 10%.",
        description_en="Treaty withholding rate on dividends: 10%.",
        url="https://www.podatki.gov.pl/",
    ),
    "treaty_pl_fr": LegalRef(
        article="art. 12",
        act="Umowa o unikaniu podwójnego opodatkowania między Polską a Francją (1976)",
        description_pl="Stawka traktatowa na dywidendy: 15%.",
        description_en="Treaty withholding rate on dividends: 15%.",
        url="https://www.podatki.gov.pl/",
    ),
    "treaty_pl_ca": LegalRef(
        article="art. 12",
        act="Umowa o unikaniu podwójnego opodatkowania między Polską a Kanadą (2014)",
        description_pl="Stawka traktatowa na dywidendy: 15%.",
        description_en="Treaty withholding rate on dividends: 15%.",
        url="https://www.podatki.gov.pl/",
    ),
    "treaty_pl_nl": LegalRef(
        article="art. 12",
        act="Umowa o unikaniu podwójnego opodatkowania między Polską a Holandią (2003)",
        description_pl="Stawka traktatowa na dywidendy: 15%.",
        description_en="Treaty withholding rate on dividends: 15%.",
        url="https://www.podatki.gov.pl/",
    ),
}


def render_legal_legend(
    refs: List[str], lang: Language = "pl"
) -> None:
    """
    Render a Streamlit expander with legal references.

    Args:
        refs: List of reference keys from LEGAL_REFS
        lang: 'pl' or 'en'
    """
    import streamlit as st

    expander_title = "📖 Podstawa prawna" if lang == "pl" else "📖 Legal basis"

    with st.expander(expander_title):
        for ref_key in refs:
            if ref_key not in LEGAL_REFS:
                continue

            ref = LEGAL_REFS[ref_key]
            desc = ref.description_pl if lang == "pl" else ref.description_en

            st.markdown(f"**{ref.article}** — {ref.act}")
            st.markdown(f"> {desc}")
            if ref.url:
                st.markdown(f"🔗 [{ref.url}]({ref.url})")
            st.markdown("---")
