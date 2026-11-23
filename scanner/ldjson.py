"""Wspólne parsowanie danych schema.org (JSON-LD) ze stron wydarzeń."""
import html
import json
import re

LD_RE = re.compile(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.S | re.I)


def _walk(obj):
    if isinstance(obj, dict):
        if str(obj.get("@type", "")).endswith("Event"):
            yield obj
        for v in obj.values():
            if isinstance(v, (dict, list)):
                yield from _walk(v)
    elif isinstance(obj, list):
        for x in obj:
            yield from _walk(x)


def events(page: str):
    """Wszystkie obiekty *Event z JSON-LD strony (także zagnieżdżone)."""
    for block in LD_RE.findall(page):
        try:
            data = json.loads(html.unescape(block.strip()))
        except json.JSONDecodeError:
            continue
        yield from _walk(data)


def parse(ev: dict, url: str, source: str) -> dict | None:
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
    title = html.unescape((ev.get("name") or "").strip())
    artists = [html.unescape(p["name"]).strip() for p in perf
               if isinstance(p, dict) and p.get("name") and p["name"].strip() != title]
    img = ev.get("image")
    org = ev.get("organizer")
    return {
        "source": source,
        "title": title,
        "artists": artists,
        "date": start[:16],
        "date_to": None,
        "cities": [city] if city else [],
        "venue": html.unescape(loc.get("name") or "") or None,
        "venue_city": city,
        "genre": "muzyka" if ev.get("@type") == "MusicEvent" else "inne",
        "organizer": org.get("name") if isinstance(org, dict) else None,
        "url": ev.get("url") or url,
        "image": img[0] if isinstance(img, list) and img else img,
        "sold_out": "SoldOut" in json.dumps(ev.get("offers") or ""),
    }
