"""Zapowiedzi prosto od organizatorów: koncerty pojawiają się tu w dniu ogłoszenia,
często kilka dni przed startem sprzedaży, razem z datami przedsprzedaży.

- Live Nation Polska: JSON z wyszukiwarki strony (/__api/search/events), z datą ogłoszenia
  i datami sprzedaży/przedsprzedaży; bilety idą przez Ticketmaster,
- Alter Art: lista wydarzeń na stronie głównej,
- Knock Out Productions: lista /pl/concert (kilka stron),
- Prestige MJM: WordPress REST (nadchodzące koncerty), daty czytane z tekstu zapowiedzi,
- Good Taste Production: WordPress REST (wpisy) + strona wydarzenia.
"""
import html
import re
from datetime import date, datetime, timezone

from .. import announce
from ..http import get, get_json

try:
    from zoneinfo import ZoneInfo
    _PL = ZoneInfo("Europe/Warsaw")
except Exception:  # brak bazy stref czasowych
    _PL = None


def _text(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def _local(utc: str | None) -> str | None:
    """'2026-11-20T11:00:00Z' -> '2026-11-20T12:00' (czas polski)."""
    if not utc or utc.startswith("0001"):
        return None
    try:
        dt = datetime.fromisoformat(utc.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(_PL).strftime("%Y-%m-%dT%H:%M") if _PL else dt.strftime("%Y-%m-%dT%H:%M")
    except ValueError:
        return None


def _ev(source, title, d, url, venue=None, city=None, **extra):
    e = {"source": source, "title": title, "artists": [], "date": d, "date_to": None,
         "cities": [city] if city else [], "venue": venue, "venue_city": city, "genre": "inne",
         "organizer": source, "url": url, "image": None, "sold_out": False}
    e.update({k: v for k, v in extra.items() if v is not None})
    return e


# ---------------------------------------------------------------- Live Nation
LN = "https://www.livenation.pl"
LN_CITY = {"warsaw": "Warszawa", "lodz": "Łódź", "lódz": "Łódź", "łódź": "Łódź", "krakow": "Kraków",
           "kraków": "Kraków", "gdansk": "Gdańsk", "poznan": "Poznań", "wroclaw": "Wrocław",
           "plock": "Płock", "suwalki": "Suwałki", "bielsko-biala": "Bielsko-Biała", "torun": "Toruń",
           "chorzow": "Chorzów", "rzeszow": "Rzeszów", "bialystok": "Białystok"}
LN_GENRE = {"pop": "pop", "rock": "rock", "electronic": "elektronika", "hip-hop-and-rap": "hip-hop",
            "alternative-and-indie": "alternatywa", "rnb-and-soul": "r&b", "hard-rock-and-metal": "metal",
            "reggae": "reggae", "country": "folk", "jazz-and-blues": "jazz"}


def livenation() -> list[dict]:
    out, page, total = [], 1, None
    while page <= 30:
        d = get_json(f"{LN}/__api/search/events?culture=pl-PL&page={page}", min_interval=0.5)
        docs = d.get("documents") or []
        total = d.get("total") or 0
        for e in docs:
            if e.get("isDeleted"):
                continue
            keys = {g.get("key") for g in e.get("genres") or []}
            if keys and keys <= {"comedy", "sport"}:
                continue  # stand-up, sport
            day = (e.get("eventDate") or "")[:10]
            if not day:
                continue
            st = re.match(r"(\d{1,2}):(\d\d)", e.get("showTime") or "")
            when = f"{day}T{int(st.group(1)):02d}:{st.group(2)}" if st else day
            v = e.get("venue") or {}
            city = LN_CITY.get((v.get("city") or "").lower(), v.get("city"))
            tickets = [t for t in e.get("tickets") or [] if t.get("isVisible", True)]
            sale = [_local(t.get("validFromUtc")) for t in tickets if t.get("typeId") == 2]
            pre = [_local(t.get("validFromUtc")) for t in tickets
                   if re.search(r"przedsprzeda|presale|pre-sale", t.get("type") or "", re.I)]
            heads = [l["name"] for l in e.get("lineup") or [] if l.get("type") == "headline" and l.get("name")]
            genre = next((LN_GENRE[k] for k in (g.get("key") for g in e.get("genres") or []) if k in LN_GENRE), "inne")
            ev = _ev("Live Nation", _text(e.get("name")), when, LN + (e.get("url") or ""), v.get("name"), city,
                     onsale=min(filter(None, sale), default=None), presale=min(filter(None, pre), default=None),
                     announced=_local(e.get("announceDateUtc")))
            ev["artists"] = heads
            ev["genre"] = genre
            ev["image"] = e.get("image")
            out.append(ev)
        if not docs or page * 20 >= total:
            break
        page += 1
    return out


# ---------------------------------------------------------------- Alter Art
ALTER = "https://alterart.pl"
_ALTER_ART = re.compile(r'<article class="event[^"]*"(.*?)</article>', re.S)


def alterart() -> list[dict]:
    page = get(ALTER + "/")
    out, seen = [], set()
    for block in _ALTER_ART.findall(page):
        t = re.search(r"<time[^>]*>(.*?)</time>", block, re.S)
        a = re.search(r'class="title"[^>]*>\s*<a href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        loc = re.search(r'class="location[^"]*"[^>]*>(.*?)<strong[^>]*>(.*?)</strong>', block, re.S)
        if not (t and a):
            continue
        dm = re.match(r"(\d\d)\.(\d\d)\.(\d\d)", _text(t.group(1)).replace(" ", ""))
        if not dm or a.group(1) in seen:
            continue
        seen.add(a.group(1))
        d, m, y = dm.groups()
        url = a.group(1) if a.group(1).startswith("http") else ALTER + a.group(1)
        ev = _ev("Alter Art", _text(a.group(2)), f"20{y}-{m}-{d}", url,
                 _text(loc.group(1)) if loc else None, _text(loc.group(2)).title() if loc else None)
        ev["sold_out"] = "WYPRZEDANY" in block.upper()
        out.append(ev)
    return out


# ---------------------------------------------------------------- Knock Out
KO = "https://www.knockoutprod.net"
_KO_ITEM = re.compile(r'<a href="([^"]*/concert/detail/\d+)" class="concerts-list__item">(.*?)</a>', re.S)


def knockout() -> list[dict]:
    out, seen = [], set()
    for page in range(1, 11):
        h = get(f"{KO}/pl/concert" + (f"?page={page}" if page > 1 else ""), min_interval=0.5)
        items = _KO_ITEM.findall(h)
        fresh = [(u, b) for u, b in items if u not in seen]
        if not fresh:
            break
        for url, block in fresh:
            seen.add(url)
            name = re.search(r'concerts-list__name[^>]*>(.*?)</h5>', block, re.S)
            place = re.search(r'concerts-list__place[^>]*>(.*?)</span>', block, re.S)
            pm = re.match(r"(.+?),\s*(\d\d)\.(\d\d)\.(20\d\d)", _text(place.group(1)) if place else "")
            if not (name and pm):
                continue
            city, d, m, y = pm.groups()
            out.append(_ev("Knock Out", _text(name.group(1)), f"{y}-{m}-{d}", url, None, city))
    return out


# ---------------------------------------------------------------- Prestige MJM
PRESTIGE = "https://prestigemjm.com"


def _from_text(source, title, text, url, posted: date) -> list[dict]:
    info = announce.parse(text, posted)
    return [_ev(source, title, d, url, None, city, onsale=info["onsale"], presale=info["presale"],
                announced=posted.isoformat())
            for d, city in info["dates"] if d >= posted.isoformat()]


def prestige() -> list[dict]:
    posts = get_json(f"{PRESTIGE}/wp-json/wp/v2/nadchodzace-koncerty?per_page=50&_fields=date,link,title,content")
    out = []
    for p in posts:
        posted = date.fromisoformat(p["date"][:10])
        out += _from_text("Prestige MJM", _text(p["title"]["rendered"]).title(),
                          _text(p["content"]["rendered"]), p["link"], posted)
    return out


# ---------------------------------------------------------------- Good Taste
GOODTASTE = "https://goodtaste.pl"
_GT_LD = re.compile(r'"name":\s*"?([^",\n]+?)"?,\s*"location":\s*"?([^",\n]+?)"?,.*?"startDate":\s*"?(\d\d)\.(\d\d)\.(20\d\d)', re.S)


def goodtaste(cache: dict) -> list[dict]:
    """cache: {link: {"modified": str, "events": [...]}} – strony pobieramy tylko po zmianie."""
    posts = get_json(f"{GOODTASTE}/wp-json/wp/v2/posts?per_page=40&_fields=date,modified,link,title")
    out, keep = [], set()
    for p in posts:
        link, title = p["link"], _text(p["title"]["rendered"])
        keep.add(link)
        c = cache.get(link)
        if not c or c.get("modified") != p.get("modified"):
            evs = []
            try:
                page = get(link, min_interval=1.0)
            except RuntimeError:
                continue
            first = title.split(" – ")[0].split(":")[0].lower()
            for name, loc, d, m, y in _GT_LD.findall(page):
                if first[:6] in name.lower() or name.lower()[:6] in title.lower():
                    evs.append(_ev("Good Taste", title, f"{y}-{m}-{d}", link, None,
                                   announce.CITIES.get(loc.strip().lower(), loc.strip())))
            if not evs:
                body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", page, flags=re.S | re.I)
                evs = _from_text("Good Taste", title, _text(body)[:20000], link, date.fromisoformat(p["date"][:10]))[:5]
            c = cache[link] = {"modified": p.get("modified"), "events": evs}
        out.extend(c["events"])
    for k in list(cache):
        if k not in keep:
            del cache[k]
    return out


def fetch(gt_cache: dict) -> list[dict]:
    out, errors = [], []
    for name, fn in (("livenation", livenation), ("alterart", alterart), ("knockout", knockout),
                     ("prestige", prestige), ("goodtaste", lambda: goodtaste(gt_cache))):
        try:
            got = fn()
            print(f"  {name}: {len(got)}", flush=True)
            out.extend(got)
        except Exception as e:
            errors.append(f"{name}: {e}")
            print(f"  {name}: błąd {e}", flush=True)
    if errors and not out:
        raise RuntimeError("; ".join(errors))
    return out
