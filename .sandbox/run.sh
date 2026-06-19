#!/usr/bin/env bash
# One-shot: ensure images are built, container is up, then drop into claude.
set -euo pipefail

cd "$(dirname "$0")"
# shellcheck source=scripts/_lib.sh
source scripts/_lib.sh

VARIANT_IMAGE="${COMPOSE_PROJECT_NAME}-${VARIANT}:latest"

if ! docker image inspect "${BASE_IMAGE}" >/dev/null 2>&1 \
 || ! docker image inspect "${VARIANT_IMAGE}" >/dev/null 2>&1; then
    scripts/build.sh
fi

docker compose up -d

exec docker compose exec claude-code claude --dangerously-skip-permissions $*
