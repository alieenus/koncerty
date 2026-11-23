"""Line-upy z oficjalnych stron festiwali.

Strony festiwali są różne, więc zamiast pisać parser pod każdą zbieramy
„kandydatów” na nazwy artystów (nagłówki, elementy z klasą title/name/artist,
linki do podstron artystów), a dopiero filtr gwiazd (MusicBrainz + Deezer)
decyduje, kto jest prawdziwym wykonawcą. Daty festiwalu bierzemy z ogłoszenia
na stronie (np. „30.06 - 3.07.2027”) albo z wydarzenia w serwisach biletowych.
"""
import html
import re
from html.parser import HTMLParser

from ..http import get

DEFAULT_SITES = [
    {"name": "Open'er Festival", "url": "https://opener.pl/", "city": "Gdynia"},
    {"name": "Orange Warsaw Festival", "url": "https://orangewarsawfestival.pl/", "city": "Warszawa"},
    {"name": "OFF Festival", "url": "https://off-festival.pl/line-up/", "city": "Katowice"},
    {"name": "Audioriver", "url": "https://audioriver.pl/", "city": "Płock"},
    {"name": "Mystic Festival", "url": "https://mysticfestival.pl/", "city": "Gdańsk"},
    {"name": "Tauron Nowa Muzyka", "url": "https://nowamuzyka.pl/", "city": "Katowice"},
]

STOP = re.compile(
    r"^(bilety?|kup bilet|newsletter|news|aktualno|artyści|artysci|artists?|line-?up|program|partner|sponsor|"
    r"kontakt|faq|regulamin|polityka|cookies|zapisz|więcej|wiecej|menu|eng?|pl|home|strona główna|media|"
    r"gospodarz|scena|dzień|sortuj|brak wyników|informacje|mapa|dojazd)", re.I)
CLASS_HINT = re.compile(r"title|name|artist|artyst|headliner|performer|lineup|line-up", re.I)
LINK_HINT = re.compile(r"/(artyst|artist|wykonawc|lineup/|line-up/)[^\"']+", re.I)
MONTHS = {m: i for i, m in enumerate(
    ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia",
     "września", "października", "listopada", "grudnia"], 1)}


class _Collector(HTMLParser):
    LEAFY = {"h1", "h2", "h3", "h4", "h5", "a", "div", "span", "p", "li", "strong", "b"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.found, self.skip = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip += 1
            return
        if tag in ("br", "img", "input", "meta", "link", "hr", "source"):
            return
        a = dict(attrs)
        hit = tag in ("h1", "h2", "h3", "h4") or CLASS_HINT.search(a.get("class") or "") \
            or (tag == "a" and LINK_HINT.search(a.get("href") or ""))
        self.stack.append([tag, bool(hit), []])

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip = max(0, self.skip - 1)
            return
        while self.stack:
            t, hit, buf = self.stack.pop()
            text = re.sub(r"\s+", " ", "".join(buf)).strip()
            if hit and text:
                self.found.append(text)
            if self.stack:
                self.stack[-1][2].append(" " + text + " ")
            if t == tag:
                break

    def handle_data(self, data):
        if not self.skip and self.stack:
            self.stack[-1][2].append(data)


def candidates(page: str) -> list[str]:
    c = _Collector()
    try:
        c.feed(page)
    except Exception:
        pass
    out = []
    for t in c.found:
        t = html.unescape(t).strip(" -–|•·,")
        if 2 <= len(t) <= 40 and not STOP.match(t) and not re.search(r"\d{3,}|[!?]|https?:", t) \
                and t not in out:
            out.append(t)
    return out[:200]


_RANGE = re.compile(r"(\d{1,2})(?:\.(\d{1,2}))?\s*[-–]\s*(\d{1,2})\.(\d{1,2})\.(20\d\d)")
_RANGE_PL = re.compile(r"(\d{1,2})\s*[-–]\s*\d{1,2}\s+(" + "|".join(MONTHS) + r")\s+(20\d\d)", re.I)


def festival_date(text: str) -> str | None:
    m = _RANGE.search(text)
    if m:
        d1, m1, _, m2, y = m.groups()
        return f"{y}-{int(m1 or m2):02d}-{int(d1):02d}"
    m = _RANGE_PL.search(text)
    if m:
        return f"{m.group(3)}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    return None


def fetch(sites: list[dict]) -> list[dict]:
    out = []
    for s in sites:
        try:
            page = get(s["url"], min_interval=1.0)
        except RuntimeError as e:
            print(f"  {s['name']}: błąd {e}", flush=True)
            continue
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", re.sub(
            r"<(script|style)[^>]*>.*?</\1>", " ", page, flags=re.S | re.I))))
        cands = candidates(page)
        print(f"  {s['name']}: {len(cands)} kandydatów", flush=True)
        out.append({"name": s["name"], "url": s["url"], "city": s.get("city"),
                    "date": festival_date(text), "candidates": cands})
    return out
