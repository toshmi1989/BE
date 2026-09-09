#!/usr/bin/env bash
# Phase 25 — Start controlled-beta stack on a Docker-capable host.
# Does NOT invent packages/writers. Does NOT claim success on hosts without Docker.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "BLOCK: Docker CLI not found. Move to a Docker-capable beta host."
  exit 2
fi

if [[ -z "${POSTGRES_PASSWORD:-}" || -z "${AUTH_SECRET:-}" ]]; then
  echo "BLOCK: export POSTGRES_PASSWORD and AUTH_SECRET (see .env.example)"
  exit 2
fi

export AUTH_REQUIRED="${AUTH_REQUIRED:-true}"
echo "Starting docker compose beta stack..."
docker compose -f docker-compose.beta.yml up -d --build

echo "Waiting for health..."
for i in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${API_PORT:-8000}/api/health" >/dev/null 2>&1; then
    echo "health OK"
    break
  fi
  sleep 2
  if [[ "$i" -eq 60 ]]; then
    echo "BLOCK: health timeout"
    exit 2
  fi
done

curl -fsS "http://127.0.0.1:${API_PORT:-8000}/api/ready" || true
curl -fsS "http://127.0.0.1:${API_PORT:-8000}/api/version" || true
echo
echo "Stack started. Migrations run on backend container start (alembic upgrade head)."
echo "Next: python scripts/beta_smoke_test.py"
