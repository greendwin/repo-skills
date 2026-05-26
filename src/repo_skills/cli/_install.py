from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated, Optional

import typer

from repo_skills.config import (
    Source,
    SourceRegistry,
    compute_file_hashes,
    load_provider_registry,
    load_skill_manifest,
    load_source_registry,
    save_skill_manifest,
)
from repo_skills.errors import AppError
from repo_skills.git import GitRepo
from repo_skills.utils import fmt_command, fmt_ident, fmt_path

from ._app import app
from ._deps import resolve_git_repo
from ._utils import echo


@app.command(help="Install a skill from a source.")
def install(
    *,
    names: Annotated[
        list[str],
        typer.Argument(help="Skill name(s) to install."),
    ],
    source: Annotated[
        Optional[str],
        typer.Option("--source", "-s", help="Source name (required when multiple)."),
    ] = None,
    offline: Annotated[
        bool,
        typer.Option("--offline", help="Skip git pull."),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing skill."),
    ] = False,
) -> None:
    source_registry = load_source_registry()
    pulled_sources: set[str] = set()
    for name in names:
        _install_one(
            source_registry,
            name,
            from_source=source,
            offline=offline,
            force=force,
            pulled_sources=pulled_sources,
        )


@app.command(help="Uninstall a skill.")
def uninstall(
    *,
    names: Annotated[
        list[str],
        typer.Argument(help="Skill name(s) to uninstall."),
    ],
) -> None:
    manifest = load_skill_manifest()
    provider_registry = load_provider_registry()

    for name in names:
        if name not in manifest.skills:
            raise AppError(f"Skill {fmt_ident(name)} is not installed.")

        for provider in provider_registry.providers.values():
            dst = provider.install_path / name
            if dst.exists():
                shutil.rmtree(dst)

        manifest.unregister_skill(name)
        save_skill_manifest(manifest)

        echo(f"Uninstalled {fmt_ident(name)}.")


def _install_one(
    source_registry: SourceRegistry,
    skill_name: str,
    *,
    from_source: str | None,
    offline: bool,
    force: bool,
    pulled_sources: set[str],
) -> None:
    source = _resolve_source(source_registry, from_source, skill_name=skill_name)

    git = resolve_git_repo(source.repo_root)
    if not offline and source.name not in pulled_sources:
        git.pull()
        pulled_sources.add(source.name)
    validate_repo(git, branch=source.get_branch(git))

    skill = source.skills.get(skill_name)
    if skill is None:
        raise AppError(
            f"Skill {fmt_ident(skill_name)} not found in source "
            f"{fmt_ident(source.name)}."
        )

    src = source.repo_root / skill.rel_path
    commit = _resolve_commit(git, skill_name)

    provider_registry = load_provider_registry()

    for prov_name, provider in provider_registry.providers.items():
        _copy_skill(
            src,
            skill_name,
            install_dir=provider.install_path,
            provider_name=prov_name,
            force=force,
        )

    _record_manifest(
        skill_name,
        source_name=source.name,
        commit=commit,
        skill_src=src,
    )

    echo(f"Installed {fmt_ident(skill_name)} from {fmt_ident(source.name)}.")


def _resolve_source(
    source_registry: SourceRegistry, source_name: str | None, *, skill_name: str
) -> Source:
    if not source_registry.sources:
        raise AppError(
            "No sources registered.",
            hint=f"Run {fmt_command('skills source init')} first.",
        )

    if source_name is not None:
        if source_name not in source_registry.sources:
            raise AppError(f"Source {fmt_ident(source_name)} not found.")

        return source_registry.get_source(source_name, load_skills=True)

    if len(source_registry.sources) == 1:
        only = next(iter(source_registry.sources))
        return source_registry.get_source(only, load_skills=True)

    matches: list[Source] = []
    for sn in source_registry.sources:
        candidate = source_registry.get_source(sn, load_skills=True)
        if skill_name in candidate.skills:
            matches.append(candidate)

    if len(matches) == 1:
        return matches[0]

    names = ", ".join(
        fmt_ident(name) for name in sorted(source_registry.sources.keys())
    )
    raise AppError(
        f"Multiple sources registered ({names}).",
        hint=f"Use {fmt_command('--source')} to specify.",
    )


def validate_repo(git: GitRepo, *, branch: str) -> None:
    if not git.is_clean():
        raise AppError(
            "Repo has uncommitted changes.",
            props={"repo": fmt_path(git.root)},
        )

    # TODO: lets switch automatically if it's clean
    # TODO: merge this code with others that check current_branch and
    #       switches to it (in update/merge modules)
    current = git.current_branch()
    if current != branch:
        raise AppError(
            f"Not on the pinned branch (on {fmt_ident(current)},"
            f" expected {fmt_ident(branch)}).",
            hint=f"Use {fmt_command(f'source init --branch {current}')}"
            " to change the pin.",
        )


def _resolve_commit(git: GitRepo, skill_name: str) -> str:
    commit = git.get_skill_commit(skill_name)
    if git.verify_commit_content(commit, skill_name):
        return commit

    raise AppError(
        f"Skill {fmt_ident(skill_name)} content does not match commit {commit}."
    )


def _record_manifest(
    name: str,
    *,
    source_name: str,
    commit: str,
    skill_src: Path,
) -> None:
    manifest = load_skill_manifest()
    manifest.register_skill(
        name,
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
            f"Skill {fmt_ident(name)} already exists at provider "
            f"{fmt_ident(provider_name)}.",
            hint=f"Use {fmt_command('--force')} to overwrite.",
        )

    if dst.exists():
        shutil.rmtree(dst)

    install_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)
