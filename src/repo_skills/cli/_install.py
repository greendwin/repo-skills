from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated, Optional

import typer

from repo_skills.config import (
    SkillManifest,
    Source,
    SourceRegistry,
    load_provider_registry,
    load_skill_manifest,
    load_source_registry,
    make_baseline,
    save_skill_manifest,
)
from repo_skills.config._source import SourceSkill
from repo_skills.console import console, fmt_command, fmt_data, fmt_ident
from repo_skills.errors import AppError
from repo_skills.git import GitRepo, ensure_on_branch, resolve_verified_commit

from ._app import app
from ._deps import resolve_git_repo


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
    manifest = load_skill_manifest()
    source_registry = load_source_registry()

    pulled_sources: set[str] = set()
    for name in names:
        _install_one(
            manifest,
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

        for provider in provider_registry.providers:
            dst = provider.install_path / name
            if dst.exists():
                shutil.rmtree(dst)

        manifest.unregister_skill(name)
        save_skill_manifest(manifest)

        console.print(f"Uninstalled {fmt_ident(name)}.")


def _install_one(
    manifest: SkillManifest,
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
    ensure_on_branch(
        git,
        source.get_branch(git),
        pull=not offline and source.name not in pulled_sources,
        require_clean=False,  # if pull is not needed, it's ok to have dirty repo
    )
    pulled_sources.add(source.name)

    skill = source.skills.get(skill_name)
    if skill is None:
        raise AppError(
            f"Skill {fmt_ident(skill_name)} not found in source "
            f"{fmt_ident(source.name)}."
        )

    src = source.repo_root / skill.rel_path
    commit = _resolve_commit(git, skill)

    provider_registry = load_provider_registry()

    for provider in provider_registry.providers:
        _copy_skill(
            src,
            skill_name,
            install_dir=provider.install_path,
            provider_name=provider.name,
            force=force,
        )

    _record_manifest(manifest, source, skill, commit)

    console.print(f"Installed {fmt_ident(skill_name)} from {fmt_ident(source.name)}.")


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


def _resolve_commit(git: GitRepo, skill: SourceSkill) -> str:
    commit = resolve_verified_commit(git, skill.rel_path)
    if commit is None:
        raise AppError(
            f"Skill {fmt_ident(skill.name)} content does not match "
            f"commit {fmt_data(git.get_skill_commit(skill.rel_path)[:8])}."
        )

    return commit


def _record_manifest(
    manifest: SkillManifest, source: Source, skill: SourceSkill, commit: str
) -> None:
    manifest.register_skill(
        skill.name,
        source_name=source.name,
        baseline=make_baseline(commit, source.repo_root / skill.rel_path),
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
