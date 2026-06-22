#!/usr/bin/env bash
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)

exec "$SCRIPT_DIR/run.sh" --workdir /work/.worktrees/work "$@"
