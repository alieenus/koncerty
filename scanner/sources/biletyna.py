"""Biletyna.pl: mapa strony z adresami koncertów + dane schema.org ze stron wydarzeń.

Adresy mają postać /koncert/<Artysta>/<Trasa>/<Miasto>, więc nazwę artysty znamy
jeszcze przed pobraniem strony. Strony pobieramy tylko dla artystów, którzy przeszli
filtr gwiazd (albo dla koncertów przy świecach), i trzymamy je w cache przez 3 dni.
"""
import re
import time
from collections import defaultdict
from typing import Callable

from .. import ldjson
from ..http import get

SITEMAP = "https://biletyna.pl/sitemap/sitemap-events.xml"
URL_RE = re.compile(r"https://biletyna\.pl/koncert/([^/]+)/([^/]+)/([^/<]+)$")
REFRESH = 3 * 86400


def slug_name(slug: str) -> str:
    return re.sub(r"\s+", " ", slug.replace("-", " ")).strip()


def fetch(cache: dict, wanted: Callable[[str], bool]) -> list[dict]:
    """cache: {url: {"t": czas, "events": [...]}}; wanted(nazwa) -> czy pobierać stronę."""
    xml = get(SITEMAP)
    by_artist: dict[str, list[str]] = defaultdict(list)
    for url in re.findall(r"<loc>([^<]+)</loc>", xml):
        m = URL_RE.match(url.strip())
        if m:
            by_artist[m.group(1)].append(url.strip())

    out, keep = [], set()
    now = time.time()
    print(f"Biletyna: {len(by_artist)} artystów w mapie strony", flush=True)
    for i, (slug, urls) in enumerate(by_artist.items(), 1):
        if i % 100 == 0:
            print(f"Biletyna: sprawdzono {i}/{len(by_artist)} artystów", flush=True)
        name = slug_name(slug)
        if not wanted(name):
            continue
        for url in urls:
            keep.add(url)
            c = cache.get(url)
            if not c or now - c.get("t", 0) > REFRESH:
                try:
                    page = get(url, min_interval=1.0)
                except RuntimeError:
                    continue
                evs = [e for e in (ldjson.parse(x, url, "Biletyna") for x in ldjson.events(page)) if e]
                for e in evs:
                    e["url"] = url  # link prowadzi do konkretnego miasta
                    e["artists"] = [name]  # nazwa z adresu jest najpewniejsza
                c = cache[url] = {"t": now, "events": evs}
            out.extend(c["events"])
    for url in list(cache):
        if url not in keep:
            del cache[url]
    return out
