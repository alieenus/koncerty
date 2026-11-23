"""Ticketmaster Polska (obejmuje Live Nation PL): oficjalne Discovery API.

Wymaga darmowego klucza z https://developer.ticketmaster.com (zmienna TM_API_KEY).
Bez klucza źródło jest pomijane.
"""
import os
import urllib.parse

from ..http import get_json

BASE = "https://app.ticketmaster.com/discovery/v2/events.json"

GENRES = {
    "Pop": "pop", "Rock": "rock", "Hip-Hop/Rap": "hip-hop", "Dance/Electronic": "elektronika",
    "Metal": "metal", "R&B": "r&b", "Jazz": "jazz", "Alternative": "alternatywa",
    "Country": "folk", "Reggae": "reggae", "Latin": "latin", "Classical": "klasyka",
}


def fetch() -> list[dict]:
    key = os.environ.get("TM_API_KEY")
    if not key:
        return []
    out = []
    page = 0
    while page < 5:  # API pozwala na max 1000 wyników (5 x 200)
        q = urllib.parse.urlencode({
            "apikey": key, "countryCode": "PL", "classificationName": "music",
            "size": 200, "page": page, "sort": "date,asc",
        })
        data = get_json(f"{BASE}?{q}", min_interval=0.25)
        for e in (data.get("_embedded") or {}).get("events", []):
            start = (e.get("dates") or {}).get("start") or {}
            date = start.get("dateTime") or start.get("localDate")
            if not date:
                continue
            if start.get("localDate") and start.get("localTime"):
                date = f"{start['localDate']}T{start['localTime'][:5]}"
            venues = (e.get("_embedded") or {}).get("venues") or [{}]
            v = venues[0]
            city = (v.get("city") or {}).get("name")
            attractions = (e.get("_embedded") or {}).get("attractions") or []
            cls = (e.get("classifications") or [{}])[0]
            genre = (cls.get("genre") or {}).get("name")
            imgs = sorted(e.get("images") or [], key=lambda i: -(i.get("width") or 0))
            out.append({
                "source": "Ticketmaster",
                "title": e.get("name", "").strip(),
                "artists": [a["name"] for a in attractions if a.get("name")],
                "date": date[:16],
                "date_to": None,
                "cities": [city] if city else [],
                "venue": v.get("name"),
                "venue_city": city,
                "genre": GENRES.get(genre, (genre or "inne").lower()),
                "organizer": (e.get("promoter") or {}).get("name"),
                "url": e.get("url"),
                "image": imgs[0]["url"] if imgs else None,
                "sold_out": (e.get("dates") or {}).get("status", {}).get("code") == "offsale",
            })
        info = data.get("page") or {}
        page += 1
        if page >= info.get("totalPages", 0):
            break
    return out
