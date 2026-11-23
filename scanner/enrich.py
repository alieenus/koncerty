"""Ustalanie, kim jest artysta: kraj (MusicBrainz) i popularność (fani na Deezerze).

Wyniki trafiają do cache (data/artists.json), więc każdego artystę sprawdzamy raz
na `CACHE_DAYS` dni.
"""
import re
import time
import unicodedata
import urllib.parse

from .http import get_json

CACHE_DAYS = 30

# Słowa, po których w tytule zaczyna się już nazwa trasy, a nie wykonawca.
_CUT = re.compile(
    r"\s*[:|•]\s|\s+[-–—]\s|\s+(?:„|\"|\(|w ramach|tour\b|world tour|live\b|na żywo|koncert\b|"
    r"\d{4}\b|europe\b|polska\b|special guest|support|\+|feat\.|&\s*goście)",
    re.I,
)
_PREFIX = re.compile(r"^(?:koncert|recital|wieczór z|spotkanie z)\s+", re.I)


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"^the\s+", "", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def guess_artists(ev: dict) -> list[str]:
    if ev.get("artists"):
        return ev["artists"][:3]
    t = _PREFIX.sub("", ev["title"]).strip()
    m = _CUT.search(t)
    if m and m.start() > 1:
        t = t[: m.start()]
    t = t.strip(" -–—:|,.")
    return [t] if t else []


def _musicbrainz(name: str, ua: str) -> dict:
    q = urllib.parse.urlencode({"query": f'artist:"{name}"', "fmt": "json", "limit": 5})
    data = get_json(f"https://musicbrainz.org/ws/2/artist?{q}", ua=ua, min_interval=1.1)
    for a in data.get("artists", []):
        if a.get("score", 0) < 90 or norm(a.get("name", "")) != norm(name):
            continue
        country = a.get("country") or ((a.get("area") or {}).get("iso-3166-1-codes") or [None])[0]
        tags = sorted(a.get("tags") or [], key=lambda t: -t.get("count", 0))
        return {"country": country, "mbid": a.get("id"),
                "tags": [t["name"] for t in tags[:5]]}
    return {"country": None, "mbid": None, "tags": []}


def _deezer(name: str) -> dict:
    q = urllib.parse.quote(name)
    data = get_json(f"https://api.deezer.com/search/artist?q={q}&limit=5", min_interval=0.2)
    best = None
    for a in data.get("data", []):
        if norm(a.get("name", "")) == norm(name):
            if not best or a.get("nb_fan", 0) > best.get("nb_fan", 0):
                best = a
    if not best:
        return {"fans": 0, "picture": None, "deezer": None}
    return {"fans": best.get("nb_fan", 0), "picture": best.get("picture_medium"),
            "deezer": best.get("link")}


def lookup(name: str, cache: dict, ua: str) -> dict:
    key = norm(name)
    hit = cache.get(key)
    if hit and time.time() - hit.get("checked", 0) < CACHE_DAYS * 86400:
        return hit
    info = {"name": name, "checked": time.time()}
    try:
        info.update(_musicbrainz(name, ua))
    except RuntimeError:
        info.update({"country": None, "mbid": None, "tags": []})
    try:
        info.update(_deezer(name))
    except RuntimeError:
        info.update({"fans": 0, "picture": None, "deezer": None})
    cache[key] = info
    return info
