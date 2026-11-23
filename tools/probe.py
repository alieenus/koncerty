"""Diagnostyka nowych źródeł: python3 tools/probe.py  (wynik wklej Claude'owi)."""
import json, re, sys, urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def get(url, accept="*/*"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept, "Accept-Language": "pl-PL,pl;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, r.read(3_000_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(2000).decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)


def show(url, accept="*/*", n=300):
    st, body = get(url, accept)
    marks = [m for m in ["ld+json", "__NEXT_DATA__", "__NUXT__", "MusicEvent", "\"@type\":\"Event\"", "startDate", "captcha", "cf-chl", "Just a moment"] if m in body]
    print(f"\n### {url}\n  status={st} len={len(body)} marks={marks}")
    locs = re.findall(r"<loc>([^<]+)</loc>", body)
    if locs:
        print(f"  sitemap locs={len(locs)}: " + " | ".join(locs[:6]))
    for m in re.findall(r"Sitemap:\s*(\S+)", body)[:8]:
        print("  robots sitemap:", m)
    ld = re.findall(r'application/ld\+json[^>]*>(.*?)</script>', body, re.S)
    if ld:
        print("  ld[0]:", re.sub(r"\s+", " ", ld[0])[:600])
    if body.lstrip().startswith(("{", "[")):
        print("  json:", re.sub(r"\s+", " ", body)[:n * 3])
    elif not locs and not ld:
        links = sorted(set(re.findall(r'href="(/[^"#?]{3,80})"', body)))
        print("  links:", " ".join(links[:40]))
    return body


print("=== EVENTIM ===")
show("https://www.eventim.pl/robots.txt")
for v in ["v2/productGroups", "v1/products"]:
    show(f"https://public-api.eventim.com/websearch/search/api/exploration/{v}?webId=web__eventim-pl&language=pl&page=1&categories=Koncerty", "application/json")
show("https://www.eventim.pl/city/warszawa-25/")
show("https://www.eventim.pl/artist/sting/")

print("\n=== BILETYNA ===")
b = show("https://biletyna.pl/robots.txt")
show("https://biletyna.pl/sitemap.xml")
show("https://biletyna.pl/koncerty")
show("https://biletyna.pl/Koncerty")
