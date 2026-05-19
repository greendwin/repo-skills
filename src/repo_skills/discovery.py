from __future__ import annotations

import os
from pathlib import Path

from .manifest import Manifest, default_install_dir, default_manifest_path

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


def find_repo_skills_dir(
    cwd: Path | None = None,
    manifest_path: Path | None = None,
) -> Path | None:
    if cwd is None:
        cwd = Path.cwd()
    root = find_git_root(cwd)
    if root is not None:
        skills_dir = root / "skills"
        if skills_dir.is_dir():
            return skills_dir

    if manifest_path is None:
        manifest_path = default_manifest_path()

    manifest = Manifest.load(manifest_path)
    if manifest.repo_path is not None:
        skills_dir = Path(manifest.repo_path) / "skills"
        if skills_dir.is_dir():
            return skills_dir

    return None


def find_install_dir() -> Path | None:
    path = default_install_dir()
    if path.is_dir():
        return path
    return None


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
