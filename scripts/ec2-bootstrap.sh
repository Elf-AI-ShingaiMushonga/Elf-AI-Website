#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${DOMAIN:-elf-ai.co.za}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env}"
EMAIL="${EMAIL:-}"
CERT_PATH="certbot/conf/live/${DOMAIN}/fullchain.pem"
BOOTSTRAP_SEED_DB="${BOOTSTRAP_SEED_DB:-true}"

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "Missing $COMPOSE_FILE. Run from the repo root." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose plugin is required." >&2
  exit 1
fi

mkdir -p certbot/www certbot/conf

if [[ ! -f "${ENV_FILE}" ]]; then
  cp .env.example "${ENV_FILE}"
fi

if grep -Eq "^SECRET_KEY=(change-me|)$" "${ENV_FILE}"; then
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
  sed -i.bak "s/^SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" "${ENV_FILE}"
  rm -f "${ENV_FILE}.bak"
fi

if [[ -n "${RDS_SECRET_ID:-}" ]]; then
  ENV_FILE="${ENV_FILE}" ./scripts/sync-rds-env.sh "${RDS_SECRET_ID}"
fi

if grep -Eq "^DATABASE_URL=.*change-me" "${ENV_FILE}"; then
  echo "Set a real DATABASE_URL in ${ENV_FILE} or export RDS_SECRET_ID before running this script." >&2
  exit 1
fi

compose() {
  docker compose -f "$COMPOSE_FILE" "$@"
}

if [[ ! -f "${CERT_PATH}" ]]; then
  if [[ -z "$EMAIL" ]]; then
    echo "Set EMAIL for Let's Encrypt, e.g. EMAIL=you@example.com" >&2
    exit 1
  fi

  echo "Starting HTTP-only Nginx to issue certificate..."
  NGINX_CONF=elf-ai-http.conf compose up --build -d web nginx

  echo "Requesting Let's Encrypt certificate for $DOMAIN..."
  compose --profile ops run --rm certbot \
    certonly --webroot -w /var/www/certbot \
    -d "$DOMAIN" -d "www.$DOMAIN" \
    --email "$EMAIL" --agree-tos --no-eff-email
else
  echo "Existing certificate found at ${CERT_PATH}. Skipping issuance."
fi

echo "Starting production stack with HTTPS Nginx..."
NGINX_CONF=elf-ai.conf compose up --build -d web nginx

echo "Running database migrations..."
compose run --rm web flask --app app.py db upgrade

echo "Ensuring required tables and baseline data exist..."
compose run --rm -e SEED_DB="${BOOTSTRAP_SEED_DB}" web flask --app app.py init-db

echo "Done. App should be available at https://$DOMAIN"
