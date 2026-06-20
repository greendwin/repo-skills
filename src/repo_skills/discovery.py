from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from .config import SKILL_FILE
from .manifest import Manifest, default_install_dir, default_manifest_path

_GIT_DIR = ".git"


class DetectKind(Enum):
    NONE = auto()
    SINGLE = auto()
    AMBIGUOUS = auto()


@dataclass(frozen=True)
class DetectResult:
    kind: DetectKind
    path: Path | None


def find_git_root(start: Path) -> Path | None:
    current = start.resolve()
    while True:
        if (current / _GIT_DIR).exists():
            return current

        parent = current.parent
        if parent == current:
            return None

        current = parent


def detect_skills_dir(git_root: Path) -> DetectResult:
    skill_dirs: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(git_root):
        path = Path(dirpath)
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]

        if SKILL_FILE in filenames:
            skill_dirs.append(path)
            # outermost SKILL.md wins; don't descend into a skill's internals
            dirnames.clear()

    if not skill_dirs:
        return DetectResult(DetectKind.NONE, None)

    parents = [sd.parent for sd in skill_dirs]
    common = _deepest_common_ancestor(parents, fallback=git_root)

    if common == git_root:
        return DetectResult(DetectKind.AMBIGUOUS, None)

    return DetectResult(DetectKind.SINGLE, common)


def resolve_skills_dir(git_root: Path, skills_dir: str) -> Path | None:
    candidate = Path(skills_dir)
    if candidate.is_absolute():
        return None

    target = (git_root / candidate).resolve()
    if git_root.resolve() not in target.parents or not target.is_dir():
        return None

    return target


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
