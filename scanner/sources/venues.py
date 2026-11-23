"""Kalendarze dużych hal: tam gwiazdy pojawiają się czasem przed startem sprzedaży.

- Tauron Arena Kraków: WordPress + The Events Calendar (publiczne REST API),
- Spodek Katowice: lista wydarzeń na stronie (data + tytuł + link),
- PGE Narodowy: kalendarz miesięczny (calendar-graphic.php), 18 miesięcy do przodu,
- Atlas Arena Łódź: lista wydarzeń (dzień.miesiąc bez roku; rok z kolejności).
"""
import html
import re
import urllib.parse
from datetime import date

from ..http import get, get_json

MONTHS = {m: i for i, m in enumerate(
    ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia",
     "września", "października", "listopada", "grudnia"], 1)}


def _ev(source, title, d, url, venue, city, image=None):
    return {"source": source, "title": title, "artists": [], "date": d, "date_to": None,
            "cities": [city], "venue": venue, "venue_city": city, "genre": "inne",
            "organizer": None, "url": url, "image": image, "sold_out": False}


def tauron() -> list[dict]:
    out, page = [], 1
    while page <= 10:
        q = urllib.parse.urlencode({"per_page": 50, "page": page, "start_date": date.today().isoformat()})
        data = get_json(f"https://www.tauronarenakrakow.pl/wp-json/tribe/events/v1/events?{q}", min_interval=0.5)
        for e in data.get("events", []):
            title = html.unescape(re.sub(r"<[^>]+>", "", e.get("title", ""))).strip()
            start = (e.get("start_date") or "").replace(" ", "T")[:16]
            if not (title and start):
                continue
            img = e.get("image") or {}
            out.append(_ev("Tauron Arena", title, start, e.get("url"), "Tauron Arena Kraków", "Kraków",
                           img.get("url") if isinstance(img, dict) else None))
        if page >= int(data.get("total_pages") or 1):
            break
        page += 1
    return out


SPODEK = "https://www.spodekkatowice.pl/pl/wydarzenia/61/"
_DATE = re.compile(r"(\d{1,2})(?:-\d{1,2})? (" + "|".join(MONTHS) + r") (20\d\d)")


def _text(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def spodek() -> list[dict]:
    page = get(SPODEK)
    page = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", page, flags=re.S | re.I)
    links = {}
    for href, inner in re.findall(r'<a[^>]+href="([^"]*/pl/wydarzenia/[^"]+,\d+\.html)"[^>]*>(.*?)</a>', page, re.S):
        t = _text(inner)
        if t:
            links[t.lower()] = href if href.startswith("http") else "https://www.spodekkatowice.pl" + href
    text = _text(page)
    out = []
    parts = _DATE.split(text)
    # split daje: [przed, dzień, miesiąc, rok, treść, dzień, miesiąc, rok, treść, ...]
    for i in range(1, len(parts) - 3, 4):
        day, month, year, rest = parts[i], parts[i + 1], parts[i + 2], parts[i + 3]
        title = re.split(r"\s+Bilety od:|\s+(?:LISTOPAD|GRUDZIEŃ|STYCZEŃ|LUTY|MARZEC|KWIECIEŃ|MAJ|CZERWIEC|LIPIEC|"
                         r"SIERPIEŃ|WRZESIEŃ|PAŹDZIERNIK) 20\d\d", rest)[0].strip(" |")
        if not title or len(title) > 150 or title.upper().startswith("ODWOŁANY"):
            continue
        d = f"{year}-{MONTHS[month]:02d}-{int(day):02d}"
        url = next((u for t, u in links.items() if title.lower()[:25] in t or t[:25] in title.lower()), SPODEK)
        out.append(_ev("Spodek", title, d, url, "Spodek", "Katowice"))
    return out


PGE = "https://www.pgenarodowy.pl"
_PGE_BLOCK = re.compile(
    r'modal-body-event.*?href="(/strony-dodatkowe/wydarzenia/[^"]+)".*?calendar-modal--title">(.*?)</span>'
    r'.*?calendar-modal--date">(.*?)</span>(?:\s*<span class="calendar-modal--time">(.*?)</span>)?', re.S)


def pge() -> list[dict]:
    today = date.today()
    out, seen = [], set()
    for i in range(18):
        m0 = today.month - 1 + i
        y, m = today.year + m0 // 12, m0 % 12 + 1
        page = get(f"{PGE}/calendar/calendar-graphic.php?month={m}&year={y}", min_interval=0.5)
        for href, title, d, t in _PGE_BLOCK.findall(page):
            title = _text(title)
            dm = _DATE.search(_text(d))
            if not (title and dm):
                continue
            day, month, year = dm.groups()
            iso = f"{year}-{MONTHS[month]:02d}-{int(day):02d}"
            tm = re.search(r"(\d{1,2}):(\d\d)", t or "")
            if tm:
                iso += f"T{int(tm.group(1)):02d}:{tm.group(2)}"
            key = (href, iso[:10])
            if key in seen:  # wydarzenie wielodniowe / wersja mobilna – raz na dzień
                continue
            seen.add(key)
            out.append(_ev("PGE Narodowy", title, iso, PGE + href, "PGE Narodowy", "Warszawa"))
    return out


ATLAS = "https://atlasarena.pl/wydarzenia/"
_ATLAS_ITEM = re.compile(
    r'eventsmain__center__item__title__day">\s*(\d{1,2})\.(\d{1,2})\s*</span>\s*<a href="([^"]+)">\s*<h3>(.*?)</h3>', re.S)


def atlas() -> list[dict]:
    page = get(ATLAS)
    today = date.today()
    year, last = today.year, (today.month, 0)
    out = []
    for d, m, url, title in _ATLAS_ITEM.findall(page):
        md = (int(m), int(d))
        if md < last and (last[0] - md[0]) > 2:  # lista jest chronologiczna: spadek miesiąca = nowy rok
            year += 1
        last = md
        out.append(_ev("Atlas Arena", _text(title), f"{year}-{md[0]:02d}-{md[1]:02d}", url, "Atlas Arena", "Łódź"))
    return out


def fetch() -> list[dict]:
    out, errors = [], []
    for fn in (tauron, spodek, pge, atlas):
        try:
            got = fn()
            print(f"  {fn.__name__}: {len(got)}", flush=True)
            out.extend(got)
        except Exception as e:
            errors.append(f"{fn.__name__}: {e}")
            print(f"  {fn.__name__}: błąd {e}", flush=True)
    if errors and not out:
        raise RuntimeError("; ".join(errors))
    return out
