"""Skaner koncertów zagranicznych gwiazd w Polsce.

Uruchomienie:  python3 -m scanner.main            (z katalogu głównego repo)
Wynik:         web/data/concerts.json  (czyta go strona)
Stan:          data/  (cache artystów, Going, lista już widzianych koncertów)
"""
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from . import enrich, filters, notify
from .sources import biletyna, ebilet, going, ticketmaster

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("KONCERTY_DATA", ROOT / "data"))
OUT = Path(os.environ.get("KONCERTY_OUT", ROOT / "web" / "data" / "concerts.json"))


def load(path: Path, default):
    try:
        return json.loads(path.read_text("utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), "utf-8")
    tmp.replace(path)


def load_config() -> dict:
    cfg = load(ROOT / "config.json", {})
    cfg.setdefault("min_fans", 100000)
    cfg.setdefault("candlelight", True)
    cfg.setdefault("min_fans_unknown_country", 500000)
    cfg["force_foreign"] = {x.lower() for x in cfg.get("force_foreign", [])}
    cfg["force_polish"] = {x.lower() for x in cfg.get("force_polish", [])}
    cfg["watchlist"] = cfg.get("watchlist", [])
    cfg.setdefault("musicbrainz_user_agent", "koncerty-scanner/1.0 (prywatny projekt)")
    return cfg


def event_key(artist: str, ev: dict) -> str:
    city = enrich.norm(ev.get("venue_city") or (ev["cities"][0] if ev["cities"] else ""))
    return f"{enrich.norm(artist)}|{ev['date'][:10]}|{city}"


def add_candle(merged: dict, ev: dict):
    """Koncert przy świecach: bez sprawdzania artysty, jako osobny gatunek."""
    city = ev.get("venue_city") or (ev["cities"][0] if ev["cities"] else "")
    k = f"swiece:{enrich.norm(ev['title'])}|{ev['date'][:10]}|{enrich.norm(city)}"
    m = merged.setdefault(k, {
        "id": k, "artist": ev["title"], "country": None, "fans": 0, "picture": ev.get("image"),
        "tags": [], "title": ev["title"], "date": ev["date"], "date_to": ev.get("date_to"),
        "cities": ev["cities"], "venue": ev.get("venue"), "venue_city": ev.get("venue_city"),
        "genre": "przy świecach", "candle": True, "links": [], "sold_out": ev["sold_out"],
    })
    if all(l["url"] != ev["url"] for l in m["links"]):
        m["links"].append({"source": ev["source"], "url": ev["url"]})


def run() -> int:
    cfg = load_config()
    artists_cache = load(DATA / "artists.json", {})
    going_cache = load(DATA / "going_cache.json", {})
    seen = load(DATA / "seen.json", {})
    status = {}

    biletyna_cache = load(DATA / "biletyna_cache.json", {})

    def wanted(name: str) -> bool:
        """Czy warto pobierać szczegóły: gwiazda z zagranicy albo koncert przy świecach."""
        if cfg["candlelight"] and filters.is_candle({"title": name}):
            return True
        if filters.is_fake({"title": name}):
            return False
        a = enrich.lookup(name, artists_cache, cfg["musicbrainz_user_agent"])
        return filters.is_star(a, filters.classify(a, cfg), cfg)

    raw: list[dict] = []
    sources = [("eBilet", ebilet.fetch), ("Biletyna", lambda: biletyna.fetch(biletyna_cache, wanted)),
               ("Ticketmaster", ticketmaster.fetch)]
    if cfg.get("going", False):  # wyłączone: strony Going. renderują dane w przeglądarce (do poprawy)
        sources.insert(1, ("Going.", lambda: going.fetch(going_cache)))
    for name, fn in sources:
        t0 = time.time()
        try:
            got = fn()
            raw.extend(got)
            status[name] = {"ok": True, "count": len(got), "seconds": round(time.time() - t0, 1)}
        except Exception as e:  # jedno źródło nie może zatrzymać całego skanu
            traceback.print_exc()
            status[name] = {"ok": False, "error": str(e)[:200]}
        print(f"{name}: {status[name]}", flush=True)
    save(DATA / "going_cache.json", going_cache)
    save(DATA / "biletyna_cache.json", biletyna_cache)
    save(DATA / "artists.json", artists_cache)

    today = datetime.now().strftime("%Y-%m-%d")
    merged: dict[str, dict] = {}
    checked = 0
    for ev in raw:
        if ev["date"][:10] < today:
            continue
        if cfg["candlelight"] and filters.is_candle(ev):
            add_candle(merged, ev)
            continue
        if filters.is_fake(ev):
            continue
        checked += 1
        if checked % 50 == 0:
            print(f"Sprawdzono {checked}/{len(raw)} wydarzeń, artystów w bazie: {len(artists_cache)}", flush=True)
        for name in enrich.guess_artists(ev):
            a = enrich.lookup(name, artists_cache, cfg["musicbrainz_user_agent"])
            kind = filters.classify(a, cfg)
            if not filters.is_star(a, kind, cfg):
                continue
            k = event_key(name, ev)
            m = merged.get(k)
            if m is None:
                m = merged[k] = {
                    "id": k, "artist": a.get("name", name), "country": a.get("country"),
                    "fans": a.get("fans", 0), "picture": a.get("picture") or ev.get("image"),
                    "tags": a.get("tags", []), "title": ev["title"], "date": ev["date"],
                    "date_to": ev.get("date_to"), "cities": ev["cities"], "venue": ev.get("venue"),
                    "venue_city": ev.get("venue_city"), "genre": ev["genre"], "links": [],
                    "sold_out": ev["sold_out"],
                }
            if all(l["url"] != ev["url"] for l in m["links"]):
                m["links"].append({"source": ev["source"], "url": ev["url"]})
            if not m.get("venue") and ev.get("venue"):
                m["venue"] = ev["venue"]
            if m["genre"] in ("inne", "muzyka") and ev["genre"] not in ("inne", "muzyka"):
                m["genre"] = ev["genre"]
            break  # pierwszy rozpoznany wykonawca = główna gwiazda
        if checked % 50 == 0:
            save(DATA / "artists.json", artists_cache)  # postęp przetrwa przerwanie skanu
    save(DATA / "artists.json", artists_cache)

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    first_run = not seen
    new = []
    for k, m in merged.items():
        if k not in seen:
            seen[k] = now
            if not first_run:
                new.append(m)
        m["first_seen"] = seen[k]
    # zapominamy koncerty, które już się odbyły
    seen = {k: v for k, v in seen.items() if k.split("|")[1] >= today}
    save(DATA / "seen.json", seen)

    concerts = sorted(merged.values(), key=lambda m: m["date"])
    save(OUT, {"updated": now, "sources": status, "count": len(concerts), "concerts": concerts})
    print(f"Zapisano {len(concerts)} koncertów, nowych: {len(new)}", flush=True)

    notify.send_new(new, cfg)
    return 0 if any(s.get("ok") for s in status.values()) else 1


if __name__ == "__main__":
    sys.exit(run())
