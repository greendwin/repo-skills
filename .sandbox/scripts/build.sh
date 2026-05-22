#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
# shellcheck source=_lib.sh
source scripts/_lib.sh

BASE_IMAGE="${COMPOSE_PROJECT_NAME}-base:latest"

echo ">>> Building base image: ${BASE_IMAGE}"
docker build \
    --build-arg UID="${HOST_UID:-1000}" \
    --build-arg GID="${HOST_GID:-1000}" \
    --build-arg USERNAME="${USER}" \
    -t "${BASE_IMAGE}" \
    base/

echo ">>> Building variant: ${VARIANT}"
docker compose build
