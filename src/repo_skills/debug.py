from __future__ import annotations

import shlex
import sys
from pathlib import Path

_debug_enabled = False


def set_debug(value: bool) -> None:
    global _debug_enabled
    _debug_enabled = value


def is_debug() -> bool:
    return _debug_enabled


def debug_cmd(cmd: list[str], cwd: Path) -> None:
    if not _debug_enabled:
        return
    joined = shlex.join(cmd)
    print(f"[debug] {joined}", file=sys.stderr)
    print(f"  cwd: {cwd}", file=sys.stderr)


def debug_output(stdout: str, stderr: str) -> None:
    if not _debug_enabled:
        return
    if stdout:
        for line in stdout.splitlines():
            print(f"  stdout: {line}", file=sys.stderr)
    if stderr:
        for line in stderr.splitlines():
            print(f"  stderr: {line}", file=sys.stderr)
