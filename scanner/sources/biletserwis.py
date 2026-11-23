"""BiletSerwis.pl (m.in. Bocelli, Scorpions, James Blunt, PGE Narodowy).

Lista wydarzeń z publicznego REST API WordPressa, terminy ze strony wydarzenia
(<li> z datą, godziną i miejscem). Strony pobieramy tylko dla wydarzeń, których
wykonawca przeszedł filtr (jak w Biletynie); cache 3 dni.
"""
import html
import re
import time
from typing import Callable

from .. import enrich
from ..http import get, get_json

BASE = "https://biletserwis.pl"
REFRESH = 3 * 86400
MONTHS = {m: i for i, m in enumerate(
    ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia",
     "września", "października", "listopada", "grudnia"], 1)}
_ROW = re.compile(
    r'first-line">\s*(\d{1,2}) (\w+) (20\d\d)\s*</p>\s*<p class="last-line">[^<]*?(\d{1,2}:\d\d)?\s*</p>'
    r'.*?event-title">(.*?)</p>\s*<p class="event-location">(.*?)</p>', re.S)


def _t(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def parse_page(page: str, url: str) -> list[dict]:
    out = []
    for day, month, year, hm, title, loc in _ROW.findall(page):
        if month not in MONTHS:
            continue
        d = f"{year}-{MONTHS[month]:02d}-{int(day):02d}" + (f"T{int(hm.split(':')[0]):02d}:{hm.split(':')[1]}" if hm else "")
        loc = _t(loc)
        venue, _, city = loc.rpartition(",")
        city = city.strip() or None
        out.append({"source": "BiletSerwis", "title": _t(title), "artists": [], "date": d, "date_to": None,
                    "cities": [city] if city else [], "venue": venue.strip() or loc, "venue_city": city,
                    "genre": "inne", "organizer": None, "url": url, "image": None, "sold_out": False})
    return out


def fetch(cache: dict, wanted: Callable[[str], bool]) -> list[dict]:
    items, page = [], 1
    while page <= 20:
        try:
            batch = get_json(f"{BASE}/wp-json/wp/v2/events?per_page=100&page={page}&_fields=link,title",
                             min_interval=0.5)
        except RuntimeError:
            break  # WordPress zwraca 400 po ostatniej stronie
        if not batch:
            break
        items += batch
        page += 1
    print(f"BiletSerwis: {len(items)} wydarzeń w API", flush=True)

    out, keep, now = [], set(), time.time()
    for it in items:
        url = it.get("link")
        title = _t((it.get("title") or {}).get("rendered", ""))
        if not (url and title):
            continue
        names = enrich.guess_artists({"title": title, "artists": []})
        if not names or not wanted(names[0]):
            continue
        keep.add(url)
        c = cache.get(url)
        if not c or now - c.get("t", 0) > REFRESH:
            try:
                evs = parse_page(get(url, min_interval=1.0), url)
            except RuntimeError:
                continue
            c = cache[url] = {"t": now, "events": evs}
        out.extend(c["events"])
    for url in list(cache):
        if url not in keep:
            del cache[url]
    return out
