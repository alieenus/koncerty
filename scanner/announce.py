"""Czytanie zapowiedzi pisanych zwykłym tekstem (newsy organizatorów).

Z tekstu w stylu:
  „W naszym kraju artysta zaśpiewa 10 marca w Hali Stulecia we Wrocławiu.
   Przedsprzedaż rozpocznie się 7 września o godzinie 10:00. Sprzedaż ogólna: 9 września – godzina 10:00”
wyciąga terminy koncertów (data + miasto) oraz daty startu przedsprzedaży i sprzedaży.
"""
import re
from datetime import date

MONTHS = {m: i for i, m in enumerate(
    ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia",
     "września", "października", "listopada", "grudnia"], 1)}

# miasto w miejscowniku („w Łodzi”) albo mianowniku -> nazwa
CITIES = {
    "warszawa": "Warszawa", "warszawie": "Warszawa", "kraków": "Kraków", "krakowie": "Kraków",
    "łódź": "Łódź", "łodzi": "Łódź", "wrocław": "Wrocław", "wrocławiu": "Wrocław",
    "gdańsk": "Gdańsk", "gdańsku": "Gdańsk", "poznań": "Poznań", "poznaniu": "Poznań",
    "katowice": "Katowice", "katowicach": "Katowice", "gliwice": "Gliwice", "gliwicach": "Gliwice",
    "lublin": "Lublin", "lublinie": "Lublin", "toruń": "Toruń", "toruniu": "Toruń",
    "sopot": "Sopot", "sopocie": "Sopot", "gdynia": "Gdynia", "gdyni": "Gdynia",
    "szczecin": "Szczecin", "szczecinie": "Szczecin", "bydgoszcz": "Bydgoszcz", "bydgoszczy": "Bydgoszcz",
    "płock": "Płock", "płocku": "Płock", "rzeszów": "Rzeszów", "rzeszowie": "Rzeszów",
    "białystok": "Białystok", "białymstoku": "Białystok", "zabrze": "Zabrze", "zabrzu": "Zabrze",
    "chorzów": "Chorzów", "chorzowie": "Chorzów", "opole": "Opole", "opolu": "Opole",
    "kielce": "Kielce", "kielcach": "Kielce", "olsztyn": "Olsztyn", "olsztynie": "Olsztyn",
    "ostróda": "Ostróda", "ostródzie": "Ostróda", "radom": "Radom", "radomiu": "Radom",
    "zielona góra": "Zielona Góra", "zielonej górze": "Zielona Góra",
    "częstochowa": "Częstochowa", "częstochowie": "Częstochowa",
    "bielsko-biała": "Bielsko-Biała", "bielsku-białej": "Bielsko-Biała",
    "gorzów wielkopolski": "Gorzów Wielkopolski", "gorzowie wielkopolskim": "Gorzów Wielkopolski",
}
_CITY = re.compile(r"(?<![\wąćęłńóśźż])(" + "|".join(sorted(map(re.escape, CITIES), key=len, reverse=True))
                   + r")(?![\wąćęłńóśźż])", re.I)
_DATE = re.compile(r"(?<!\d)(\d{1,2})(?:\s+(" + "|".join(MONTHS) + r")|\.(\d{1,2})\.)(?:\s*(20\d\d)|(?<=\.)(20\d\d))?", re.I)
_TIME = re.compile(r"^\D{0,25}?(\d{1,2})[:.](\d\d)")
_SALE = re.compile(r"sprzeda|bilet[yów]* (?:trafi|będ|dostęp|w sprzeda)|w sprzedaży od|ruszy sprzeda|start sprzeda", re.I)
_PRESALE = re.compile(r"przedsprzeda|pre-?sale", re.I)
_OTHER = re.compile(r"premier|album|płyt|ukaż|singiel|utw[oó]r|teledysk|urodzi|zmar|wydan", re.I)


def _year(d: int, m: int, y: str | None, ref: date) -> int:
    if y:
        return int(y)
    year = ref.year
    try:
        if date(year, m, d) < ref.replace(day=1):
            year += 1
    except ValueError:
        pass
    return year


def parse(text: str, ref: date | None = None) -> dict:
    """Zwraca {"dates": [(iso, miasto|None)], "onsale": iso|None, "presale": iso|None}."""
    ref = ref or date.today()
    text = re.sub(r"\s+", " ", text)
    out = {"dates": [], "onsale": None, "presale": None}
    for sent in re.split(r"(?<=[.!?])\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ0-9„\"])", text):
        cities = [(m.start(), CITIES[m.group(1).lower()]) for m in _CITY.finditer(sent)]
        for m in _DATE.finditer(sent):
            d = int(m.group(1))
            mon = MONTHS[m.group(2).lower()] if m.group(2) else int(m.group(3))
            if not (1 <= d <= 31 and 1 <= mon <= 12):
                continue
            y = _year(d, mon, m.group(4) or m.group(5), ref)
            iso = f"{y}-{mon:02d}-{d:02d}"
            before = sent[max(0, m.start() - 90):m.start()]
            tm = _TIME.match(sent[m.end():])
            if _SALE.search(before) or _PRESALE.search(before):
                if tm:
                    iso += f"T{int(tm.group(1)):02d}:{tm.group(2)}"
                key = "presale" if _PRESALE.search(before[-60:]) else "onsale"
                if not out[key] or iso < out[key]:
                    out[key] = iso
                continue
            if _OTHER.search(before[-50:]):
                continue
            after = [c for p, c in cities if p > m.start()]
            prior = [c for p, c in cities if p < m.start()]
            city = after[0] if after else (prior[-1] if prior else None)
            if (iso, city) not in out["dates"]:
                out["dates"].append((iso, city))
    return out
