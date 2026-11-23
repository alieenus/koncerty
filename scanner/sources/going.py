"""Going. (goingapp.pl): mapa strony z wydarzeniami + dane schema.org (JSON-LD) z każdej strony.

Strony wydarzeń pobieramy tylko, gdy są nowe albo zmieniła się ich data `lastmod`,
więc kolejne skany wykonują zaledwie kilka zapytań.
"""
import html
import json
import re

from ..http import get

SITEMAP = "https://goingapp.pl/sitemap_events.xml"
SKIP_WORDS = re.compile(r"voucher|karta-podarunkowa|motylarnia|wystawa|warsztat", re.I)
LD_RE = re.compile(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.S | re.I)


def _events_from_ld(page: str):
    for block in LD_RE.findall(page):
        try:
            data = json.loads(html.unescape(block.strip()))
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data])
        for it in items:
            if isinstance(it, dict) and str(it.get("@type", "")).endswith("Event"):
                yield it


def _parse(ev: dict, url: str) -> dict | None:
    start = ev.get("startDate")
    if not start:
        return None
    loc = ev.get("location") or {}
    if isinstance(loc, list):
        loc = loc[0] if loc else {}
    addr = loc.get("address") or {}
    city = addr.get("addressLocality") if isinstance(addr, dict) else None
    perf = ev.get("performer") or []
    if isinstance(perf, dict):
        perf = [perf]
    artists = [p.get("name", "").strip() for p in perf if isinstance(p, dict) and p.get("name")]
    img = ev.get("image")
    return {
        "source": "Going.",
        "title": html.unescape((ev.get("name") or "").strip()),
        "artists": artists,
        "date": start[:16],
        "date_to": None,
        "cities": [city] if city else [],
        "venue": loc.get("name"),
        "venue_city": city,
        "genre": "muzyka" if ev.get("@type") == "MusicEvent" else "inne",
        "organizer": (ev.get("organizer") or {}).get("name") if isinstance(ev.get("organizer"), dict) else None,
        "url": ev.get("url") or url,
        "image": img[0] if isinstance(img, list) and img else img,
        "sold_out": "SoldOut" in json.dumps(ev.get("offers") or ""),
    }


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
            evs = [e for e in (_parse(x, url) for x in _events_from_ld(page)) if e]
            # zostawiamy tylko koncerty (MusicEvent albo strony z /koncert w adresie)
            evs = [e for e in evs if e["genre"] == "muzyka" or "koncert" in url]
            c = cache[url] = {"lastmod": lastmod, "events": evs}
        out.extend(c["events"])
    for url in list(cache):
        if url not in seen:
            del cache[url]
    return out
