from __future__ import annotations

import os
from pathlib import Path

_MAX_DETECT_DEPTH = 3
_GIT_DIR = ".git"
_SKILL_FILE = "SKILL.md"


def find_git_root(start: Path) -> Path | None:
    current = start.resolve()
    while True:
        if (current / _GIT_DIR).exists():
            return current

        parent = current.parent
        if parent == current:
            return None

        current = parent


def detect_skills_dir(git_root: Path) -> Path | None:
    skill_dirs: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(git_root):
        path = Path(dirpath)
        rel = path.relative_to(git_root)
        if rel.parts and rel.parts[0].startswith("."):
            dirnames.clear()
            continue

        depth = len(rel.parts)
        if depth >= _MAX_DETECT_DEPTH:
            dirnames.clear()
            continue

        if _SKILL_FILE in filenames:
            skill_dirs.append(path)

    if not skill_dirs:
        return None

    parents = [sd.parent for sd in skill_dirs]
    common = _deepest_common_ancestor(parents, fallback=git_root)

    if common == git_root:
        return None

    return common


def _deepest_common_ancestor(paths: list[Path], *, fallback: Path) -> Path:
    result = paths[0]
    for p in paths[1:]:
        result_parts = result.parts
        p_parts = p.parts
        shared = 0
        for a, b in zip(result_parts, p_parts):
            if a != b:
                break
            shared += 1
        result = Path(*result_parts[:shared]) if shared else fallback

    return result
