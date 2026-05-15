#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
  echo "Edit .env if you need to override SEARXNG_IMAGE or VALKEY_IMAGE for a mirror registry."
fi

set -a
source ./.env
set +a

SEARXNG_IMAGE="${SEARXNG_IMAGE:-docker.io/searxng/searxng:${SEARXNG_VERSION:-latest}}"
VALKEY_IMAGE="${VALKEY_IMAGE:-docker.io/valkey/valkey:9-alpine}"

for image in "$SEARXNG_IMAGE" "$VALKEY_IMAGE"; do
  if ! docker image inspect "$image" >/dev/null 2>&1; then
    echo "Pulling $image"
    docker pull "$image"
  fi
done

docker compose --env-file .env up -d

echo "SearXNG should be available at ${SEARXNG_BASE_URL:-http://127.0.0.1:${SEARXNG_PORT:-18080}/}"
