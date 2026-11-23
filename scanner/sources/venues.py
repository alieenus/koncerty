"""Kalendarze dużych hal: tam gwiazdy pojawiają się czasem przed startem sprzedaży.

- Tauron Arena Kraków: WordPress + The Events Calendar (publiczne REST API),
- Spodek Katowice: lista wydarzeń na stronie (data + tytuł + link).
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


def fetch() -> list[dict]:
    out, errors = [], []
    for fn in (tauron, spodek):
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
