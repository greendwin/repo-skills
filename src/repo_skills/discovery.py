from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from .config import iter_skill_dirs
from .manifest import default_install_dir

_GIT_DIR = ".git"


class DetectKind(Enum):
    NONE = auto()
    SINGLE = auto()
    AMBIGUOUS = auto()


@dataclass(frozen=True)
class DetectResult:
    kind: DetectKind
    path: Path | None

    def require_path(self) -> Path:
        # valid for SINGLE results, which always carry a path
        assert self.path is not None, "SINGLE detection must carry a path"
        return self.path


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
    skill_dirs = list(iter_skill_dirs(git_root))

    if not skill_dirs:
        return DetectResult(DetectKind.NONE, None)

    parents = [sd.parent for sd in skill_dirs]
    common = _deepest_common_ancestor(parents, fallback=git_root)

    # compare by `parts`, not `==`: a real and a faked-fs `Path` to the same
    # location are unequal under `==` but share `parts`
    if common.parts == git_root.parts:
        return DetectResult(DetectKind.AMBIGUOUS, None)

    return DetectResult(DetectKind.SINGLE, common)


def has_any_skill(root: Path) -> bool:
    return next(iter_skill_dirs(root), None) is not None


def path_within(path: Path, root: Path) -> bool:
    # return whether `path` lands on or inside `root`
    # note: symlinks are never followed
    norm_path = Path(os.path.normpath(path))
    norm_root = Path(os.path.normpath(root))
    return norm_path.parts[: len(norm_root.parts)] == norm_root.parts


def normalize_repo_dir(git_root: Path, skills_dir: str) -> Path | None:
    # resolve `skills_dir` to an absolute path inside `git_root`
    target = Path(os.path.normpath(git_root / skills_dir))
    if not path_within(target, git_root):
        return None

    return target


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
