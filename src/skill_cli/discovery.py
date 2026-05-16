from pathlib import Path

from .manifest import Manifest, default_install_dir, default_manifest_path


def find_repo_skills_dir(
    cwd: Path | None = None,
    manifest_path: Path | None = None,
) -> Path | None:
    if cwd is None:
        cwd = Path.cwd()
    root = _find_git_root(cwd)
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


def _find_git_root(start: Path) -> Path | None:
    current = start.resolve()
    while True:
        if (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent
