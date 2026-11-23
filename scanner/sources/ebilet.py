"""eBilet.pl: publiczne JSON API, z którego korzysta ich strona.

Jedno zapytanie zwraca wszystkie tytuły z kategorii „muzyka” (ok. 800).
"""
from ..http import get_json

URL = "https://www.ebilet.pl/api/TitleListing/Search?category=muzyka&size=3000"

# Podkategorie eBilet -> nasze gatunki
GENRES = {
    "pop": "pop", "rock": "rock", "hip-hop-rap": "hip-hop", "elektro-techno": "elektronika",
    "hard-heavy": "metal", "jazz-blues": "jazz", "k-pop": "k-pop", "r-b-soul": "r&b",
    "alternatywa": "alternatywa", "festiwale": "festiwal", "reggae": "reggae",
    "folk-country": "folk", "punk": "punk", "ethno": "world", "piosenka": "piosenka",
}

SKIP_SUBCATS = {"pozostale", "disco-polo"}


def fetch() -> list[dict]:
    data = get_json(URL)
    out = []
    for t in data.get("titles", []):
        if t.get("category") != "muzyka" or t.get("subcategory") in SKIP_SUBCATS:
            continue
        if not t.get("dateFrom"):
            continue  # vouchery, karty podarunkowe itp.
        nxt = t.get("nextEventPlace") or {}
        cities = [c.strip() for c in (t.get("place") or "").split(",") if c.strip()]
        out.append({
            "source": "eBilet",
            "title": (t.get("title") or "").strip(),
            "artists": [a.strip() for a in (t.get("artists") or []) if a and a.strip()],
            "date": t["dateFrom"][:16],
            "date_to": (t.get("dateTo") or "")[:16] or None,
            "cities": cities,
            "venue": nxt.get("customName"),
            "venue_city": nxt.get("city"),
            "genre": GENRES.get(t.get("subcategory"), t.get("subcategoryName") or "inne"),
            "organizer": (t.get("organizer") or {}).get("name"),
            "url": t.get("linkTo") or f"https://www.ebilet.pl/{t['category']}/{t['subcategory']}/{t['slug']}",
            "image": t.get("imagePortrait") or t.get("imageLandscape"),
            "sold_out": bool(t.get("soldOut")),
        })
    return out
