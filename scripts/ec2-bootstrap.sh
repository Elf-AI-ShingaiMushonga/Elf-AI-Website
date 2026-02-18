#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${DOMAIN:-}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env}"
EMAIL="${EMAIL:-}"
BOOTSTRAP_SEED_DB="${BOOTSTRAP_SEED_DB:-true}"

read_env_value() {
  local key="$1"
  local file="$2"
  local value

  value="$(awk -v k="$key" '
    $0 !~ /^[[:space:]]*#/ && $0 ~ "^[[:space:]]*" k "[[:space:]]*=" {
      sub(/^[[:space:]]*[^=]+=[[:space:]]*/, "", $0)
      print $0
      exit
    }
  ' "$file")"

  if [[ -z "${value}" ]]; then
    return 1
  fi

  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"
  printf '%s' "$value"
}

extract_host() {
  local raw="${1:-}"
  raw="${raw#http://}"
  raw="${raw#https://}"
  raw="${raw%%/*}"
  raw="${raw##*@}"
  raw="${raw%%:*}"
  printf '%s' "$raw"
}

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

if [[ -z "${DOMAIN}" ]]; then
  DOMAIN="$(read_env_value "DOMAIN" "${ENV_FILE}" || true)"
fi
if [[ -z "${DOMAIN}" ]]; then
  SITE_URL_VALUE="$(read_env_value "SITE_URL" "${ENV_FILE}" || true)"
  DOMAIN="$(extract_host "${SITE_URL_VALUE}")"
fi
if [[ -z "${DOMAIN}" ]]; then
  DOMAIN="elf-ai.co.za"
fi

if [[ -z "${EMAIL}" ]]; then
  EMAIL="$(read_env_value "LETSENCRYPT_EMAIL" "${ENV_FILE}" || true)"
fi
if [[ -z "${EMAIL}" ]]; then
  EMAIL="$(read_env_value "EMAIL" "${ENV_FILE}" || true)"
fi
if [[ -z "${EMAIL}" ]]; then
  EMAIL="$(read_env_value "MAIL_DEFAULT_SENDER" "${ENV_FILE}" || true)"
fi

CERT_PATH="certbot/conf/live/${DOMAIN}/fullchain.pem"

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

RDS_SECRET_ID_VALUE="${RDS_SECRET_ID:-$(read_env_value "RDS_SECRET_ID" "${ENV_FILE}" || true)}"
AWS_REGION_VALUE="${AWS_REGION:-$(read_env_value "AWS_REGION" "${ENV_FILE}" || true)}"
if [[ -z "${AWS_REGION_VALUE}" ]]; then
  AWS_REGION_VALUE="$(read_env_value "AWS_DEFAULT_REGION" "${ENV_FILE}" || true)"
fi

if [[ -n "${RDS_SECRET_ID_VALUE}" ]]; then
  if [[ -n "${AWS_REGION_VALUE}" ]]; then
    AWS_REGION="${AWS_REGION_VALUE}" ENV_FILE="${ENV_FILE}" ./scripts/sync-rds-env.sh "${RDS_SECRET_ID_VALUE}"
  else
    ENV_FILE="${ENV_FILE}" ./scripts/sync-rds-env.sh "${RDS_SECRET_ID_VALUE}"
  fi
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
    echo "Set LETSENCRYPT_EMAIL (or EMAIL) in ${ENV_FILE}, or export EMAIL before running." >&2
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
