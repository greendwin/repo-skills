from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated, Optional

import typer
from typer_di import Depends

from repo_skills.config import SkillEntry as ManifestSkillEntry
from repo_skills.config import (
    compute_file_hashes,
    load_provider_registry,
    load_skill_manifest,
    load_source_config,
    load_source_registry,
    save_skill_manifest,
)
from repo_skills.errors import AppError
from repo_skills.git import GitRepo
from repo_skills.manifest import Manifest

from ._app import app
from ._deps import (
    resolve_git_repo,
    resolve_install_dir,
    resolve_manifest_path,
)
from ._utils import echo


@app.command(help="Install a skill from a source.")
def install(
    *,
    name: str,
    source: Annotated[
        Optional[str],
        typer.Option("--source", help="Source name (required when multiple)."),
    ] = None,
    offline: Annotated[
        bool,
        typer.Option("--offline", help="Skip git pull."),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite existing skill."),
    ] = False,
) -> None:
    source_name, source_path = _resolve_source(source)

    source_cfg = load_source_config(source_path)
    skills_dir = source_path / source_cfg.skills_dir

    git = resolve_git_repo(source_path)
    if not offline:
        git.pull()
    _validate_repo(git)

    src = skills_dir / name
    if not src.is_dir():
        raise AppError(
            f"Skill [cyan]{name}[/cyan] not found in source "
            f"[cyan]{source_name}[/cyan]."
        )

    commit = _resolve_commit(git, name)

    providers = load_provider_registry()

    for pname, pcfg in providers.providers.items():
        install_dir = Path(pcfg.install_dir).expanduser()
        _copy_skill(
            src, name, install_dir=install_dir, provider_name=pname, force=force
        )

    _record_manifest(
        name,
        source_name=source_name,
        commit=commit,
        skill_src=src,
    )

    echo(f"Installed [green]{name}[/green] from [cyan]{source_name}[/cyan].")


@app.command(help="Uninstall a skill.")
def uninstall(
    name: str,
    install_dir: Path = Depends(resolve_install_dir),
    manifest_path: Path = Depends(resolve_manifest_path),
) -> None:
    dst = install_dir / name
    if not dst.exists():
        raise AppError(f"Skill '{name}' is not installed.")

    shutil.rmtree(dst)

    manifest = Manifest.load(manifest_path)
    manifest.skills.pop(name, None)
    manifest.save(manifest_path)

    typer.echo(f"Uninstalled '{name}'.")


def _record_manifest(
    name: str,
    *,
    source_name: str,
    commit: str,
    skill_src: Path,
) -> None:
    manifest = load_skill_manifest()
    manifest.skills[name] = ManifestSkillEntry(
        source=source_name,
        commit=commit,
        files=compute_file_hashes(skill_src),
    )
    save_skill_manifest(manifest)


def _copy_skill(
    src: Path,
    name: str,
    *,
    install_dir: Path,
    provider_name: str,
    force: bool,
) -> None:
    dst = install_dir / name

    if dst.exists() and not force:
        raise AppError(
            f"Skill [cyan]{name}[/cyan] already exists at provider "
            f"[cyan]{provider_name}[/cyan]. Use [bold]--force[/bold] to overwrite."
        )

    if dst.exists():
        shutil.rmtree(dst)

    install_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)


def _resolve_source(source_name: str | None) -> tuple[str, Path]:
    registry = load_source_registry()

    if not registry.sources:
        raise AppError(
            "No sources registered. Run [bold]skills source init[/bold] first."
        )

    if source_name is not None:
        if source_name not in registry.sources:
            raise AppError(f"Source [cyan]{source_name}[/cyan] not found.")
        return source_name, Path(registry.sources[source_name].path)

    if len(registry.sources) == 1:
        name = next(iter(registry.sources))
        return name, Path(registry.sources[name].path)

    names = ", ".join(sorted(registry.sources.keys()))
    raise AppError(
        f"Multiple sources registered ({names}). "
        f"Use [bold]--source[/bold] to specify."
    )


def _validate_repo(git: GitRepo) -> None:
    main = git.get_main_branch()
    current = git.current_branch()
    if current != main:
        raise AppError(f"Not on main branch (on '{current}', expected '{main}').")

    if not git.is_clean():
        raise AppError("Repo has uncommitted changes.")


def _resolve_commit(git: GitRepo, skill_name: str) -> str:
    commit = git.get_skill_commit(skill_name)
    if git.verify_commit_content(commit, skill_name):
        return commit

    raise AppError(f"Skill '{skill_name}' content does not match commit {commit}.")
