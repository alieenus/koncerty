"""Going. (goingapp.pl): mapa strony z wydarzeniami + dane schema.org (JSON-LD) z każdej strony.

Strony wydarzeń pobieramy tylko, gdy są nowe albo zmieniła się ich data `lastmod`,
więc kolejne skany wykonują zaledwie kilka zapytań.
"""
import re

from .. import ldjson
from ..http import get

SITEMAP = "https://goingapp.pl/sitemap_events.xml"
SKIP_WORDS = re.compile(r"voucher|karta-podarunkowa|motylarnia|wystawa|warsztat", re.I)


def fetch(cache: dict) -> list[dict]:
    """cache: {url: {"lastmod": str, "events": [...]}} – modyfikowany w miejscu."""
    xml = get(SITEMAP)
    entries = re.findall(r"<url>\s*<loc>([^<]+)</loc>(?:\s*<lastmod>([^<]+)</lastmod>)?", xml)
    seen = set()
    out = []
    for url, lastmod in entries:
        if SKIP_WORDS.search(url):
            continue
        seen.add(url)
        c = cache.get(url)
        if not c or c.get("lastmod") != lastmod:
            try:
                page = get(url, min_interval=1.0)
            except RuntimeError:
                continue
            evs = [e for e in (ldjson.parse(x, url, "Going.") for x in ldjson.events(page)) if e]
            # zostawiamy tylko koncerty (MusicEvent albo strony z /koncert w adresie)
            evs = [e for e in evs if e["genre"] == "muzyka" or "koncert" in url]
            c = cache[url] = {"lastmod": lastmod, "events": evs}
        out.extend(c["events"])
    for url in list(cache):
        if url not in seen:
            del cache[url]
    return out
