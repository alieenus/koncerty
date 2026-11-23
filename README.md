# Koncerty gwiazd w Polsce

Strona z koncertami zagranicznych artystów w Polsce (kto, kiedy, gdzie). Skan co 6 godzin, powiadomienia Telegram dla obserwowanych artystów.

## Jak to działa
1. `scanner/` co 6h (timer systemd na VPS) pobiera koncerty z:
   - **eBilet**: ich JSON API, wszystkie tytuły muzyczne w jednym zapytaniu,
   - **Going.**: mapa strony i dane schema.org; pobierane są tylko nowe lub zmienione wydarzenia,
   - **Ticketmaster PL** (razem z Live Nation): oficjalne Discovery API, potrzebny darmowy klucz `TM_API_KEY`.
2. Odrzuca tribute, covery i wersje symfoniczne. Koncerty przy świecach trafiają na stronę jako osobny gatunek „przy świecach” (wyłączysz je przez `"candlelight": false`).
3. Dla każdego artysty sprawdza kraj w **MusicBrainz** i liczbę fanów na **Deezerze**. Zostają tylko artyści spoza Polski, którzy mają co najmniej `min_fans` fanów. Wyniki są zapisywane w pamięci podręcznej na 30 dni.
4. Łączy te same koncerty z różnych serwisów (artysta + dzień + miasto) i zapisuje `concerts.json`.
5. `web/index.html` wyświetla listę z wyszukiwarką i filtrami gatunku, miasta oraz „tylko nowe”.
6. Nowy koncert artysty z `watchlist` (plik `config.json`) wysyła wiadomość na Telegram.

## Ustawienia (`config.json`)
- `min_fans`: próg popularności (fani na Deezerze) dla artystów zagranicznych,
- `min_fans_unknown_country`: wyższy próg, gdy MusicBrainz nie zna kraju artysty,
- `watchlist`: artyści, o których chcesz dostawać powiadomienia,
- `notify_all_new`: `true` oznacza powiadomienia o każdym nowym koncercie,
- `candlelight` / `notify_candlelight`: pokazywanie koncertów przy świecach i powiadamianie o nich,
- `force_foreign` / `force_polish`: ręczne poprawki, gdy automatyczne rozpoznanie się pomyli.

## Instalacja na VPS
```bash
curl -fsSL https://raw.githubusercontent.com/alieenus/koncerty/main/deploy/install.sh | sudo bash
sudo nano /etc/koncerty.env      # klucze: TM_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
sudo systemctl start koncerty     # skan od razu
journalctl -u koncerty -f         # logi
```
Strona: `http://<IP serwera>/`. Kod aktualizuje się sam (`git pull` przed każdym skanem).

## Testy
```bash
python3 -m unittest discover tests
```
