#!/usr/bin/env bash
set -euo pipefail

SECRET_ID="${1:-${RDS_SECRET_ID:-}}"
AWS_REGION="${AWS_REGION:-}"
ENV_FILE="${ENV_FILE:-.env}"

if [[ -z "${SECRET_ID}" ]]; then
  echo "Usage: $0 <secret-arn-or-name>" >&2
  echo "Or set RDS_SECRET_ID in the environment." >&2
  exit 1
fi

if ! command -v aws >/dev/null 2>&1; then
  echo "aws CLI is required." >&2
  exit 1
fi

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "Python is required to parse the secret JSON." >&2
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  if [[ -f .env.example ]]; then
    cp .env.example "${ENV_FILE}"
  else
    touch "${ENV_FILE}"
  fi
fi

if [[ -n "${AWS_REGION}" ]]; then
  SECRET_JSON="$(aws secretsmanager get-secret-value --region "${AWS_REGION}" --secret-id "${SECRET_ID}" --query SecretString --output text)"
else
  SECRET_JSON="$(aws secretsmanager get-secret-value --secret-id "${SECRET_ID}" --query SecretString --output text)"
fi

DATABASE_URL="$("${PYTHON_BIN}" - "$SECRET_JSON" <<'PY'
import json
import sys
from urllib.parse import quote_plus

payload = json.loads(sys.argv[1])
username = quote_plus(payload["username"])
password = quote_plus(payload["password"])
host = payload["host"]
port = payload.get("port", 5432)
dbname = payload.get("dbname", "postgres")
sslmode = payload.get("sslmode", "require")

print(f"postgresql+psycopg2://{username}:{password}@{host}:{port}/{dbname}?sslmode={sslmode}")
PY
)"

if grep -q '^DATABASE_URL=' "${ENV_FILE}"; then
  sed -i.bak "s|^DATABASE_URL=.*|DATABASE_URL=${DATABASE_URL}|" "${ENV_FILE}"
else
  printf "\nDATABASE_URL=%s\n" "${DATABASE_URL}" >> "${ENV_FILE}"
fi
rm -f "${ENV_FILE}.bak"

echo "DATABASE_URL was updated in ${ENV_FILE}."
echo "Run: docker compose -f docker-compose.prod.yml up --build -d"
