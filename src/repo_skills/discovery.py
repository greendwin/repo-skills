from __future__ import annotations

import os
from collections.abc import Iterator
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


def _iter_skill_dirs(root: Path) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        if SKILL_FILE in filenames:
            # outermost SKILL.md wins; don't descend into a skill's internals
            dirnames.clear()
            yield Path(dirpath)


def detect_skills_dir(git_root: Path) -> DetectResult:
    skill_dirs = list(_iter_skill_dirs(git_root))

    if not skill_dirs:
        return DetectResult(DetectKind.NONE, None)

    parents = [sd.parent for sd in skill_dirs]
    common = _deepest_common_ancestor(parents, fallback=git_root)

    # compared by ``parts`` (not ``==``) so detection stays correct when the two
    # paths come from different ``Path`` flavours (e.g. a real ``pathlib`` path
    # built here versus a faked filesystem root)
    if common.parts == git_root.parts:
        return DetectResult(DetectKind.AMBIGUOUS, None)

    return DetectResult(DetectKind.SINGLE, common)


def has_any_skill(root: Path) -> bool:
    return next(_iter_skill_dirs(root), None) is not None


def path_within(path: Path, root: Path) -> bool:
    """Return whether ``path`` lands on or inside ``root``.

    Containment is judged lexically: both inputs are normalized with
    ``os.path.normpath`` (``..`` collapsed, ``.`` dropped) and compared by
    path components, so symlinks are never followed and the check rests purely
    on the textual targets. Callers need not pre-normalize.
    """
    norm_path = Path(os.path.normpath(path))
    norm_root = Path(os.path.normpath(root))
    return norm_path.parts[: len(norm_root.parts)] == norm_root.parts


def normalize_repo_dir(git_root: Path, skills_dir: str) -> Path | None:
    """Resolve ``skills_dir`` to an absolute path inside ``git_root``.

    Accepts any path (existing or not, including the repo root itself) as long
    as it does not escape the repo; an absolute path outside the repo or a
    ``../`` traversal beyond the root returns ``None``. Resolution is lexical
    (symlinks are not followed), and the returned path is exactly the one whose
    containment was validated.
    """
    target = Path(os.path.normpath(git_root / skills_dir))
    if not path_within(target, git_root):
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
