from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Optional

import typer
from typer_di import Depends

from repo_skills.config import Source
from repo_skills.discovery import find_git_root, find_install_dir, find_repo_skills_dir
from repo_skills.errors import AppError
from repo_skills.git import GitRepo, SyncedRepo, ensure_on_branch
from repo_skills.git_real import RealGitRepo
from repo_skills.manifest import default_manifest_path


def resolve_repo_dir(
    repo_skills_dir: Annotated[
        Optional[str],
        typer.Option(
            "--repo-skills-dir",
            help="Path to the repo skills directory.",
            file_okay=False,
            dir_okay=True,
            exists=True,
        ),
    ] = None,
) -> Path:
    if repo_skills_dir:
        return Path(repo_skills_dir)

    repo_dir = find_repo_skills_dir()
    if repo_dir is None:
        raise AppError("Cannot find skills repo. Run from within the repo.")

    return repo_dir


def resolve_install_dir_opt(
    install_dir: Annotated[
        Optional[str],
        typer.Option(
            "--install-dir",
            help="Path to the skill install directory.",
            file_okay=False,
            dir_okay=True,
            exists=True,
        ),
    ] = None,
) -> Optional[Path]:
    if install_dir:
        return Path(install_dir)
    return find_install_dir()


def resolve_install_dir(
    install_dir: Optional[Path] = Depends(resolve_install_dir_opt),
) -> Path:
    if install_dir is None:
        raise AppError("Cannot find install directory.")

    return install_dir


def resolve_manifest_path(
    manifest_path: Annotated[
        Optional[str],
        typer.Option("--manifest-path", help="Path to the manifest file."),
    ] = None,
) -> Path:
    if manifest_path:
        return Path(manifest_path)
    return default_manifest_path()


_git_repo_factory: Callable[[Path], GitRepo] | None = None


def resolve_git_repo(path: Path) -> GitRepo:
    git_root = find_git_root(path)
    if git_root is None:
        raise AppError("Not inside a git repository.")

    if _git_repo_factory is not None:
        return _git_repo_factory(git_root)

    return RealGitRepo(git_root)


def prepare_source_repo(source: Source, *, pull: bool) -> SyncedRepo:
    git = resolve_git_repo(source.repo_root)
    target_branch = source.get_branch(git)
    return ensure_on_branch(git, target_branch, pull=pull)
