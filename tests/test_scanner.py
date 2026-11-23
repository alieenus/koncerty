"""Testy bez sieci: python3 -m unittest discover tests"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scanner import enrich, filters, main
from scanner.sources import biletyna, ebilet, going

EBILET = {"titles": [
    {"title": "Backstreet Boys Into The Millennium Tour", "dateFrom": "2099-06-01T20:00:00", "dateTo": None,
     "place": "Warszawa", "category": "muzyka", "subcategory": "pop", "subcategoryName": "Pop", "slug": "bsb",
     "artists": ["Backstreet Boys"], "nextEventPlace": {"customName": "PGE Narodowy", "city": "Warszawa"},
     "organizer": {"name": "Live Nation"}, "soldOut": False},
    {"title": "Koncert wśród kwiatów i świec: Tribute to Backstreet Boys & Spice Girls", "dateFrom": "2099-06-02T17:30:00",
     "place": "Radom", "category": "muzyka", "subcategory": "pop", "slug": "tribute", "artists": [], "nextEventPlace": {}},
    {"title": "Guzior Widmo Tour", "dateFrom": "2099-06-03T18:00:00", "place": "Gdańsk, Poznań", "category": "muzyka",
     "subcategory": "hip-hop-rap", "slug": "guzior", "artists": ["Guzior"], "nextEventPlace": {"city": "Poznań"}},
    {"title": "Voucher", "dateFrom": None, "category": "muzyka", "subcategory": "pop", "slug": "v"},
]}

GOING_SITEMAP = """<urlset><url><loc>https://goingapp.pl/wydarzenie/bsb</loc><lastmod>2026-11-01</lastmod></url>
<url><loc>https://goingapp.pl/wydarzenie/vouchery</loc></url></urlset>"""
GOING_PAGE = """<html><script type="application/ld+json">{"@context":"https://schema.org","@type":"MusicEvent",
"name":"Backstreet Boys","startDate":"2099-06-01T20:00:00+02:00","url":"https://goingapp.pl/wydarzenie/bsb",
"location":{"@type":"Place","name":"PGE Narodowy","address":{"addressLocality":"Warszawa"}},
"performer":[{"@type":"MusicGroup","name":"Backstreet Boys"}]}</script></html>"""

BIL_SITEMAP = """<urlset><url><loc>https://biletyna.pl/koncert/Backstreet-Boys/Into-The-Millennium/Krakow</loc></url>
<url><loc>https://biletyna.pl/koncert/Kaska-Sochacka/TA-DRUGA/Lublin</loc></url></urlset>"""
BIL_PAGE = """<script type="application/ld+json">{"@context":"https://schema.org","@type":"PerformingGroup",
"name":"Backstreet Boys - Into The Millennium","event":[{"@type":"MusicEvent","name":"Backstreet Boys - Into The Millennium",
"startDate":"2099-06-05T20:00","location":{"@type":"Place","name":"Tauron Arena","address":{"addressLocality":"Kraków"}},
"performer":{"@type":"PerformingGroup","name":"Backstreet Boys - Into The Millennium"}}]}</script>"""

ARTISTS = {
    "backstreet boys": {"name": "Backstreet Boys", "country": "US", "fans": 1152023, "checked": 9e12},
    "guzior": {"name": "Guzior", "country": "PL", "fans": 300000, "checked": 9e12},
    "kaska sochacka": {"name": "Kaska Sochacka", "country": "PL", "fans": 90000, "checked": 9e12},
}


