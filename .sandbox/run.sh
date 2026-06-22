#!/usr/bin/env bash
# One-shot: ensure images are built, container is up, then drop into claude.
set -euo pipefail

cd "$(dirname "$0")"
# shellcheck source=scripts/_lib.sh
source scripts/_lib.sh

WORKDIR=""
ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --workdir)
            WORKDIR="$2"
            shift 2
            ;;
        --workdir=*)
            WORKDIR="${1#*=}"
            shift
            ;;
        *)
            ARGS+=("$1")
            shift
            ;;
    esac
done

WORKDIR_ARGS=()
if [[ -n "$WORKDIR" ]]; then
    WORKDIR_ARGS=(--workdir "$WORKDIR")
fi

VARIANT_IMAGE="${COMPOSE_PROJECT_NAME}-${VARIANT}:latest"

if ! docker image inspect "${BASE_IMAGE}" >/dev/null 2>&1 \
 || ! docker image inspect "${VARIANT_IMAGE}" >/dev/null 2>&1; then
    scripts/build.sh
fi

docker compose up -d

exec docker compose exec "${WORKDIR_ARGS[@]}" claude-code claude --dangerously-skip-permissions "${ARGS[@]}"
