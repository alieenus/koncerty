"""Powiadomienia Telegram o nowych koncertach artystów z listy obserwowanych.

Działa dopiero po ustawieniu zmiennych TELEGRAM_BOT_TOKEN i TELEGRAM_CHAT_ID
(w pliku /etc/koncerty.env na serwerze). Bez nich nic nie wysyła.
"""
import json
from datetime import datetime
import os
import urllib.request

from .enrich import norm


def _send(token: str, chat: str, text: str):
    body = json.dumps({"chat_id": chat, "text": text, "parse_mode": "HTML",
                       "disable_web_page_preview": False}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=body,
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=20).read()


def _fmt(m: dict) -> str:
    where = ", ".join(filter(None, [m.get("venue"), m.get("venue_city") or ", ".join(m["cities"])]))
    links = "\n".join(f'<a href="{l["url"]}">Bilety: {l["source"]}</a>' for l in m["links"])
    fest = f"\n🎪 {m['festival_name']}" if m.get("festival_name") else ""
    sale, now = "", datetime.now().strftime("%Y-%m-%dT%H:%M")
    if (m.get("presale") or "") > now:
        sale += f"\n⏰ Przedsprzedaż: {m['presale'].replace('T', ' ')}"
    if (m.get("onsale") or "") > now:
        sale += f"\n🎟 Sprzedaż: {m['onsale'].replace('T', ' ')}"
    return f"🎤 <b>{m['artist']}</b>{fest}\n📅 {m['date'].replace('T', ' ')}\n📍 {where}{sale}\n{links}"


def send_new(new: list[dict], cfg: dict):
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat) or not new:
        return
    watch = {norm(a) for a in cfg["watchlist"]}
    notify_all = cfg.get("notify_all_new", False)
    for m in new:
        if m.get("candle") and not cfg.get("notify_candlelight", False):
            continue
        if notify_all or norm(m["artist"]) in watch:
            try:
                _send(token, chat, _fmt(m))
            except Exception as e:
                print(f"Telegram: błąd {e}")