class T(unittest.TestCase):
    def test_guess_artists(self):
        g = lambda t: enrich.guess_artists({"title": t, "artists": []})
        self.assertEqual(g("Metallica - M72 World Tour"), ["Metallica"])
        self.assertEqual(g("Dua Lipa: Radical Optimism Tour 2027"), ["Dua Lipa"])
        self.assertEqual(g("Koncert Imagine Dragons"), ["Imagine Dragons"])
        self.assertEqual(g("Sting „3.0”"), ["Sting"])

    def test_fake(self):
        self.assertTrue(filters.is_fake({"title": "Tribute to Queen"}))
        self.assertTrue(filters.is_fake({"title": "Candlelight: Coldplay"}))
        self.assertFalse(filters.is_fake({"title": "Coldplay Music of the Spheres"}))
        for t in ["Koncert przy świecach: Tribute to Metallica", "Queen Classic Concert By Candle Glow",
                  "Koncert wśród kwiatów i świec: Tribute to Backstreet Boys & Spice Girls", "Candlelight: Coldplay"]:
            self.assertTrue(filters.is_candle({"title": t}), t)
        self.assertFalse(filters.is_candle({"title": "Tribute to Queen"}))

    def test_include_polish_star(self):
        cfg = main.load_config()
        for name in ["Dawid Podsiadło", "Dawid Podsiadlo", "MROZU"]:
            a = {"name": name, "country": "PL", "fans": 10}
            kind = filters.classify(a, cfg)
            self.assertTrue(filters.is_star(a, kind, cfg), name)
        a = {"name": "Guzior", "country": "PL", "fans": 300000}
        self.assertFalse(filters.is_star(a, filters.classify(a, cfg), cfg))

    def test_pipeline(self):
        with tempfile.TemporaryDirectory() as d:
            data, out = Path(d) / "data", Path(d) / "out.json"
            data.mkdir()
            (data / "artists.json").write_text(json.dumps(ARTISTS))
            real_cfg = main.load_config
            cfg_on = lambda: {**real_cfg(), "going": True}

            def fake_get(url, **kw):
                return GOING_SITEMAP if "sitemap" in url else GOING_PAGE

            with mock.patch.object(main, "DATA", data), mock.patch.object(main, "OUT", out), \
                 mock.patch.object(main, "load_config", cfg_on), \
                 mock.patch.object(ebilet, "get_json", return_value=EBILET), \
                 mock.patch.object(going, "get", side_effect=fake_get), \
                 mock.patch.object(biletyna, "get", side_effect=lambda u, **k: BIL_SITEMAP if "sitemap" in u else BIL_PAGE) as bget, \
                 mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("TM_API_KEY", None)
                self.assertEqual(main.run(), 0)
                res = json.loads(out.read_text())
                # BSB Warszawa + BSB Kraków (Biletyna) + koncert przy świecach; Guzior (PL) odpada
                self.assertEqual(res["count"], 3)
                krk = [c for c in res["concerts"] if c.get("venue_city") == "Kraków"]
                self.assertEqual(krk[0]["artist"], "Backstreet Boys")
                self.assertEqual(krk[0]["links"][0]["source"], "Biletyna")
                # strona polskiej artystki nie była pobierana
                self.assertFalse(any("Sochacka" in c.args[0] and "sitemap" not in c.args[0] for c in bget.call_args_list))
                candle = [c for c in res["concerts"] if c.get("candle")]
                self.assertEqual(len(candle), 1)
                self.assertEqual(candle[0]["genre"], "przy świecach")
                c = [c for c in res["concerts"] if not c.get("candle") and c["venue_city"] == "Warszawa"][0]
                self.assertEqual(c["artist"], "Backstreet Boys")
                self.assertEqual({l["source"] for l in c["links"]}, {"eBilet", "Going."})  # deduplikacja
                self.assertEqual(c["venue"], "PGE Narodowy")

                # drugi skan z nowym koncertem -> powiadomienie
                EBILET["titles"].append({**EBILET["titles"][0], "dateFrom": "2099-06-02T20:00:00", "slug": "bsb2"})
                with mock.patch.object(main.notify, "send_new") as sn:
                    main.run()
                    new = sn.call_args[0][0]
                    self.assertEqual([n["date"] for n in new], ["2099-06-02T20:00"])


if __name__ == "__main__":
    unittest.main()
