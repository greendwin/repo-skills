from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated, Optional

import typer
from typer_di import Depends

from repo_skills._git import GitRepo
from repo_skills.manifest import Manifest, SkillEntry

from ._app import app
from ._deps import (
    resolve_git_repo,
    resolve_install_dir,
    resolve_install_dir_opt,
    resolve_manifest_path,
    resolve_repo_dir,
)


@app.command(help="Install a skill from the repo.")
def install(
    *,
    name: str,
    offline: Annotated[
        bool,
        typer.Option("--offline", help="Skip git pull."),
    ] = False,
    repo_dir: Path = Depends(resolve_repo_dir),
    install_dir: Optional[Path] = Depends(resolve_install_dir_opt),
    manifest_path: Path = Depends(resolve_manifest_path),
) -> None:
    git = resolve_git_repo(repo_dir.parent)

    if not offline:
        git.pull()

    _validate_repo(git)

    src = repo_dir / name
    if not src.is_dir():
        typer.echo(f"Skill '{name}' not found in repo.", err=True)
        raise typer.Exit(1)

    if install_dir is None:
        install_dir = manifest_path.parent
    install_dir.mkdir(parents=True, exist_ok=True)

    dst = install_dir / name
    if dst.exists():
        typer.echo(f"Skill '{name}' is already installed.", err=True)
        raise typer.Exit(1)

    commit = _resolve_commit(git, name)

    shutil.copytree(src, dst)

    manifest = Manifest.load(manifest_path)
    manifest.repo_path = str(repo_dir.parent)
    manifest.skills[name] = SkillEntry(commit=commit)
    manifest.save(manifest_path)

    typer.echo(f"Installed '{name}'.")


@app.command(help="Uninstall a skill.")
def uninstall(
    name: str,
    install_dir: Path = Depends(resolve_install_dir),
    manifest_path: Path = Depends(resolve_manifest_path),
) -> None:
    dst = install_dir / name
    if not dst.exists():
        typer.echo(f"Skill '{name}' is not installed.", err=True)
        raise typer.Exit(1)

    shutil.rmtree(dst)

    manifest = Manifest.load(manifest_path)
    manifest.skills.pop(name, None)
    manifest.save(manifest_path)

    typer.echo(f"Uninstalled '{name}'.")


def _validate_repo(git: GitRepo) -> None:
    main = git.get_main_branch()
    current = git.current_branch()
    if current != main:
        typer.echo(
            f"Not on main branch (on '{current}', expected '{main}').",
            err=True,
        )
        raise typer.Exit(1)

    if not git.is_clean():
        typer.echo("Repo has uncommitted changes.", err=True)
        raise typer.Exit(1)


def _resolve_commit(git: GitRepo, skill_name: str) -> str:
    commit = git.get_skill_commit(skill_name)
    if git.verify_commit_content(commit, skill_name):
        return commit

    typer.echo(
        f"Skill '{skill_name}' content does not match commit {commit}.",
        err=True,
    )
    raise typer.Exit(1)
