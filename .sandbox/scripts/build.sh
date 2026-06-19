#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
# shellcheck source=_lib.sh
source scripts/_lib.sh

FORCE=0
for arg in "$@"; do
    case "$arg" in
        --force) FORCE=1 ;;
        *)
            echo "Usage: build.sh [--force]" >&2
            echo "  --force  rebuild the shared base image from scratch (--no-cache)" >&2
            exit 1
            ;;
    esac
done

# The base image is shared across all sandboxes, so leave it untouched when it
# already exists unless --force is given (which rebuilds it for everyone).
if [[ "${FORCE}" -eq 1 ]]; then
    echo ">>> Forcing rebuild of base image: ${BASE_IMAGE}"
    docker build \
        --no-cache \
        --build-arg UID="${HOST_UID:-1000}" \
        --build-arg GID="${HOST_GID:-1000}" \
        --build-arg USERNAME="${USER}" \
        -t "${BASE_IMAGE}" \
        base/
elif docker image inspect "${BASE_IMAGE}" >/dev/null 2>&1; then
    echo ">>> Base image already present, skipping: ${BASE_IMAGE} (use --force to rebuild)"
else
    echo ">>> Building base image: ${BASE_IMAGE}"
    docker build \
        --build-arg UID="${HOST_UID:-1000}" \
        --build-arg GID="${HOST_GID:-1000}" \
        --build-arg USERNAME="${USER}" \
        -t "${BASE_IMAGE}" \
        base/
fi

echo ">>> Building variant: ${VARIANT}"
docker compose build
