#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=_lib.sh
source scripts/_lib.sh
exec docker compose exec claude-code tmux attach -t main
