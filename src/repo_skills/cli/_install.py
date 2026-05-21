from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated, Optional

import typer

from repo_skills.config import SkillEntry as ManifestSkillEntry
from repo_skills.config import (
    compute_file_hashes,
    list_source_skills,
    load_provider_registry,
    load_skill_manifest,
    load_source_config,
    load_source_registry,
    save_skill_manifest,
)
from repo_skills.errors import AppError
from repo_skills.git import GitRepo

from ._app import app
from ._deps import resolve_git_repo
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
    any_branch: Annotated[
        bool,
        typer.Option("--any-branch", help="Allow install from any branch."),
    ] = False,
) -> None:
    source_name, source_path = _resolve_source(source, skill_name=name)

    source_cfg = load_source_config(source_path)
    skills_dir = source_path / source_cfg.skills_dir

    git = resolve_git_repo(source_path)
    if not offline:
        git.pull()
    _validate_repo(git, any_branch=any_branch)

    src = skills_dir / name
    if not src.is_dir():
        raise AppError(
            f"Skill [green]{name}[/green] not found in source "
            f"[green]{source_name}[/green]."
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

    echo(f"Installed [green]{name}[/green] from [green]{source_name}[/green].")


@app.command(help="Uninstall a skill.")
def uninstall(
    *,
    name: str,
) -> None:
    manifest = load_skill_manifest()
    if name not in manifest.skills:
        raise AppError(f"Skill [green]{name}[/green] is not installed.")

    providers = load_provider_registry()
    for _pname, pcfg in providers.providers.items():
        dst = Path(pcfg.install_dir).expanduser() / name
        if dst.exists():
            shutil.rmtree(dst)

    manifest.skills.pop(name)
    save_skill_manifest(manifest)

    echo(f"Uninstalled [green]{name}[/green].")


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
            f"Skill [green]{name}[/green] already exists at provider "
            f"[green]{provider_name}[/green].\n\nUse [blue]--force[/blue] to overwrite."
        )

    if dst.exists():
        shutil.rmtree(dst)

    install_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)


def _resolve_source(source_name: str | None, *, skill_name: str) -> tuple[str, Path]:
    registry = load_source_registry()

    if not registry.sources:
        raise AppError(
            "No sources registered.\n\nRun [blue]skills source init[/blue] first."
        )

    if source_name is not None:
        if source_name not in registry.sources:
            raise AppError(f"Source [green]{source_name}[/green] not found.")
        return source_name, Path(registry.sources[source_name].path)

    if len(registry.sources) == 1:
        name = next(iter(registry.sources))
        return name, Path(registry.sources[name].path)

    matches = [
        sn
        for sn, se in registry.sources.items()
        if skill_name in list_source_skills(Path(se.path))
    ]

    if len(matches) == 1:
        return matches[0], Path(registry.sources[matches[0]].path)

    names = ", ".join(sorted(registry.sources.keys()))
    raise AppError(
        f"Multiple sources registered ({names}).\n\n"
        f"Use [blue]--source[/blue] to specify."
    )


def _validate_repo(git: GitRepo, *, any_branch: bool = False) -> None:
    main = git.get_main_branch()
    current = git.current_branch()
    if current != main and not any_branch:
        raise AppError(
            f"Not on main branch (on '{current}', expected '{main}').\n"
            f"  repo: [dim]{git.path}[/dim]\n\n"
            f"Use [blue]--any-branch[/blue] to override."
        )

    if not git.is_clean():
        raise AppError(f"Repo has uncommitted changes.\n  repo: [dim]{git.path}[/dim]")


def _resolve_commit(git: GitRepo, skill_name: str) -> str:
    commit = git.get_skill_commit(skill_name)
    if git.verify_commit_content(commit, skill_name):
        return commit

    raise AppError(
        f"Skill [green]{skill_name}[/green] content does not match commit {commit}."
    )
