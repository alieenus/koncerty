"""Diagnostyka: Going. (API) i kalendarze dużych hal.  python3 tools/probe2.py"""
import re, urllib.request, urllib.error, json

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def get(url, data=None, headers=None):
    h = {"User-Agent": UA, "Accept-Language": "pl-PL,pl;q=0.9"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, r.geturl(), r.read(4_000_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, url, e.read(1500).decode("utf-8", "replace")
    except Exception as e:
        return 0, url, str(e)


def short(s, n=400):
    return re.sub(r"\s+", " ", s)[:n]


print("=== GOING: szukanie API w skryptach ===")
st, _, home = get("https://goingapp.pl/")
scripts = sorted(set(re.findall(r'src="([^"]+\.js[^"]*)"', home)))
print("home", st, len(home), "scripts:", len(scripts))
found = set()
for s in scripts[:25]:
    u = s if s.startswith("http") else "https://goingapp.pl" + s
    _, _, js = get(u)
    for m in re.findall(r'https://[a-z0-9.\-]+(?:goingapp|empik)[a-z0-9.\-/]*', js):
        found.add(m)
    for m in re.findall(r'(?:query|operationName)\s*[:=]?\s*["`]?\s*(?:query\s+)?([A-Za-z]{4,40})\s*\(', js):
        found.add("op:" + m)
    for m in re.findall(r'["`](/api/[A-Za-z0-9_/\-{}$.]{3,80})["`]', js):
        found.add("path:" + m)
print("\n".join(sorted(found)[:120]))
for gq in ["https://empikbilety-cache-proxy.prod.goingapp.eu/graphql"]:
    body = json.dumps({"query": "{ __schema { queryType { fields { name } } } }"}).encode()
    st, _, r = get(gq, body, {"Content-Type": "application/json"})
    print("\nintrospection", st, short(r, 1500))

print("\n=== HALE I STADIONY ===")
SITES = [
    "https://pgenarodowy.pl/wydarzenia", "https://www.stadionslaski.pl/wydarzenia",
    "https://tauronarenakrakow.pl/wydarzenia", "https://www.atlasarena.pl/wydarzenia",
    "https://ergoarena.pl/wydarzenia-lista/", "https://polsatplusarenagdansk.pl/wydarzenia",
    "https://www.spodekkatowice.pl/wydarzenia", "https://halastulecia.pl/wydarzenia",
    "https://arenagliwice.com/wydarzenia", "https://www.cos.pl/torwar",
    "https://tarczynskiarena.pl/wydarzenia", "https://www.ptakwarsawexpo.com/wydarzenia",
]
for url in SITES:
    st, final, b = get(url)
    host = final.split("/")[2] if "//" in final else url
    marks = [m for m in ["ld+json", "MusicEvent", "\"Event\"", "startDate", "__NEXT_DATA__", "__NUXT", "wp-json", "Just a moment"] if m in b]
    print(f"\n### {url} -> {final}\n  status={st} len={len(b)} marks={marks}")
    ld = re.findall(r'application/ld\+json[^>]*>(.*?)</script>', b, re.S)
    for x in ld[:2]:
        print("  ld:", short(x, 350))
    _, _, rob = get(f"https://{host}/robots.txt")
    print("  robots sitemaps:", re.findall(r"Sitemap:\s*(\S+)", rob)[:4])
    if not ld:
        links = sorted(set(re.findall(r'href="([^"#]*(?:wydarzen|event|koncert)[^"#]*)"', b, re.I)))
        print("  links:", " | ".join(links[:12]))
        dates = re.findall(r"\b\d{1,2}[./]\d{1,2}[./]20\d\d\b|\b\d{1,2} (?:stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|września|października|listopada|grudnia) 20\d\d", b)
        print("  daty w HTML:", dates[:6])
