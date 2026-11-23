"""Reguły: co jest koncertem zagranicznej gwiazdy, a co nie."""
import re

# Tribute, covery, „muzyka X przy świecach” itp. – to nie jest prawdziwy artysta.
FAKE = re.compile(
    r"tribute|cover|candlelight|przy świecach|wśród (?:kwiatów|świec)|symfonicznie|"
    r"\bplays?\b|hołd|w hołdzie|the music of|muzyka (?:zespołu|z filmów)|legends of|"
    r"musical|show\b.*\bhits|największe przeboje|greatest hits live|orchestra plays|"
    r"in concert:|dj set z muzyką|by candle glow|klasycznie|best of\b|golden hits|\bthe show\b|"
    r"tribute show|solo piano|grand piano|\blegends?\b|experience\b|w blasku|świąteczn|kolęd",
    re.I,
)


# Koncerty przy świecach (Candlelight, „by Candle Glow” itp.) – osobna kategoria na stronie.
CANDLE = re.compile(r"candle|przy [sś]wiecach|w[sś]r[oó]d (?:kwiat[oó]w i )?[sś]wiec|w blasku (?:tysi[eę]cy )?[sś]wiec", re.I)


def is_candle(ev: dict) -> bool:
    return bool(CANDLE.search(ev["title"]))


def is_fake(ev: dict) -> bool:
    return bool(FAKE.search(ev["title"]))


def classify(artist: dict, cfg: dict) -> str:
    """Zwraca 'foreign', 'polish' albo 'unknown'."""
    key = artist.get("name", "").lower()
    if key in cfg["force_foreign"]:
        return "foreign"
    if key in cfg["force_polish"]:
        return "polish"
    c = artist.get("country")
    if c == "PL":
        return "polish"
    if c:
        return "foreign"
    return "unknown"


def is_star(artist: dict, kind: str, cfg: dict) -> bool:
    fans = artist.get("fans", 0)
    if kind == "foreign":
        return fans >= cfg["min_fans"]
    if kind == "unknown":  # brak kraju w MusicBrainz: wymagamy dużo większej popularności
        return fans >= cfg["min_fans_unknown_country"]
    return False
