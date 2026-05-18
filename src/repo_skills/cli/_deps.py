from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Optional

import typer
from typer_di import Depends

from repo_skills._git import GitRepo
from repo_skills.discovery import find_install_dir, find_repo_skills_dir
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
        typer.echo("Cannot find skills repo. Run from within the repo.", err=True)
        raise typer.Exit(1)

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
        typer.echo("Cannot find install directory.", err=True)
        raise typer.Exit(1)

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


def resolve_git_repo(repo_dir: Path) -> GitRepo:
    if _git_repo_factory is not None:
        return _git_repo_factory(repo_dir)
    from repo_skills._git_real import RealGitRepo

    return RealGitRepo(repo_dir)
