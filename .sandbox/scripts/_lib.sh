# Sourced by other scripts — loads .env and exports COMPOSE_FILE.
# Assumes the caller has already cd'd to sandbox/.

if [[ ! -f .env ]]; then
    echo "Error: sandbox/.env not found. Copy .env.example to .env and edit it." >&2
    exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

: "${COMPOSE_PROJECT_NAME:?Must set COMPOSE_PROJECT_NAME in .env}"
: "${VARIANT:?Must set VARIANT in .env}"
: "${USER:?Must set USER in .env}"

export COMPOSE_FILE="docker-compose.yml:variants/${VARIANT}/compose.override.yml"
