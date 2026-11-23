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
                 mock.patch.object(main.venues, "fetch", return_value=[]), \
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


class Festivals(unittest.TestCase):
    def test_festival_with_lineup(self):
        ev = {"source": "eBilet", "title": "Open'er Festival 2099", "artists": ["Backstreet Boys", "Guzior", "Nikt Znany"],
              "date": "2099-07-01T16:00", "date_to": None, "cities": ["Gdynia"], "venue": "Lotnisko", "venue_city": "Gdynia",
              "genre": "festiwal", "organizer": None, "url": "https://x/o", "image": None, "sold_out": False}
        self.assertTrue(filters.is_festival(ev))
        self.assertTrue(filters.is_festival({"title": "Audioriver 2099", "genre": "inne"}))
        self.assertFalse(filters.is_festival({"title": "Metallica M72", "genre": "metal"}))
        with tempfile.TemporaryDirectory() as d:
            data, out = Path(d) / "data", Path(d) / "out.json"
            data.mkdir()
            (data / "artists.json").write_text(json.dumps({**ARTISTS, "nikt znany": {"name": "Nikt Znany", "country": "US", "fans": 5, "checked": 9e12}}))
            with mock.patch.object(main, "DATA", data), mock.patch.object(main, "OUT", out), \
                 mock.patch.object(ebilet, "fetch", return_value=[ev]), \
                 mock.patch.object(biletyna, "get", return_value="<urlset></urlset>"), \
                 mock.patch.object(main.venues, "fetch", return_value=[]):
                os.environ.pop("TM_API_KEY", None)
                main.run()
                c = json.loads(out.read_text())["concerts"]
                self.assertEqual(len(c), 1)
                self.assertEqual(c[0]["genre"], "festiwal")
                self.assertEqual(c[0]["lineup"], ["Backstreet Boys"])
                # drugi skan: do line-upu dochodzi Guzior? nie (PL) – ale dopisanie BSB do innego festiwalu = powiadomienie
                ev2 = {**ev, "title": "Orange Warsaw Festival 2099", "url": "https://x/ow"}
                with mock.patch.object(ebilet, "fetch", return_value=[ev, ev2]), \
                     mock.patch.object(main.notify, "send_new") as sn:
                    main.run()
                    new = sn.call_args[0][0]
                    self.assertIn(("Backstreet Boys", "Orange Warsaw Festival 2099"),
                                  [(n["artist"], n.get("festival_name")) for n in new])


class Venues(unittest.TestCase):
    def test_tauron(self):
        from scanner.sources import venues
        data = {"total_pages": 1, "events": [{"title": "Metallica &#8211; M72", "start_date": "2099-05-01 20:00:00",
                                              "url": "https://x/event/m", "image": {"url": "https://x/i.jpg"}}]}
        with mock.patch.object(venues, "get_json", return_value=data):
            ev = venues.tauron()
        self.assertEqual((ev[0]["title"], ev[0]["date"], ev[0]["venue_city"]), ("Metallica – M72", "2099-05-01T20:00", "Kraków"))
        self.assertEqual(enrich.guess_artists(ev[0]), ["Metallica"])
