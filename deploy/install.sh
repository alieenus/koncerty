#!/usr/bin/env bash
# Instalacja na VPS (Ubuntu/Debian). Uruchom jako root:
#   curl -fsSL https://raw.githubusercontent.com/alieenus/koncerty/main/deploy/install.sh | sudo bash
set -euo pipefail
REPO="${REPO:-https://github.com/alieenus/koncerty.git}"

apt-get update -qq
USE_CADDY=0
if ss -ltnp 2>/dev/null | grep -q '"caddy"'; then USE_CADDY=1; fi
apt-get install -y -qq python3 git ca-certificates
[ "$USE_CADDY" = 1 ] || apt-get install -y -qq nginx

id koncerty &>/dev/null || useradd --system --home /var/lib/koncerty --shell /usr/sbin/nologin koncerty
install -d -o koncerty -g koncerty /var/lib/koncerty /var/www/koncerty /var/www/koncerty/data

if [ -d /opt/koncerty/.git ]; then
  git -C /opt/koncerty pull --ff-only
else
  git clone "$REPO" /opt/koncerty
fi
chown -R koncerty:koncerty /opt/koncerty
git config --system --add safe.directory /opt/koncerty

[ -f /etc/koncerty.env ] || install -m 600 -o koncerty -g koncerty /opt/koncerty/deploy/koncerty.env.example /etc/koncerty.env

install -m 644 /opt/koncerty/deploy/koncerty.service /opt/koncerty/deploy/koncerty.timer /etc/systemd/system/
install -m 755 /opt/koncerty/deploy/koncerty /usr/local/bin/koncerty
if [ "$USE_CADDY" = 1 ]; then
  # Na serwerze działa już Caddy: nie ruszamy nginx ani Caddyfile, stronę dopinasz ręcznie
  systemctl disable --now nginx 2>/dev/null || true
  if [ -d /etc/caddy ]; then
    install -m 644 /opt/koncerty/deploy/koncerty.caddy /etc/caddy/koncerty.caddy
    echo ">>> Wykryto Caddy. Dopisz na końcu /etc/caddy/Caddyfile:  import /etc/caddy/koncerty.caddy"
  else
    echo ">>> Wykryto Caddy (poza /etc/caddy). Konfiguracja strony: /opt/koncerty/deploy/koncerty.caddy"
  fi
else
  install -m 644 /opt/koncerty/deploy/nginx-koncerty.conf /etc/nginx/sites-available/koncerty
  ln -sf /etc/nginx/sites-available/koncerty /etc/nginx/sites-enabled/koncerty
  rm -f /etc/nginx/sites-enabled/default
  nginx -t
  systemctl enable --now nginx
  systemctl reload nginx
fi

# zapora: otwórz HTTP, jeśli ufw jest włączony
if command -v ufw &>/dev/null && ufw status | grep -q active; then ufw allow 80,443,8080/tcp; fi

systemctl daemon-reload
systemctl enable --now koncerty.timer
echo "Pierwszy skan startuje w tle (pierwszy trwa ok. 15-25 min, kolejne 1-2 min)."
systemctl start --no-block koncerty.service
echo "Podgląd logów: journalctl -u koncerty -f"
