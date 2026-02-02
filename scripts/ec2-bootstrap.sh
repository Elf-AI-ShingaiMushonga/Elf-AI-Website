#!/usr/bin/env bash
set -euo pipefail

DOMAIN="elf-ai.co.za"
COMPOSE_FILE="docker-compose.prod.yml"
APP_UID="${APP_UID:-1000}"
APP_GID="${APP_GID:-1000}"

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "Missing $COMPOSE_FILE. Run from the repo root." >&2
  exit 1
fi

mkdir -p data certbot/www certbot/conf
sudo chown -R "${APP_UID}:${APP_GID}" data

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

if grep -Eq "^SECRET_KEY=(change-me|)$" .env; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    echo "Python is required to generate SECRET_KEY." >&2
    exit 1
  fi
  SECRET_KEY="$($PYTHON_BIN - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)"
  sed -i.bak "s/^SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" .env
  rm -f .env.bak
fi

EMAIL="${EMAIL:-}"
if [[ -z "$EMAIL" ]]; then
  echo "Set EMAIL for Let's Encrypt, e.g. EMAIL=you@example.com" >&2
  exit 1
fi

echo "Starting HTTP-only Nginx to issue certificate..."
sed -i.bak "s#./nginx/elf-ai.conf#./nginx/elf-ai-http.conf#" "$COMPOSE_FILE"
rm -f "${COMPOSE_FILE}.bak"
docker compose -f "$COMPOSE_FILE" up -d

echo "Requesting Let's Encrypt certificate for $DOMAIN..."
docker compose -f "$COMPOSE_FILE" run --rm certbot \
  certonly --webroot -w /var/www/certbot \
  -d "$DOMAIN" -d "www.$DOMAIN" \
  --email "$EMAIL" --agree-tos --no-eff-email

echo "Switching Nginx to HTTPS..."
sed -i.bak "s#./nginx/elf-ai-http.conf#./nginx/elf-ai.conf#" "$COMPOSE_FILE"
rm -f "${COMPOSE_FILE}.bak"
docker compose -f "$COMPOSE_FILE" up -d

echo "Done. App should be available at https://$DOMAIN"
