"""Minimalny klient HTTP (tylko biblioteka standardowa) z ponawianiem i limitem tempa."""
import json
import time
import urllib.error
import urllib.request

BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)

_last_call: dict[str, float] = {}


def get(url: str, *, ua: str = BROWSER_UA, accept: str = "*/*", min_interval: float = 0.0,
        retries: int = 3, timeout: int = 30) -> str:
    host = url.split("/")[2]
    if min_interval:
        wait = _last_call.get(host, 0) + min_interval - time.time()
        if wait > 0:
            time.sleep(wait)
    last_err: Exception | None = None
    for attempt in range(retries):
        _last_call[host] = time.time()
        req = urllib.request.Request(url, headers={
            "User-Agent": ua,
            "Accept": accept,
            "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (400, 401, 403, 404):
                break
        except Exception as e:  # sieć, timeout
            last_err = e
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"GET {url} nie powiódł się: {last_err}")


def get_json(url: str, **kw):
    kw.setdefault("accept", "application/json")
    return json.loads(get(url, **kw))
