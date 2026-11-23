"""Diagnostyka hal (WordPress REST API i strony listy).  python3 tools/probe3.py"""
import json, re, urllib.request, urllib.error

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "pl-PL,pl;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, r.read(3_000_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, str(e)[:100]


def text(html):
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


WP = ["https://www.tauronarenakrakow.pl", "https://atlasarena.pl", "https://ergoarena.pl",
      "https://prezeroarenagliwice.pl", "https://tarczynskiarenawroclaw.pl", "https://polsatplusarenagdansk.pl"]
for base in WP:
    print(f"\n### {base}")
    st, b = get(base + "/wp-json/wp/v2/types")
    types = {}
    if st == 200:
        try:
            types = {k: v.get("rest_base") for k, v in json.loads(b).items()}
        except Exception:
            pass
    print("  types:", st, types)
    st, b = get(base + "/wp-json/tribe/events/v1/events?per_page=2")
    print("  tribe:", st, re.sub(r"\s+", " ", b)[:300] if st == 200 else "")
    for k, rb in types.items():
        if rb and re.search(r"event|wydarz|impreza|kalend", f"{k} {rb}", re.I):
            st, b = get(f"{base}/wp-json/wp/v2/{rb}?per_page=2")
            print(f"  [{rb}] status={st}")
            try:
                items = json.loads(b)
                it = items[0]
                print("   keys:", list(it.keys()))
                print("   title:", it.get("title"), "link:", it.get("link"))
                for f in ("acf", "meta", "event_date", "date_event", "start_date"):
                    if it.get(f):
                        print(f"   {f}:", json.dumps(it[f], ensure_ascii=False)[:500])
                st2, page = get(it["link"])
                t = text(page)
                dates = re.findall(r"\b\d{1,2}[./]\d{1,2}[./]20\d\d\b|\b\d{1,2} (?:stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|września|października|listopada|grudnia) 20\d\d|20\d\d-\d\d-\d\d[T ]\d\d:\d\d", page)
                print("   strona:", st2, "daty:", dates[:6], "ld:", "ld+json" in page)
            except Exception as e:
                print("   err", e, re.sub(r"\s+", " ", b)[:200])

print("\n### PGE Narodowy kalendarium")
st, b = get("https://www.pgenarodowy.pl/wydarzenia/kalendarium-wydarzen")
t = text(b)
i = t.find("2026")
print(st, t[max(0, i - 300): i + 900])
print("  linki:", sorted(set(re.findall(r'href="(/wydarzenia/[^"#]{5,90})"', b)))[:10])

print("\n### Spodek")
st, b = get("https://www.spodekkatowice.pl/pl/wydarzenia/61/")
t = text(b)
i = t.find("2026")
print(st, t[max(0, i - 200): i + 900])
st, b = get("https://www.spodekkatowice.pl/pl/wydarzenia/magic-christmas-concert,3848.html")
print("  event:", st, "ld:", "ld+json" in b, text(b)[:0])
d = re.findall(r"\b\d{1,2}[./]\d{1,2}[./]20\d\d\b|\b\d{1,2} (?:stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|września|października|listopada|grudnia) 20\d\d", b)
print("  daty:", d[:5])
